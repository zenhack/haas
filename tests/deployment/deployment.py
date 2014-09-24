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

"""Deployment Unit Tests - These tests are intended for our
internal setup only and will most likely not work on
other HaaS configurations."""

from haas import api, model
from haas.drivers.driver_tools.vlan import get_vlan_list
from haas.test_common import *
import importlib
import json
import pexpect
import pytest
import re

class TestHeadNode:

    @deployment_test
    @headnode_cleanup
    def test_headnode_start(self, db):
        api.group_create('acme-code')
        api.project_create('anvil-nextgen', 'acme-code')
        api.network_create('spider-web', 'anvil-nextgen')
        api.headnode_create('hn-0', 'anvil-nextgen')
        api.headnode_create_hnic('hn-0', 'hnic-0', 'de:ad:be:ef:20:14')
        api.headnode_connect_network('hn-0', 'hnic-0', 'spider-web')
        assert json.loads(api.show_headnode('hn-0'))['vncport'] is None
        api.headnode_start('hn-0')
        assert json.loads(api.show_headnode('hn-0'))['vncport'] is not None


class TestNetwork:

    @deployment_test
    @headnode_cleanup
    def test_isolated_networks(self, db):

        driver_name = cfg.get('general', 'driver')
        driver = importlib.import_module('haas.drivers.' + driver_name)

        def get_switch_vlans():
            return driver.get_switch_vlans(get_vlan_list())

        def get_network(port, vlan_cfg):
            """Returns all interfaces on the same network as a given port"""
            for vlan in vlan_cfg:
                if port in vlan_cfg[vlan]:
                    return vlan_cfg[vlan]
            return []
        
        def create_networks(): 
            # Add up to 4 available nodes with nics to the project
            free_nodes = db.query(model.Node).filter_by(project_id=None).all()
            nodes = []
            for node in free_nodes:
                if len(node.nics) > 0:
                    api.project_connect_node('anvil-nextgen', node.label)
                    nodes.append(node)
                    if len(nodes) >= 4:
                        break
    
            # If there are not enough nodes with nics, raise an exception 
            if len(nodes) < 4:
                raise api.AllocationError(('At least 4 nodes with at least ' +
                    '1 NIC are required for this test. Only %d node(s) were ' +
                    'provided.') % len(nodes))

            # Create two networks
            api.network_create('net-0', 'anvil-nextgen')
            api.network_create('net-1', 'anvil-nextgen')
 
            # Convert each node to a dict for ease of access
            nodes = [{'label': n.label,
                      'nic': n.nics[0].label,
                      'port': n.nics[0].port.label}
                     for n in nodes]

            # Assert that n0 and n1 are not on any network
            vlan_cfgs = get_switch_vlans()

            assert get_network(nodes[0]['port'], vlan_cfgs) == []
            assert get_network(nodes[1]['port'], vlan_cfgs) == []

            # Connect n0 and n1 to net-0 and net-1 respectively
            api.node_connect_network(nodes[0]['label'], nodes[0]['nic'], 'net-0')
            api.node_connect_network(nodes[1]['label'], nodes[1]['nic'], 'net-1')
            
            # Apply current configuration
            api.project_apply('anvil-nextgen')
    
            # Assert that n0 and n1 are on isolated networks
            vlan_cfgs = get_switch_vlans()
            assert get_network(nodes[0]['port'], vlan_cfgs) == [nodes[0]['port']]
            assert get_network(nodes[1]['port'], vlan_cfgs) == [nodes[1]['port']]
    
            # Add n2 and n3 to the same networks as n0 and n1 respectively
            api.node_connect_network(nodes[2]['label'], nodes[2]['nic'], 'net-0')
            api.node_connect_network(nodes[3]['label'], nodes[3]['nic'], 'net-1')
    
            # Apply current configuration
            api.project_apply('anvil-nextgen')
    
            # Assert that n2 and n3 have been added to n0 and n1's networks
            # respectively
            vlan_cfgs = get_switch_vlans() 
            assert get_network(nodes[0]['port'], vlan_cfgs) == [nodes[0]['port'], nodes[2]['port']]
            assert get_network(nodes[1]['port'], vlan_cfgs) == [nodes[1]['port'], nodes[3]['port']]


        def delete_networks():
            # Query the DB for nodes on this project 
            project = api._must_find(db, model.Project, 'anvil-nextgen')
            nodes = project.nodes

            # Remove all nodes from their networks
            for node in nodes:
                if node.nics[0].network is not None:
                    api.node_detach_network(node.label, node.nics[0].label)
    
            # Apply current configuration
            api.project_apply('anvil-nextgen')
    
            # Assert that none of the nodes are on any network
            vlan_cfgs = get_switch_vlans()
            for node in nodes:
                assert get_network(node.nics[0].label, vlan_cfgs) == []
    
            # Delete the networks
            api.network_delete('net-0')
            api.network_delete('net-1')
            
            # Apply current configuration
            api.project_apply('anvil-nextgen')

        
        # Create group and project
        api.group_create('acme-code')
        api.project_create('anvil-nextgen', 'acme-code')
        
        create_networks()
        delete_networks()

    @deployment_test
    @headnode_cleanup
    def test_network_allocation(self, db):
        try:
            api.group_create('acme-code')
            api.project_create('anvil-nextgen', 'acme-code')
            
            vlans = get_vlan_list()
            num_vlans = len(vlans)

            for network in range(0,num_vlans):
                api.network_create('net-%d' % network, 'anvil-nextgen')
     
            # Ensure that error is raised if too many networks allocated
            with pytest.raises(api.AllocationError):
                api.network_create('net-%d' % num_vlans, 'anvil-nextgen')
     
            # Ensure that project_apply doesn't affect network allocation
            api.project_apply('anvil-nextgen')
            with pytest.raises(api.AllocationError):
                api.network_create('net-%d' % num_vlans, 'anvil-nextgen')
     
            # Ensure that network_delete doesn't affect network allocation
            api.network_delete('net-%d' % (num_vlans-1))
            api.network_create('net-%d' % (num_vlans-1), 'anvil-nextgen')
            with pytest.raises(api.AllocationError):
                api.network_create('net-%d' % num_vlans, 'anvil-nextgen')
     
            # Ensure that network_delete+project_apply doesn't affect network
            # allocation
            api.network_delete('net-%d' % (num_vlans-1))
            api.project_apply('anvil-nextgen')
            api.network_create('net-%d' % (num_vlans-1), 'anvil-nextgen')
            with pytest.raises(api.AllocationError):
                api.network_create('net-%d' % num_vlans, 'anvil-nextgen')
    
            api.network_delete('net-%d' % (num_vlans-1))
            api.network_create('net-%d' % (num_vlans-1), 'anvil-nextgen')
            api.project_apply('anvil-nextgen')
            with pytest.raises(api.AllocationError):
                api.network_create('net-%d' % num_vlans, 'anvil-nextgen')

        finally:
            # Clean up networks
            for network in range(0,num_vlans):
                api.network_delete('net-%d' % network)
            api.project_apply('anvil-nextgen')
