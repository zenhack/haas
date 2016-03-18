"""Tests related to the authorization of api calls.

NOTE: while all of these are conceptually authorization related, some illegal
operations will raise exceptions other than AuthorizationError. This usually
happens when the operation is illegal *in principle*, and would not be fixed by
authenticating as someone else. We were already raising exceptions in
these cases before actually adding authentication and authorization to
the mix. They are still tested here, since they are important for security.
"""

import pytest
import unittest
from haas import api, config, model, server, deferred
from haas.network_allocator import get_network_allocator
from haas.rest import local
from haas.auth import get_auth_backend
from haas.errors import AuthorizationError, BadArgumentError, \
    ProjectMismatchError, BlockedError
from haas.test_common import config_testsuite, config_merge, fresh_database, \
    with_request_context

from haas.ext.switches.mock import MockSwitch
from haas.ext.obm.mock import MockObm


def auth_call_test(fn, error, admin, project, args, kwargs={}):
    """Test the authorization properties of an api call.

    Parmeters:

        * `fn` - the api function to call
        * `error` - The error that should be raised. None if no error should
                    be raised.
        * `admin` - Whether the request should have admin access.
        * `project` - The name of the project the request should be
                      authenticated as. Can be None if `admin` is True.
        * `args` - the arguments (as a list) to `fn`.
    """
    auth_backend = get_auth_backend()
    auth_backend.set_admin(admin)
    if not admin:
        project = local.db.query(model.Project).filter_by(label=project).one()
        auth_backend.set_project(project)

    if error is None:
        fn(*args, **kwargs)
    else:
        with pytest.raises(error):
            fn(*args, **kwargs)


@pytest.fixture
def configure():
    config_testsuite()
    config_merge({
        'extensions': {
            'haas.ext.auth.mock': '',

            # This extension is enabled by default in the tests, so we need to
            # disable it explicitly:
            'haas.ext.auth.null': None,
            'haas.ext.switches.mock': '',
            'haas.ext.obm.mock': ''
        },
    })
    config.load_extensions()


