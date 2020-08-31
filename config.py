import os
import logging
import json
from enum import Enum
import sys

from yurt.exceptions import ConfigWriteException, ConfigReadException

applicationName = "yurt"
applianceVersion = "0.1.4"


class ConfigName(Enum):
    vmName = 1
    hostOnlyInterface = 2
    hostOnlyInterfaceIPAddress = 3
    hostOnlyInterfaceNetworkMask = 4
    hostSSHPort = 5
    hostLXDPort = 6


YURT_ENV = os.environ.get("YURT_ENV")

if YURT_ENV == "development":
    configFileName = "testConfig.json"
    vmInstallDir = "vm-test"
else:
    configFileName = "config.json"
    vmInstallDir = "vm"

try:
    configDir = os.path.join(os.environ['HOME'], f".{applicationName}")
except KeyError:
    logging.error("HOME environment variable is not set")
    sys.exit(1)

configFile = os.path.join(configDir, configFileName)
vmInstallDir = os.path.join(configDir, vmInstallDir)

# Resource Paths ###########################################################
_srcHome = os.path.dirname(__file__)
provisionDir = os.path.join(_srcHome, "provision")
artifactsDir = os.path.join(_srcHome, "artifacts")
binDir = os.path.join(_srcHome, "bin")


# SSH #####################################################################
SSHUserName = "yurt"
SSHPrivateKeyFile = os.path.join(provisionDir, "ssh", "id_rsa_yurt")
SSHHostKeysFile = os.path.join(configDir, "known_hosts")


# Utilities ###############################################################
def _ensureConfigFileExists():
    if not os.path.isdir(configDir):
        os.makedirs(configDir)

    if not os.path.isfile(configFile):
        with open(configFile, 'w') as f:
            f.write('{}')


def _readConfig():
    try:
        _ensureConfigFileExists()
        with open(configFile, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        msg = 'Config file not found'
        logging.error(msg)
        raise ConfigReadException(msg)
    except json.JSONDecodeError:
        msg = f"Malformed config file: {configFile}"
        logging.error(msg)
        raise ConfigReadException(msg)


def _writeConfig(config):
    try:
        _ensureConfigFileExists()
        with open(configFile, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        logging.error(f"Error writing config: {e}")
        raise ConfigWriteException(e)


def getConfig(configName: ConfigName):
    config = _readConfig()
    if config:
        return config.get(configName.name, None)


def setConfig(configName: ConfigName, value: str):
    old = _readConfig()

    if old is None:
        return

    new = old.copy()
    new[configName.name] = value

    try:
        _writeConfig(new)
    except ConfigWriteException:
        _writeConfig(old)
        raise ConfigWriteException


def clear():
    logging.debug("Clearing config")
    _writeConfig({})
