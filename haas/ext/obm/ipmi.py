# Copyright 2015-2016 Massachusetts Open Cloud Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS
# IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language
# governing permissions and limitations under the License.

"""IPMI driver for implementing out of band management. """

from sqlalchemy import Column, String, Integer, ForeignKey
import schema
import subprocess

from haas.model import Obm
from haas.errors import OBMError
from haas.dev_support import no_dry_run
from subprocess import call, check_call, Popen, PIPE
import os

class Ipmi(Obm):
    id = Column(Integer, ForeignKey('obm.id'), primary_key=True)
    host = Column(String, nullable=False)
    user = Column(String, nullable=False)
    password = Column(String, nullable=False)

    api_name = 'http://schema.massopencloud.org/haas/v0/obm/ipmi'

    __mapper_args__ = {
        'polymorphic_identity': api_name,
        }

    @staticmethod
    def validate(kwargs):
        schema.Schema({
            'type': Ipmi.api_name,
            'host': basestring,
            'user': basestring,
            'password': basestring,
            }).validate(kwargs)

    def _ipmitool(self, args):
        """Invoke ipmitool with the right host/pass etc. for this node.

        `args`- A list of any additional arguments to pass to ipmitool.
        Returns the exit status of ipmitool.

        Note: Includes the ``-I lanplus`` flag, available only in IPMI v2+.
        This is needed for machines which do not accept the older version.
        """
        status = call(['ipmitool',
            '-I', 'lanplus', #see docstring above
            '-U', self.user,
            '-P', self.password,
            '-H', self.host]  + args)

        if status != 0:
            logger = logging.getLogger(__name__)
            logger.info('Nonzero exit status form ipmitool, args = %r', args)
        return status

    @no_dry_run
    def power_cycle(self):
        self._ipmitool(['chassis', 'bootdev', 'pxe'])
        if self._ipmitool(['chassis', 'power', 'cycle']) == 0:
            return
        if self._ipmitool(['chassis', 'power', 'on']) == 0:
            # power cycle will fail if the machine is not running.
            # To avoid such a situation, just turn it on anyways.
            # Doing this saves power by turning things off without 
            # Without breaking the HaaS.
            return
        # If it is still does not work, then it is a real error:
        raise OBMError('Could not power cycle node %s' % self.node.label)

    @no_dry_run
    def power_off(self):
        if self._ipmitool(['chassis', 'power', 'off']) != 0:
            raise OBMError('Could not power off node %s', self.label)


    @no_dry_run
    def start_console(self):
        """Starts logging the IPMI console."""

        # stdin and stderr are redirected to a PIPE that is never read in order
        # to prevent stdout from becoming garbled.  This happens because
        # ipmitool sets shell settings to behave like a tty when communicateing
        # over Serial over Lan
        Popen(
            ['ipmitool',
            '-H', self.host,
            '-U', self.user,
            '-P', self.password,
            '-I', 'lanplus',
            'sol', 'activate'],
            stdin=PIPE,
            stdout=open(self.get_console_log_filename(), 'a'),
            stderr=PIPE)

    # stdin, stdout, and stderr are redirected to a pipe that is never read
    # because we are not interested in the ouput of this command.
    @no_dry_run
    def stop_console(self):
        call(['pkill', '-f', 'ipmitool -H %s' %self.host])
        proc = Popen(
            ['ipmitool',
            '-H', self.host,
            '-U', self.user,
            '-P', self.password,
            '-I', 'lanplus',
            'sol', 'deactivate'],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE)
        proc.wait()

    def delete_console(self):
        if os.path.isfile(self.get_console_log_filename()):
            os.remove(self.get_console_log_filename())

    def get_console(self):
        if not os.path.isfile(self.get_console_log_filename()):
            return None
        with open(self.get_console_log_filename(), 'r') as log:
            return "".join(i for i in log.read() if ord(i)<128)

    def get_console_log_filename(self):
        return '/var/run/haas_console_logs/%s.log' % self.host
