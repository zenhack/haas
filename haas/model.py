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
"""core database objects for the HaaS"""

from sqlalchemy import *
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import relationship, sessionmaker,backref
from passlib.hash import sha512_crypt
from subprocess import call, check_call
import subprocess
from haas.config import cfg
from haas.dev_support import no_dry_run
import importlib
import uuid
import xml.etree.ElementTree
import logging

Base=declarative_base()
Session = sessionmaker()

# A joining table for users and groups, which have a many to many relationship:
user_groups = Table('user_groups', Base.metadata,
                    Column('user_id', Integer, ForeignKey('user.id')),
                    Column('group_id', Integer, ForeignKey('group.id')))


def init_db(create=False, uri=None):
    """Start up the DB connection.

    If `create` is True, this will generate the schema for the database.

    `uri` is the uri to use for the databse. If it is None, the uri from the
    config file will be used.
    """

    if uri == None:
        uri = cfg.get('database', 'uri')

    # We have to import this prior to doing create_all, so that any tables
    # defined by the driver will make it into the schema.
    driver_name = cfg.get('general', 'driver')
    driver = importlib.import_module('haas.drivers.' + driver_name)

    engine = create_engine(uri)
    if create:
        Base.metadata.create_all(engine)
    Session.configure(bind=engine)

    driver.init_db(create=create)


class Model(Base):
    """All of our database models are descendants of this class.

    Its main purpose is to reduce boilerplate by doing things such as
    auto-generating table names.

    It also declares two columns which are common to every model:

        * id, which is an arbitrary integer primary key.
        * label, which is a symbolic name for the object.
    """
    __abstract__ = True
    id = Column(Integer, primary_key=True, nullable=False)
    label = Column(String, nullable=False)

    def __repr__(self):
        return '%s<%r>' % (self.__class__.__name__, self.label)

    @declared_attr
    def __tablename__(cls):
        """Automatically generate the table name."""
        return cls.__name__.lower()


class Nic(Model):
    """a nic belonging to a Node"""

    # The Node to which the nic belongs:
    owner_id   = Column(Integer,ForeignKey('node.id'), nullable=False)
    owner     = relationship("Node",backref=backref('nics'))

    # The mac address of the nic:
    mac_addr  = Column(String)

    # The switch port to which the nic is attached:
    port_id   = Column(Integer,ForeignKey('port.id'))
    port      = relationship("Port",backref=backref('nic',uselist=False))

    # The Network to which the nic is attached:
    network_id = Column(Integer, ForeignKey('network.id'))
    network   = relationship("Network", backref=backref('nics'))

    def __init__(self, node, label, mac_addr):
        self.owner     = node
        self.label     = label
        self.mac_addr  = mac_addr


class Node(Model):
    """a (physical) machine"""

    # The project to which this node is allocated. If the project is null, the
    # node is unallocated:
    project_id    = Column(Integer,ForeignKey('project.id'))
    project       = relationship("Project",backref=backref('nodes'))

    # ipmi connection information:
    ipmi_host = Column(String, nullable=False)
    ipmi_user = Column(String, nullable=False)
    ipmi_pass = Column(String, nullable=False)

    def __init__(self, label, ipmi_host, ipmi_user, ipmi_pass):
        """Register the given node.

        ipmi_* must be supplied to allow the HaaS to do things like reboot
        the node.

        The node is initially registered with no nics; see the Nic class.
        """
        self.label = label
        self.ipmi_host = ipmi_host
        self.ipmi_user = ipmi_user
        self.ipmi_pass = ipmi_pass

    def _ipmitool(self, args):
        """Invoke ipmitool with the right host/pass etc. for this node.

        `args` - A list of any additional arguments to pass to ipmitool.

        Returns the exit status of ipmitool.
        """
        status = call(['ipmitool',
            '-U', self.ipmi_user,
            '-P', self.ipmi_pass,
            '-H', self.ipmi_host] + args)
        if status != 0:
            logger = logging.getLogger(__name__)
            logger.info('Nonzero exit status from ipmitool, args = %r', args)
        return status


    def power_cycle(self):
        """Reboot the node via ipmi.

        Returns True if successful, False otherwise.
        """
        self._ipmitool(['chassis', 'bootdev', 'pxe'])
        status = self._ipmitool(['chassis', 'power', 'cycle'])
        if status != 0:
            # power cycle will fail if the machine isn't running, so let's
            # just turn it on in that case. This way we can save power by
            # turning things off without breaking the HaaS.
            status = self._ipmitool(['chassis', 'power', 'on'])
        return status == 0


