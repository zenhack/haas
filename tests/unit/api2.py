from haas import api, model
from moc.rest import req_local
from schema import Schema, Use, And
from sqlalchemy import create_engine
from uuid import UUID
from werkzeug.local import release_local
import json
import pytest
import unittest


@pytest.yield_fixture
def setup_db():
    engine = create_engine("sqlite:///:memory:")
    model.Base.metadata.create_all(engine)
    model.Session.configure(bind=engine)
    yield
    release_local(req_local)

pytestmark = pytest.mark.usefixtures("setup_db")


@pytest.mark.parametrize('typ,input,output', [

    # A node with no nics:
    ('node',

        {
            "ipmi": {
                "host": "ipmi.node4.example.com",
                "user": "alice",
                "pass": "secret",
            },
        },

        {
            "uuid": Use(UUID),
            "free": True,
            "ipmi": {
                "host": "ipmi.node4.example.com",
                "user": "alice",
                "pass": "secret",
            },
        }),

    # A node with one nic
    ('node',

        {
            "ipmi": {
                "host": "ipmi.node4.example.com",
                "user": "alice",
                "pass": "secret",
            },
            "nics": {
                "eth0": {
                    "mac_addr": "de:ad:be:ef:20:14",
                    "port": "gi1/0/4",
                },
            },
        },

        {
            "uuid": Use(UUID),
            "free": True,
            "ipmi": {
                "host": "ipmi.node4.example.com",
                "user": "alice",
                "pass": "secret",
            },
            "nics": {
                "eth0": {
                    "uuid": Use(UUID),
                    "mac_addr": And(Use(str.lower), "de:ad:be:ef:20:14"),
                    "port": "gi1/0/4",
                },
            },
        }),

])
def test_uuid_object_create(typ, input, output):
    """Test ``api.uuid_object_create`` for various types & values."""
    result = api.uuid_object_create(typ, json.dumps(input))
    Schema(And(Use(json.loads, output))).validate(result)


class Test_project_create(object):

    def test_create_one(self):
        """Create a single project. Should succeed."""
        api.project_create("manhattan", "")
        api._must_find(req_local.db, model.Project, name="manhattan")

    def test_duplicate(self):
        """Try to create a duplicate project, which should fail."""
        api.project_create("manhattan", "")
        with pytest.raises(api.DuplicateError):
            api.project_create("manhattan", "")

    def test_two_different(self):
        """Create two projects, with different names. Should succeed."""
        for name in "manhattan", "runway":
            api.project_create(name, "")
            api._must_find(req_local.db, model.Project, name=name)


class Test_project_delete(unittest.TestCase):

    def setUp(self):
        api.project_create("runway", "")

    def test_delete_once(self):
        """Delete a project that exists (once)."""
        api.project_delete("runway", "")
        api._assert_absent(req_local.db, model.Project, name="runway")

    def test_delete_twice(self):
        """Delete a project that exists, twice. The second try should fail."""
        api.project_delete("runway", "")
        with pytest.raises(api.NotFoundError):
            api.project_delete("runway", "")

    def test_delete_nonexistant(self):
        """Try to delete a project that doesn't exist. Should fail."""
        with pytest.raises(api.NotFoundError):
            api.project_delete("manhattan", "")
