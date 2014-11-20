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

"""Unit tests for config.py"""

from haas import config, api

import pytest
import os, os.path, tempfile

def newConfigEnv(haasCfg):
    """
    Set a new HAAS_CONFIG env variable, returning the previous value.
    Returns None if there was no previous value. If called with 'None', will
    delete the HAAS_CONFIG
    """
    prev = os.environ.get('HAAS_CONFIG')

    if haasCfg == None:
        if prev != None:
            del os.environ['HAAS_CONFIG']
    else:
        os.environ['HAAS_CONFIG'] = haasCfg

    return prev

class TestConfig:
    """
    Tests for haas.config.
    NOTE: It's important for tests to restore the previous config file state
    after running so that other programs are not impacted.
    """

    def test_missing(self):
        # Ensure config file is not set
        env = newConfigEnv(None)

        prevCfg = config.reset()
        with pytest.raises(api.ServerError):
            config.load('/dev/does/not/exist')

        newConfigEnv(env)
        if prevCfg != None:
            config.load(prevCfg)

    def test_load_order(self):
        """
        Ensure load() honors the order documented, which is to load from:
        1) arg, 2) env and 3) ./haas.cfg
        """
        prevCfg = config.reset()
        prevEnv = newConfigEnv(None)

        arg = tempfile.NamedTemporaryFile()
        env = tempfile.NamedTemporaryFile()
        haasDir = tempfile.mkdtemp()
        haasCfg = open(os.path.join(haasDir, 'haas.cfg'), "w")

        arg.write('[general]\ncustom = arg\n')
        arg.flush()
        env.write('[general]\ncustom = env\n')
        env.flush()
        haasCfg.write('[general]\ncustom = haas.cfg\n')
        haasCfg.close()

        # Change to the new dir/use the haas.cfg in there.
        curDir = os.getcwd()
        os.chdir(haasDir)
        config.load()

        # Test that we're using haas.cfg
        assert config.cfg.get('general', 'custom') == "haas.cfg"

        newConfigEnv(env.name)
        config.reset()
        config.load()
        # Test that we're using the HAAS_CONFIG env
        assert config.cfg.get('general', 'custom') == "env"

        # Test priority of passed-in config
        config.reset()
        config.load(arg.name)
        assert config.cfg.get('general', 'custom') == "arg"

        # Try to change it back. load() should silently ignore this
        config.load(env.name)
        assert config.cfg.get('general', 'custom') == "arg"

        # Cleanup
        os.remove(haasCfg.name)
        os.rmdir(haasDir)
        env.close()
        arg.close()
        config.reset()
        config.load(prevCfg, requireConfigFile=False)
        newConfigEnv(prevEnv)


