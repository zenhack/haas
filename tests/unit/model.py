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

"""Functional tests for model.py"""

# Some Notes:
#
# * We don't really have any agreed-upon requirements about what __repr__
# should print, but I'm fairly certain I hit an argument mistmatch at
# some point, which is definitely wrong. The test_repr methods are there just
# to make sure it isn't throwing an exception.

from haas.model import *
from haas import config
from haas.ext.obm.ipmi import Ipmi


from haas.test_common import fresh_database, config_testsuite, ModelTest
import pytest

@pytest.fixture
def configure():
    config_testsuite()
    config.load_extensions()

@pytest.fixture
def db(request):
    return fresh_database(request)

pytestmark = pytest.mark.usefixtures('configure', 'db')


class TestNic(ModelTest):

    def sample_obj(self):
        return Nic(Node(label='node-99', obm=Ipmi(type="http://schema.massopencloud.org/haas/v0/obm/ipmi",
                  host= "ipmihost", user= "root", password= "tapeworm")), 'ipmi', '00:11:22:33:44:55')


class TestNode(ModelTest):

    def sample_obj(self):
        return Nic(Node(label='node-99', obm=Ipmi(type="http://schema.massopencloud.org/haas/v0/obm/ipmi",
                  host= "ipmihost", user= "root", password= "tapeworm")), 'ipmi', '00:11:22:33:44:55')

class TestProject(ModelTest):

    def sample_obj(self):
        return Project('manhattan')


class TestHeadnode(ModelTest):

    def sample_obj(self):
        return Headnode(Project('anvil-nextgen'), 'hn-example', 'base-headnode')


class TestHnic(ModelTest):

    def sample_obj(self):
        return Hnic(Headnode(Project('anvil-nextgen'),
            'hn-0', 'base-headnode'), 'storage')


class TestNetwork(ModelTest):

    def sample_obj(self):
        pj = Project('anvil-nextgen')
        return Network(pj, pj, True, '102', 'hammernet')

class TestNetworkingAction(ModelTest):

    def sample_obj(self):
        nic = Nic(Node(label='node-99', obm=Ipmi(type="http://schema.massopencloud.org/haas/v0/obm/ipmi",
                  host= "ipmihost", user= "root", password= "tapeworm")), 'ipmi', '00:11:22:33:44:55')

        project = Project('anvil-nextgen')
        network = Network(project, project, True, '102', 'hammernet')
        return NetworkingAction(nic=nic,
                                new_network=network,
                                channel='null')
