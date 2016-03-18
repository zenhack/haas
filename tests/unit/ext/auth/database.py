from haas import api, model, config, server
from haas.test_common import config_testsuite, config_merge, fresh_database, \
    ModelTest
from haas.errors import AuthorizationError
from haas.rest import app, init_auth, DBContext, local
from haas.ext.auth.database import User, user_create, user_delete, \
    user_add_project, user_remove_project
import flask
import pytest
import unittest


@pytest.fixture
def configure():
    config_testsuite()
    config_merge({
        'auth': {
            # The tests in this module are checking the specific authorization
            # requirements of the API calls. as such, we don't want things to
            # fail due to complete lack of authentication, where they should
            # fail later when the specific authorization checks we're testing
            # for happen.
            'require_authentication': 'False',
        },
        'extensions': {
            'haas.ext.auth.database': '',
            'haas.ext.auth.null': None,
        },
    })
    config.load_extensions()


@pytest.fixture
def db(request):
    session = fresh_database(request)
    alice = User(label='alice',
                 password='secret',
                 is_admin=True)
    bob = User(label='bob',
               password='password',
               is_admin=False)

    session.add(alice)
    session.add(bob)

    runway = model.Project('runway')
    runway.users.append(alice)
    session.add(runway)
    session.commit()

    return session


@pytest.fixture
def server_init():
    server.register_drivers()
    server.validate_state()

@pytest.yield_fixture
def db_context():
    with app.test_request_context():
        with DBContext():
            yield


@pytest.fixture
def auth_context():
    init_auth()


class FakeAuthRequest(object):
    """Fake (authenticated) request object.

    This spoofs just enough of flask's request functionality for the
    database auth plugin to work.
    """

    def __init__(self, username, password):
        self.username = username
        self.password = password

    @property
    def authorization(self):
        return self


class FakeNoAuthRequest(object):
    """Fake (unauthenticated) request object.

    Like `FakeAuthRequest`, except that the spoofed request is
    unauthenticated.
    """
    authorization = None


@pytest.fixture
def admin_auth():
    """Inject mock credentials that give the request admin access."""
    flask.request = FakeAuthRequest('alice', 'secret')


@pytest.fixture
def runway_auth():
    """Inject mock credentials that give the request access to the "runway" project."""
    flask.request = FakeAuthRequest('bob', 'password')


@pytest.fixture
def no_auth():
    """Spoof an unauthenticated request."""
    flask.request = FakeNoAuthRequest()


def use_fixtures(auth_fixture):
    return pytest.mark.usefixtures('configure',
                                   'db',
                                   'server_init',
                                   'db_context',
                                   auth_fixture,
                                   'auth_context')


@use_fixtures('admin_auth')
class TestUserCreateDelete(unittest.TestCase):
    """Tests for user_create and user_delete."""

    def test_new_user(self):
        api._assert_absent(User, 'charlie')
        user_create('charlie', 'foo')

    def test_duplicate_user(self):
        user_create('charlie', 'secret')
        with pytest.raises(api.DuplicateError):
                user_create('charlie', 'password')

    def test_delete_user(self):
        user_create('charlie', 'foo')
        user_delete('charlie')

    def test_delete_missing_user(self):
        with pytest.raises(api.NotFoundError):
            user_delete('charlie')

    def test_delete_user_twice(self):
        user_create('charlie', 'foo')
        user_delete('charlie')
        with pytest.raises(api.NotFoundError):
            user_delete('charlie')

    def _new_user(self, is_admin):
        """Helper method for creating/switching to a new user.

        A new admin user will be created with the credentials:

        username: 'charlie'
        password: 'foo'

        The argument is_admin determines whether the user has admin rights.

        Once the user has been created, the authentication info will be
        changed to that user.
        """
        user_create('charlie', 'foo', is_admin=is_admin)
        flask.request = FakeAuthRequest('charlie', 'foo')
        local.auth = local.db.query(User).filter_by(label='charlie').one()

    def test_new_admin_can_admin(self):
        """Verify that a newly created admin can actually do admin stuff."""
        self._new_user(is_admin=True)
        user_delete('charlie')

    def test_new_non_admin_cannot_admin(self):
        """Verify that a newly created regular user can't do admin stuff."""
        self._new_user(is_admin=False)
        with pytest.raises(AuthorizationError):
            user_delete('charlie')


@use_fixtures('admin_auth')
class TestUserAddRemoveProject(unittest.TestCase):
    """Tests for user_add_project/user_remove_project."""

    def test_user_add_project(self):
        user_create('charlie', 'secret')
        api.project_create('acme-corp')
        user_add_project('charlie', 'acme-corp')
        user = api._must_find(User, 'charlie')
        project = api._must_find(model.Project, 'acme-corp')
        assert project in user.projects
        assert user in project.users

    def test_user_remove_project(self):
        user_create('charlie', 'secret')
        api.project_create('acme-corp')
        user_add_project('charlie', 'acme-corp')
        user_remove_project('charlie', 'acme-corp')
        user = api._must_find(User, 'charlie')
        project = api._must_find(model.Project, 'acme-corp')
        assert project not in user.projects
        assert user not in project.users

    def test_duplicate_user_add_project(self):
        user_create('charlie', 'secret')
        api.project_create('acme-corp')
        user_add_project('charlie', 'acme-corp')
        with pytest.raises(api.DuplicateError):
            user_add_project('charlie', 'acme-corp')

    def test_bad_user_remove_project(self):
        """Tests that removing a user from a project they're not in fails."""
        user_create('charlie', 'secret')
        api.project_create('acme-corp')
        with pytest.raises(api.NotFoundError):
            user_remove_project('charlie', 'acme-corp')


@pytest.mark.usefixtures('configure', 'db')
class TestUserModel(ModelTest):
    """Basic sanity check for the User model.

    Similar to the tests in /tests/unit/model.py, which cover the models
    defined in HaaS core.
    """

    def sample_obj(self):
        return User('charlie', 'secret')


admin_calls = [
    (user_create, ['charlie', '1337']),
    (user_create, ['charlie', '1337', False]),
    (user_create, ['charlie', '1337', True]),
    (user_delete, ['bob']),
    (user_add_project, ['bob', 'runway']),
    (user_remove_project, ['alice', 'runway']),
]


@pytest.mark.parametrize('fn,args', admin_calls)
@use_fixtures('admin_auth')
def test_admin_succeed(fn, args):
    """Verify that an admin-only call succeds when invoked by an admin."""
    fn(*args)


@pytest.mark.parametrize('fn,args', admin_calls)
@use_fixtures('runway_auth')
def test_admin_runway_fail(fn, args):
    """Verify that an admin-only call fails when invoked by a non-admin user."""
    with pytest.raises(AuthorizationError):
        fn(*args)


@pytest.mark.parametrize('fn,args', admin_calls)
@use_fixtures('no_auth')
def test_admin_noauth_fail(fn, args):
    """Verify that an admin-only call fails when invoked without authentication."""
    with pytest.raises(AuthorizationError):
        fn(*args)