class Project(Model):
    """a collection of resources

    A project may contain allocated nodes, networks, and headnodes.
    Originally, the primary functionality offered by projects was to
    stage changes to be made to a project, and then apply them all at
    once. The HaaS has drifted from this somewhat; in particular
    changes to headnodes are generally immediate.
    """

    # A project is "dirty" if it has unapplied changes:
    dirty = Column(Boolean, nullable=False)

    # The group to which the project belongs:
    group_id = Column(Integer, ForeignKey('group.id'), nullable=False)
    group = relationship("Group", backref=backref("projects"))

    def __init__(self, group, label):
        """Create a project with the given label belonging to `group`."""
        self.group = group
        self.label = label
        self.dirty = False


class Network(Model):
    """A link-layer network."""

    # The project to which the network belongs:
    project_id    = Column(String,ForeignKey('project.id'), nullable=False)
    project = relationship("Project",backref=backref('networks'))

    # An identifier meaningful to the networking driver:
    network_id    = Column(String, nullable=False)

    def __init__(self, project, network_id, label):
        """Create a network.

        The network will belong to `project`, and have a symbolic name of
        `label`. `network_id`, as expected, is the identifier meaningful to
        the driver.
        """
        self.network_id = network_id
        self.project = project
        self.label = label



class Port(Model):
    """a port on a switch

    The port's label is an identifier that is meaningful only to the
    corresponding switch's driver.
    """

    # The switch to which the port belongs:
    owner_id     = Column(String,ForeignKey('switch.id'), nullable=False)
    owner        = relationship("Switch",backref=backref('ports'))

    def __init__(self, switch, label):
        """Register a port on the given switch."""
        self.owner = switch
        self.label   = label



class Switch(Model):
    driver = Column(String)

    def __init__(self, label, driver):
        self.label = label
        self.driver = driver


class User(Model):
    """A user of the HaaS.

    Right now we're not doing authentication, so this isn't really used. In
    theory, a user must autheticate, and their membership within groups
    determines what they are authorized to do.
    """

    # The user's salted & hashed password. We currently use sha512 as the
    # hasing algorithm:
    hashed_password    = Column(String)

    # The groups of which the user is a member.
    groups      = relationship('Group', secondary = user_groups, backref = 'users')

    def __init__(self, label, password):
        """Create a user `label` with the specified (plaintext) password."""
        self.label = label
        self.set_password(password)

    def verify_password(self, password):
        """Return whether `password` is the user's (plaintext) password."""
        return sha512_crypt.verify(password, self.hashed_password)

    def set_password(self, password):
        """Set the user's password to `password` (which must be plaintext)."""
        self.hashed_password = sha512_crypt.encrypt(password)


class Group(Model):
    """a group of users

    The main function of groups is to act as the owner of projects.
    This is somewhat clumsy, and there are changes on the roadmap
    that will likely result in the elimination of groups.
    """

    def __init__(self, label):
        """Create a group with the specified label."""
        self.label = label


