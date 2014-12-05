# Copyright 2013-2014 Massachusetts Open Cloud Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the
# License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS
# IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied.  See the License for the specific language
# governing permissions and limitations under the License.

from functools import wraps
from haas.model import *
# XXX: This function has an underscore so that we don't import it elsewhere.
# But... we need it here.  Oops.
from haas.model import _on_virt_uri
from haas.config import cfg
from haas import api
import json
import unittest

def network_create_simple(network, project):
    """Create a simple project-owned network.

    This is a shorthand for the network_create API call, that defaults
    parameters to the most common case---namely, that the network is owned by
    a project, has access only by that project, and uses an allocated
    underlying net_id.  Note that this is the only valid set of parameters for
    a network that belongs to a project.

    The test-suite uses this extensively, for tests that don't care about more
    complicated features of networks.
    """
    api.network_create(network, project, project, "")

def newDB():
    """Configures and returns an in-memory DB connection"""
    init_db(create=True,uri="sqlite:///:memory:")
    return Session()

def releaseDB(db):
    """Do we need to do anything here to release resources?"""
    pass


def clear_config():
    """Removes all sections/options from haas.config.cfg."""
    for section in cfg.sections():
        cfg.remove_section(section)


def set_config(config_dict):
    """Populates haas.config.cfg based on the contents of ``config_dict``.

    ``config_dict`` should be a dictionary of the form:

        {
            "headnode": {
                "libvirt_uri": "qemu://...",
                ...
            },
            "devel": {
                "dry_run": True,
            },
        }

    i.e. a dictionary whose keys/values corresponding to section names/sections
    of the config, with each "section" being a dictionary from option names to
    values.

    The config will *not* be cleared first -- ``clear_config`` should be called
    explicitly.
    """
    for section in config_dict.keys():
        cfg.add_section(section)

        for option in config_dict[section].keys():
            cfg.set(section, option, config_dict[section][option])


class DBOnlyTest(unittest.TestCase):
    """A test case which only interacts with the database.

    Tests will run in dry-run mode, with the null driver, a fresh database,
    and the list of valid base images:

        base-headnode, img1, img2, img3, img4
    """

    def setUp(self):
        clear_config()
        set_config({
            'general': {'driver': 'null'},
            'devel': {'dry_run': True},
            'headnode': {'base_imgs': 'base-headnode, img1, img2, img3, img4'},
        })

        self.db = newDB()

    def tearDown(self):
        releaseDB(self.db)


class DeploymentTest(unittest.TestCase):
    """A test case intended to run against a real swtich/libvirt.

    The behavior of deployment tests is configured in ``deployment.cfg``, which
    must exist in the current directory when the tests are run.

    The database will be populated with available nodes from
    ``site-layout.json.``
    """

    def setUp(self):
        # Use the deployment config for these tests.  Setup such as the switch
        # IP address and password must be in this file, as well as the allowed
        # VLAN range.
        # XXX: Currently, the deployment tests only support the Dell driver.
        clear_config()
        cfg.read('deployment.cfg')
        self.db = newDB()
        self.allocate_nodes()

    def tearDown(self):
        releaseDB(self.db)
        # We need to clear out the headnode VMs left over from the test.
        # There's a bug in some versions of libvirt which causes
        # 'virsh undefine' to fail if called too quickly.
        for hn in self.db.query(Headnode):
            # XXX: Our current version of libvirt has a bug that causes this
            # command to hang for a minute and throw an error before
            # completing successfully.  For this reason, we are ignoring any
            # errors thrown by 'virsh undefine'. This should be changed once
            # we start using a version of libvirt that has fixed this bug.
            call(_on_virt_uri(['virsh', 'undefine', hn._vmname(),
                               '--remove-all-storage']))

    def allocate_nodes(self):
        layout_json_data = open('site-layout.json')
        layout = json.load(layout_json_data)
        layout_json_data.close()

        netmap = {}
        for node in layout['nodes']:
            api.node_register(node['name'], node['ipmi']['host'],
                node['ipmi']['user'], node['ipmi']['pass'])
            for nic in node['nics']:
                api.node_register_nic(node['name'], nic['name'], nic['mac'])
                api.port_register(nic['port'])
                api.port_connect_nic(nic['port'], node['name'], nic['name'])
                netmap[nic['port']] = None

        # Now ensure that all of these ports are turned off
        driver_name = cfg.get('general', 'driver')
        driver = importlib.import_module('haas.drivers.' + driver_name)
        driver.apply_networking(netmap)