@pytest.fixture
def db(request):
    session = fresh_database(request)
    # Create a couple projects:
    runway = model.Project("runway")
    manhattan = model.Project("manhattan")
    for proj in [runway, manhattan]:
        session.add(proj)

    # ...including at least one with nothing in it:
    session.add(model.Project('empty-project'))

    # ...A variety of networks:

    networks = [
        {
            'creator': None,
            'access': None,
            'allocated': True,
            'label': 'stock_int_pub',
        },
        {
            'creator': None,
            'access': None,
            'allocated': False,
            'network_id': 'ext_pub_chan',
            'label': 'stock_ext_pub',
        },
        {
            # For some tests, we want things to initial be attached to a
            # network. This one serves that purpose; using the others would
            # interfere with some of the network_delete tests.
            'creator': None,
            'access': None,
            'allocated': True,
            'label': 'pub_default',
        },
        {
            'creator': runway,
            'access': runway,
            'allocated': True,
            'label': 'runway_pxe'
        },
        {
            'creator': None,
            'access': runway,
            'allocated': False,
            'network_id': 'runway_provider_chan',
            'label': 'runway_provider',
        },
        {
            'creator': manhattan,
            'access': manhattan,
            'allocated': True,
            'label': 'manhattan_pxe'
        },
        {
            'creator': None,
            'access': manhattan,
            'allocated': False,
            'network_id': 'manhattan_provider_chan',
            'label': 'manhattan_provider',
        },
    ]

    for net in networks:
        if net['allocated']:
            net['network_id'] = \
                get_network_allocator().get_new_network_id(session)
        session.add(model.Network(**net))

    # ... Two switches. One of these is just empty, for testing deletion:
    session.add(MockSwitch(label='empty-switch',
                           hostname='empty',
                           username='alice',
                           password='secret',
                           type=MockSwitch.api_name))

    # ... The other we'll actually attach stuff to for other tests:
    switch = MockSwitch(label="stock_switch_0",
                        hostname='stock',
                        username='bob',
                        password='password',
                        type=MockSwitch.api_name)

    # ... Some free ports:
    session.add(model.Port('free_port_0', switch))
    session.add(model.Port('free_port_1', switch))

    # ... Some nodes (with projets):
    nodes = [
        {'label': 'runway_node_0', 'project': runway},
        {'label': 'runway_node_1', 'project': runway},
        {'label': 'manhattan_node_0', 'project': manhattan},
        {'label': 'manhattan_node_1', 'project': manhattan},
        {'label': 'free_node_0', 'project': None},
        {'label': 'free_node_1', 'project': None},
    ]
    for node_dict in nodes:
        obm=MockObm(type=MockObm.api_name,
                    host=node_dict['label'],
                    user='user',
                    password='password')
        node = model.Node(label=node_dict['label'], obm=obm)
        node.project = node_dict['project']
        session.add(model.Nic(node, label='boot-nic', mac_addr='Unknown'))

        # give it a nic that's attached to a port:
        port_nic = model.Nic(node, label='nic-with-port', mac_addr='Unknown')
        port = model.Port(node_dict['label'] + '_port', switch)
        port.nic = port_nic

    # ... Some headnodes:
    headnodes = [
        {'label': 'runway_headnode_on', 'project': runway, 'on': True},
        {'label': 'runway_headnode_off', 'project': runway, 'on': False},
        {'label': 'runway_manhattan_on', 'project': manhattan, 'on': True},
        {'label': 'runway_manhattan_off', 'project': manhattan, 'on': False},
    ]
    for hn_dict in headnodes:
        headnode = model.Headnode(hn_dict['project'],
                                  hn_dict['label'],
                                  'base-headnode')
        headnode.dirty = not hn_dict['on']
        hnic = model.Hnic(headnode, 'pxe')
        session.add(hnic)

        # Connect them to a network, so we can test detaching.
        hnic = model.Hnic(headnode, 'public')
        hnic.network = session.query(model.Network)\
            .filter_by(label='pub_default').one()


    # ... and at least one node with no nics (useful for testing delete):
    obm=MockObm(type=MockObm.api_name,
        host='hostname',
        user='user',
        password='password')
    session.add(model.Node(label='no_nic_node', obm=obm))

    session.commit()
    return session


@pytest.fixture
def server_init():
    server.register_drivers()
    server.validate_state()


with_request_context = pytest.yield_fixture(with_request_context)


pytestmark = pytest.mark.usefixtures('configure',
                                     'db',
                                     'server_init',
                                     'with_request_context')


# We have a *lot* of different parameters with which we're going to invoke
# `test_auth_call`, below. Rather than passing one giant list to the decorator
# in-line, we construct it in stages here:


auth_call_params = [
    # network_create

    ### Legal cases:

    ### Admin creates a public network internal to HaaS:
    dict(fn=api.network_create,
         error=None,
         admin=True,
         project=None,
         args=['pub', 'admin', '', '']),

    ### Admin creates a public network with an existing net_id:
    dict(fn=api.network_create,
         error=None,
         admin=True,
         project=None,
         args=['pub', 'admin', '', 'some-id']),

    ### Admin creates a provider network for some project:
    dict(fn=api.network_create,
         error=None,
         admin=True,
         project=None,
         args=['pxe', 'admin', 'runway', 'some-id']),

    ### Admin creates an allocated network on behalf of a project. Silly, but
    ### legal.
    dict(fn=api.network_create,
         error=None,
         admin=True,
         project=None,
         args=['pxe', 'admin', 'runway', '']),

    ### Project creates a private network for themselves:
    dict(fn=api.network_create,
         error=None,
         admin=False,
         project='runway',
         args=['pxe', 'runway', 'runway', '']),

    ## Illegal cases:

    ### Project tries to create a private network for another project.
    dict(fn=api.network_create,
         error=AuthorizationError,
         admin=False,
         project='runway',
         args=['pxe', 'manhattan', 'manhattan', '']),

    ### Project tries to specify a net_id.
    dict(fn=api.network_create,
         error=BadArgumentError,
         admin=False,
         project='runway',
         args=['pxe', 'runway', 'runway', 'some-id']),

    ### Project tries to create a public network:
    dict(fn=api.network_create,
         error=AuthorizationError,
         admin=False,
         project='runway',
         args=['pub', 'admin', '', '']),

    ### Project tries to set creator to 'admin' on its own network:
    dict(fn=api.network_create,
         error=AuthorizationError,
         admin=False,
         project='runway',
         args=['pxe', 'admin', 'runway', '']),
]

