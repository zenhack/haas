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

"""Load and query configuration data.

This module handles loading of the haas.cfg file, and querying the options
therein. the `cfg` attribute is an instance of `ConfigParser.RawConfigParser`.
Once `load` has been called, it will be ready to use.

Logging is initialized here.
"""

import ConfigParser, logging, os

# If not specified otherwise, this is the default config file read
DEFAULT_CONFIG_FILENAME='haas.cfg'

# cfg is used extensively by other parts of the program and represents a
# "public" interface
cfg = ConfigParser.RawConfigParser()

# Keep track of the loaded config file.
cfgFile = None

def reset():
    """
    Reset the cfg global. Return the previous config file. Used for unit
    tests.
    If you want to use this to reload the config file in normal operation,
    users of 'cfg' will need to use an accessor function instead of cfg
    directly since they could cache a stale copy.
    """
    global cfg, cfgFile
    cfg = ConfigParser.RawConfigParser()

    temp = cfgFile
    cfgFile = None
    return temp

import os.path
def load(filename=None, requireConfigFile=True):
    """
    Loads the configuration from exactly one file (or file-like object)
    indicated by (in order):
        1) The argument passed (most likely a command line argument or the
        testing framework)
        2) The environmental variable "HAAS_CONFIG"
        3) 'haas.cfg' in the current directory

    This must be called once at program startup; no configuration options will
    be available until then. Once called, further calls to load() will silently
    be ignored.

    If the configuration file is not available, throw an exception unless
    requireConfigFile was set to False. We generally (for server configs) need
    a config file to function. For CLI clients, it's foreseeable that someone
    might want to get help without having a full configuration yet.
    """

    global cfgFile
    if cfgFile != None:
        return

    if filename == None:
        if 'HAAS_CONFIG' in os.environ:
            # Look in environmental variable
            filename = os.environ['HAAS_CONFIG']
        else:
            # Use the default
            filename = DEFAULT_CONFIG_FILENAME

    loadedCfg = cfg.read(filename)

def configure_logging():
    """Configure the logger according to the settings in the config file.

    This must be called *after* the config is loaded.
    """
    if cfg.has_option('general', 'log_level'):
        LOG_SET = ["CRITICAL", "DEBUG", "ERROR", "FATAL", "INFO", "WARN",
                   "WARNING"]
        log_level = cfg.get('general', 'log_level').upper()
        if log_level in LOG_SET:
            # Set to mnemonic log level
            logging.basicConfig(level=getattr(logging, log_level))
        else:
            # Set to 'warning', and warn that the config is bad
            logging.basicConfig(level=logging.WARNING)
            logging.getLogger(__name__).warning(
                "Invalid debugging level %s defaulted to WARNING"% log_level)
    else:
        # Default to 'warning'
        logging.basicConfig(level=logging.WARNING)

    # Keep logs and raise error if unable to access the config file
    if len(loadedCfg) == 0:
        logging.error("Unable to load config file %s", str(filename))
        if requireConfigFile:
            import api
            raise api.ServerError("Unable to load config file")
    else:
        logging.info("Successfully parsed config file(s) %s", loadedCfg)
        cfgFile = filename