class Headnode(Model):
    """A virtual machine used to administer a project."""

    # The project to which this Headnode belongs:
    project_id = Column(String, ForeignKey('project.id'), nullable=False)
    project = relationship("Project", backref=backref('headnode', uselist=False))

    # True iff there are unapplied changes to the Headnode:
    dirty = Column(Boolean, nullable=False)

    # We need a guaranteed unique name to generate the libvirt machine name;
    # The name is therefore a function of a uuid:
    uuid = Column(String, nullable=False, unique=True)

    def __init__(self, project, label):
        """Create a headnode belonging to `project` with the given label."""
        self.project = project
        self.label = label
        self.dirty = True
        self.uuid = str(uuid.uuid1())

    @no_dry_run
    def create(self):
        """Creates the vm within libvirt, by cloning the base image.

        The vm is not started at this time.
        """
        # Before doing anything else, make sure the VM doesn't already
        # exist. This gives us the nice property that create will not fail
        # because of state left behind by previous failures (much like
        # applying a project):
        call(['virsh', 'undefine', self._vmname(), '--remove-all-storage'])
        # The --remove-all-storage flag above *should* take care of this,
        # but doesn't seem to on our development setup. XXX.
        call(['rm', '-f', '/var/lib/libvirt/images/%s.img' % self._vmname()])

        check_call(['virt-clone', '-o', 'base-headnode', '-n', self._vmname(), '--auto-clone'])
        for hnic in self.hnics:
            hnic.create()

    def delete(self):
        """Delete the vm, including associated storage"""
        # XXX: This doesn't actually work. I (ian) copied this from the
        # headnode  module so I could finally delete it, but I haven't
        # actually made the  slight changes needed to get it to work
        # again (variable renames, mostly).
        cmd(['virsh', 'undefine', self.name, '--remove-all-storage'])

    @no_dry_run
    def start(self):
        """Powers on the vm, which must have been previously created.

        Once the headnode has been started once it is "frozen," and no changes
        may be made to it, other than starting, stopping or deleting it.
        """
        check_call(['virsh', 'start', self._vmname()])
        self.dirty = False

    @no_dry_run
    def stop(self):
        """Stop the vm.

        This does a hard poweroff; the OS is not given a chance to react.
        """
        check_call(['virsh', 'destroy', self._vmname()])

    def _vmname(self):
        """Returns the name (as recognized by libvirt) of this vm."""
        return 'headnode-%s' % self.uuid


    # This function returns a meaningful value, but also uses actual hardware.
    # It has no_dry_run because the unit test for 'show_headnode' will call
    # it.  None is a fine return value there, because it will just put it into
    # a JSON object.
    @no_dry_run
    def get_vncport(self):
        """Return the port that VNC is listening on, as an int.

        If the VM is powered off, the return value may be None -- this is
        dependant on the configuration of libvirt. A powered on VM will always
        have a vnc port.

        If the VM has not been created yet (and is therefore dirty) the return
        value will be None.
        """
        if self.dirty:
            return None

        p = subprocess.Popen(['virsh', 'dumpxml', self._vmname()],
                             stdout=subprocess.PIPE)
        xmldump, _ = p.communicate()
        root = xml.etree.ElementTree.fromstring(xmldump)
        port = root.findall("./devices/graphics")[0].get('port')
        if port == -1:
            # No port allocated (yet)
            return None
        else:
            return port
        # No VNC service found, so no port available
        return None


class Hnic(Model):
    """a network interface for a Headnode"""

    # The Headnode to which this Hnic belongs:
    owner_id    = Column(Integer, ForeignKey('headnode.id'), nullable=False)
    owner       = relationship("Headnode", backref = backref('hnics'))

    # The mac address of this Hnic. XXX: This isn't actually used for anything
    # currently; we should either remove it or make it do something.
    # intuitively, it should actually define the mac address in the VM, right
    # now it just serves to confuse users.
    mac_addr    = Column(String)

    # The network to which this Hnic is attached.
    network_id  = Column(Integer, ForeignKey('network.id'))
    network     = relationship("Network", backref=backref('hnics'))

    def __init__(self, headnode, label, mac_addr):
        """Create an Hnic attached to the given headnode.

        The Hnic will have the given label and mac_addr.
        Note that the mac_addr field is not currently respected; it has no
        effect on the Headnode.
        """
        self.owner    = headnode
        self.label    = label
        self.mac_addr = mac_addr

    @no_dry_run
    def create(self):
        """Create the hnic within livbirt.

        XXX: This is a noop if the Hnic isn't connected to a network. This
        means that the headnode won't have a corresponding nic, even a
        disconnected one.
        """
        if not self.network:
            # It is non-trivial to make a NIC not connected to a network, so
            # do nothing at all instead.
            return
        vlan_no = str(self.network.network_id)
        bridge = 'br-vlan%s' % vlan_no
        check_call(['virsh', 'attach-interface', self.owner._vmname(), 'bridge', bridge, '--config'])
