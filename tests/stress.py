
from haas.test_common import config_testsuite, fresh_database
from haas import api, config, server, rest

import json
import pytest


@pytest.fixture
def configure():
    config_testsuite()
    config.load_extensions()


@pytest.fixture
def db(request):
    return fresh_database(request)


@pytest.fixture
def server_init():
    server.register_drivers()
    server.validate_state()


pytestmark = pytest.mark.usefixtures('configure',
                                     'db',
                                     'server_init')


def test_many_http_queries():
    """Put a few objects in the db, then bombard the api with queries.

    This is intended to shake out problems like the resource leak discussed
    in issue #454.
    """
    with rest.app.test_request_context():
        with rest.DBContext():
            rest.init_auth()
            api.node_register('node-99', obm={
                    "type": "http://schema.massopencloud.org/haas/v0/obm/ipmi",
                    "host": "ipmihost",
                    "user": "root",
                    "password": "tapeworm"})
            api.node_register('node-98', obm={
                    "type": "http://schema.massopencloud.org/haas/v0/obm/ipmi",
                    "host": "ipmihost",
                    "user": "root",
                    "password": "tapeworm"})
            api.node_register('node-97', obm={
                    "type": "http://schema.massopencloud.org/haas/v0/obm/ipmi",
                    "host": "ipmihost",
                    "user": "root",
                    "password": "tapeworm"})
            api.node_register_nic('node-99', 'eth0', 'DE:AD:BE:EF:20:14')
            api.node_register_nic('node-98', 'eth0', 'DE:AD:BE:EF:20:15')
            api.node_register_nic('node-97', 'eth0', 'DE:AD:BE:EF:20:16')
            api.project_create('anvil-nextgen')
            api.project_create('anvil-legacy')
            api.project_connect_node('anvil-nextgen', 'node-99')
            api.project_connect_node('anvil-legacy', 'node-98')

    client = rest.app.test_client()

    def _show_nodes(path):
        """Helper for the loop below.

        This does a GET on path, which must return a json list of names of
        nodes. It will then query the state of each node. If any request does
        not return 200 or has a body which is not valid json, the test will
        fail.
        """
        resp = client.get(path)
        assert resp.status_code == 200
        for node in json.loads(resp.get_data()):
            resp = client.get('/node/%s' % node)
            assert resp.status_code == 200
            # At least make sure the body parses:
            json.loads(resp.get_data())

    for i in range(100):
        _show_nodes('/free_nodes')
        resp = client.get('/projects')
        assert resp.status_code == 200
        for project in json.loads(resp.get_data()):
            _show_nodes('/project/%s/nodes' % project)