# network_delete

## Legal cases

### admin should be able to delete any network:
for net in [
    'stock_int_pub',
    'stock_ext_pub',
    'runway_pxe',
    'runway_provider',
    'manhattan_pxe',
    'manhattan_provider',
]:
    auth_call_params.append(dict(
        fn=api.network_delete,
        error=None,
        admin=True,
        project=None,
        args=[net]
    ))

### project should be able to delete it's own (created) network:
auth_call_params.append(dict(
    fn=api.network_delete,
    error=None,
    admin=False,
    project='runway',
    args=['runway_pxe']
))

## Illegal cases:

### Project should not be able to delete admin-created networks.
for net in [
    'stock_int_pub',
    'stock_ext_pub',
    'runway_provider',  # ... including networks created for said project.
]:
    auth_call_params.append(dict(
        fn=api.network_delete,
        error=AuthorizationError,
        admin=False,
        project='runway',
        args=[net]
    ))

### Project should not be able to delete networks created by other projects.
for net in [
    'manhattan_pxe',
    'manhattan_provider',
]:
    auth_call_params.append(dict(
        fn=api.network_delete,
        error=AuthorizationError,
        admin=False,
        project='runway',
        args=[net]))

# show_network

## Legal cases

### Public networks should be accessible by anyone:
for net in ('stock_int_pub', 'stock_ext_pub'):
    for project in ('runway', 'manhattan'):
        for admin in (True, False):
            auth_call_params.append(dict(
                fn=api.show_network,
                error=None,
                admin=admin,
                project=project,
                args=[net]
            ))

### Projects should be able to view networks they have access to:
for (project, net) in [
    ('runway', 'runway_pxe'),
    ('runway', 'runway_provider'),
    ('manhattan', 'manhattan_pxe'),
    ('manhattan', 'manhattan_provider'),
]:
    auth_call_params.append(dict(
        fn=api.show_network,
        error=None,
        admin=False,
        project=project,
        args=[net]
    ))

## Illegal cases

### Projects should not be able to access each other's networks:
for (project, net) in [
    ('runway', 'manhattan_pxe'),
    ('runway', 'manhattan_provider'),
    ('manhattan', 'runway_pxe'),
    ('manhattan', 'runway_provider'),
]:
    auth_call_params.append(dict(
        fn=api.show_network,
        error=AuthorizationError,
        admin=False,
        project=project,
        args=[net]
    ))

# node_connect_network

## Legal cases

### Projects should be able to connect their own nodes to their own networks.
for (project, node, net) in [
    ('runway', 'runway_node_0', 'runway_pxe'),
    ('runway', 'runway_node_1', 'runway_provider'),
    ('manhattan', 'manhattan_node_0', 'manhattan_pxe'),
    ('manhattan', 'manhattan_node_1', 'manhattan_provider'),
]:
    auth_call_params.append(dict(
        fn=api.node_connect_network,
        error=None,
        admin=False,
        project=project,
        args=[node, 'boot-nic', net]
    ))


### Projects should be able to connect their nodes to public networks.
for net in ('stock_int_pub', 'stock_ext_pub'):
    for (project, node) in [
          ('runway', 'runway_node_0'),
          ('runway', 'runway_node_1'),
          ('manhattan', 'manhattan_node_0'),
          ('manhattan', 'manhattan_node_1'),
    ]:
        auth_call_params.append(dict(
            fn=api.node_connect_network,
            error=None,
            admin=False,
            project=project,
            args=[node, 'boot-nic', net]))

