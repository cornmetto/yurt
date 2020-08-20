import os
import logging
import json
from enum import Enum


class ConfigName(Enum):
    vmName = 1
    hostOnlyInterface = 2
    hostSSHPort = 3


class ConfigReadError(Exception):
    def __init__(self, message):
        self.message = message


class ConfigWriteError(Exception):
    def __init__(self, message):
        self.message = message


class Config:
    def __init__(self, applicationName="yurt", fileName="config.json", vmInstallDir="vm"):
        configDir = os.path.join(os.environ.get(
            'HOME'), ".{0}".format(applicationName))
        configFile = os.path.join(configDir, fileName)

        self.applicationName = applicationName
        self.configDir = configDir
        self.configFile = configFile

        self._ensureConfigFileExists()

        logging.debug('Using config %s', self.configFile)

        # Constants. ############################################
        self.applianceVersion = "0.0.2"

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
            raise ConfigReadError(msg)
        except json.JSONDecodeError:
            msg = 'Malformed config file: {0}'.format(self.configFile)
            logging.error(msg)
            raise ConfigReadError(msg)

    def _writeConfig(self, config):
        try:
            with open(self.configFile, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            logging.error("Error writing config: {0}".format(e))
            raise ConfigWriteError(e)

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
        except ConfigWriteError:
            self._writeConfig(old)
            raise ConfigWriteError

    def clear(self):
        logging.debug("Clearing config")
        self._writeConfig({})


class TestConfig(Config):
    def __init__(self):
        super().__init__(fileName="testConfig.json", vmInstallDir="vm-test")
