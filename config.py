import os
import logging
import json
from enum import Enum

from yurt.exceptions import ConfigWriteException, ConfigReadException


class ConfigName(Enum):
    vmName = 1
    hostOnlyInterface = 2
    hostOnlyInterfaceIPAddress = 3
    hostOnlyInterfaceNetworkMask = 4
    hostSSHPort = 5
    hostLXDPort = 6


class Config:
    def __init__(self, applicationName="yurt", env="prod"):

        if env == "prod":
            fileName = "config.json"
            vmInstallDir = "vm"
        else:
            fileName = "testConfig.json"
            vmInstallDir = "vm-test"

        configDir = os.path.join(os.environ.get(
            'HOME'), ".{0}".format(applicationName))
        configFile = os.path.join(configDir, fileName)

        self.applicationName = applicationName
        self.configDir = configDir
        self.configFile = configFile

        self._ensureConfigFileExists()

        logging.debug('Using config %s', self.configFile)

        # Constants. ############################################
        self.applianceVersion = "0.1.4"

        # Paths
        provisionDir = os.path.join(
            os.path.dirname(__file__), "provision")
        self.artifactsDir = os.path.join(
            os.path.dirname(__file__), "artifacts")
        self.vmInstallDir = os.path.join(configDir, vmInstallDir)
        self.SSHUserName = "yurt"
        self.SSHPrivateKeyFile = os.path.join(
            provisionDir, ".ssh", "id_rsa_yurt")
        self.SSHHostKeysFile = os.path.join(
            configDir, "known_hosts")
        self.LXDTLSKey = os.path.join(provisionDir, ".tls", "client.key")
        self.LXDTLSCert = os.path.join(provisionDir, ".tls", "client.crt")

        #########################################################

    def _ensureConfigFileExists(self):
        if not os.path.isdir(self.configDir):
            os.makedirs(self.configDir)

        if not os.path.isfile(self.configFile):
            with open(self.configFile, 'w') as f:
                f.write('{}')

    def _readConfig(self):
        try:
            with open(self.configFile, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            msg = 'Config file not found'
            logging.error(msg)
            raise ConfigReadException(msg)
        except json.JSONDecodeError:
            msg = 'Malformed config file: {0}'.format(self.configFile)
            logging.error(msg)
            raise ConfigReadException(msg)

    def _writeConfig(self, config):
        try:
            with open(self.configFile, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            logging.error("Error writing config: {0}".format(e))
            raise ConfigWriteException(e)

    def get(self, configName: ConfigName):
        config = self._readConfig()
        if config:
            return config.get(configName.name, None)

    def set(self, configName: ConfigName, value: str):
        old = self._readConfig()

        if old is None:
            return

        new = old.copy()
        new[configName.name] = value

        try:
            self._writeConfig(new)
        except ConfigWriteException:
            self._writeConfig(old)
            raise ConfigWriteException

    def clear(self):
        logging.debug("Clearing config")
        self._writeConfig({})