## Illegal cases

### Projects should not be able to connect their nodes to each other's
### networks.
for (node, net) in [
    ('runway_node_0', 'manhattan_pxe'),
    ('runway_node_1', 'manhattan_provider'),
]:
     auth_call_params.append(dict(
         fn=api.node_connect_network,
         error=ProjectMismatchError,
         admin=False,
         project='runway',
         args=[node, 'boot-nic', net]
     ))

auth_call_params += [
    ### Projects should not be able to attach each other's nodes to public networks.
    dict(fn=api.node_connect_network,
         error=AuthorizationError,
         admin=False,
         project='runway',
         args=['manhattan_node_0', 'boot-nic', 'stock_int_pub']),

    ### Projects should not be able to attach free nodes to networks.
    ### The same node about the exception as above applies.
    dict(fn=api.node_connect_network,
         error=ProjectMismatchError,
         admin=False,
         project='runway',
         args=['free_node_0', 'boot-nic', 'stock_int_pub']),

    # list_project_nodes

    ## Legal: admin lists a project's nodes.
    dict(fn=api.list_project_nodes,
         error=None,
         admin=True,
         project=None,
         args=['runway']),

    ## Legal: project lists its own nodes.
    dict(fn=api.list_project_nodes,
         error=None,
         admin=False,
         project='runway',
         args=['runway']),

    ## Illegal: project lists another project's nodes.
    dict(fn=api.list_project_nodes,
         error=AuthorizationError,
         admin=False,
         project='runway',
         args=['manhattan']),

    # show_node

    ## Legal: project shows a free node
    dict(fn=api.show_node,
         error=None,
         admin=False,
         project='runway',
         args=['free_node_0']),

    ## Legal: project shows its own node.
    dict(fn=api.show_node,
         error=None,
         admin=False,
         project='runway',
         args=['runway_node_0']),

    ## Illegal: project tries to show another project's node.
    dict(fn=api.show_node,
         error=AuthorizationError,
         admin=False,
         project='runway',
         args=['manhattan_node_0']),

    # project_connect_node: Project tries to connect someone else's node
    # to itself. The basic cases of connecting a free node are covered by
    # project_calls, below.
    dict(fn=api.project_connect_node,
         error=BlockedError,
         admin=False,
         project='runway',
         args=['runway', 'manhattan_node_0']),
]


@pytest.mark.parametrize('kwargs', auth_call_params)
def test_auth_call(kwargs):
    return auth_call_test(**kwargs)


# There are a whole bunch of api calls that just unconditionally require admin
# access. This is  a list of (function, args) pairs, each of which should
# succed as admin and fail as a regular project. The actual test functions for
# these are below.

admin_calls = [
    (api.node_register, ['new_node'], {'obm':{
              "type": MockObm.api_name,
	      "host": "ipmihost",
	      "user": "root",
	      "password": "tapeworm"}}),
#    (api.node_register, ['new_node', obm=obm, {}),
    (api.node_delete, ['no_nic_node'], {}),
    (api.node_register_nic, ['free_node_0', 'extra-nic', 'de:ad:be:ef:20:16'], {}),
    (api.node_delete_nic, ['free_node_0', 'boot-nic'], {}),
    (api.project_create, ['anvil-nextgen'], {}),
    (api.list_projects, [], {}),

    # node_power_*, on free nodes only. Nodes assigned to a project are
    # tested in project_calls, below.
    (api.node_power_cycle, ['free_node_0'], {}),
    (api.node_power_off, ['free_node_0'], {}),

    (api.project_delete, ['empty-project'], {}),

    (api.switch_register, ['new-switch', MockSwitch.api_name], {
        'hostname': 'oak-ridge',
        'username': 'alice',
        'password': 'changeme',
    }),
    (api.switch_delete, ['empty-switch'], {}),
    (api.switch_register_port, ['stock_switch_0', 'new_port'], {}),
    (api.switch_delete_port, ['stock_switch_0', 'free_port_0'], {}),
    (api.port_connect_nic, ['stock_switch_0', 'free_port_0',
                            'free_node_0', 'boot-nic'], {}),
    (api.port_detach_nic, ['stock_switch_0', 'free_node_0_port'], {}),
]


# Similarly, there are a large number of calls that require access to a
# particular project. This is a list of (function, args) pairs that should
# succeed as project 'runway', and fail as project 'manhattan'.
project_calls = [
    # node_power_*, on allocated nodes only. Free nodes are testsed in
    # admin_calls, above.
    (api.node_power_cycle, ['runway_node_0'], {}),
    (api.node_power_off, ['runway_node_0'], {}),

    (api.project_connect_node, ['runway', 'free_node_0'], {}),
    (api.project_detach_node, ['runway', 'runway_node_0'], {}),

    (api.headnode_create, ['new-headnode', 'runway', 'base-headnode'], {}),
    (api.headnode_delete, ['runway_headnode_off'], {}),
    (api.headnode_start, ['runway_headnode_off'], {}),
    (api.headnode_stop, ['runway_headnode_on'], {}),
    (api.headnode_create_hnic, ['runway_headnode_off', 'extra-hnic'], {}),
    (api.headnode_delete_hnic, ['runway_headnode_off', 'pxe'], {}),

    (api.headnode_connect_network, ['runway_headnode_off', 'pxe', 'stock_int_pub'], {}),
    (api.headnode_connect_network, ['runway_headnode_off', 'pxe', 'runway_pxe'], {}),
    (api.headnode_detach_network, ['runway_headnode_off', 'public'], {}),

    (api.list_project_headnodes, ['runway'], {}),
    (api.show_headnode, ['runway_headnode_on'], {}),
]


@pytest.mark.parametrize('fn,args,kwargs', admin_calls)
def test_admin_succeed(fn, args, kwargs):
    auth_call_test(fn=fn,
                   error=None,
                   admin=True,
                   project=None,
                   args=args,
                   kwargs=kwargs)


@pytest.mark.parametrize('fn,args,kwargs', admin_calls)
def test_admin_fail(fn, args, kwargs):
    auth_call_test(fn=fn,
                   error=AuthorizationError,
                   admin=False,
                   project='runway',
                   args=args,
                   kwargs=kwargs)


@pytest.mark.parametrize('fn,args,kwargs', project_calls)
def test_runway_succeed(fn, args, kwargs):
    auth_call_test(fn=fn,
                   error=None,
                   admin=False,
                   project='runway',
                   args=args,
                   kwargs=kwargs)


@pytest.mark.parametrize('fn,args,kwargs', project_calls)
def test_manhattan_fail(fn, args, kwargs):
    auth_call_test(fn=fn,
                   error=AuthorizationError,
                   admin=False,
                   project='manhattan',
                   args=args,
                   kwargs=kwargs)


class Test_node_detach_network(unittest.TestCase):

    def setUp(self):
        self.auth_backend = get_auth_backend()
        self.runway = local.db.query(model.Project).filter_by(label='runway').one()
        self.manhattan = local.db.query(model.Project).filter_by(label='manhattan').one()
        self.auth_backend.set_project(self.manhattan)
        api.node_connect_network('manhattan_node_0', 'boot-nic', 'stock_int_pub')
        deferred.apply_networking()

    def test_success(self):
        self.auth_backend.set_project(self.manhattan)
        api.node_detach_network('manhattan_node_0', 'boot-nic', 'stock_int_pub')

    def test_wrong_project(self):
        self.auth_backend.set_project(self.runway)
        with pytest.raises(AuthorizationError):
            api.node_detach_network('manhattan_node_0', 'boot-nic', 'stock_int_pub')
