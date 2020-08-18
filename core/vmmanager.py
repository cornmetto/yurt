import logging
import uuid

from .vboxmanage import VBoxManage
from config import ConfigName, ConfigReadError


class VMManager:
    def __init__(self, config):
        self.config = config

    def init(self):
        config = self.config
        try:
            vmName = config.get(ConfigName.vmName)
        except ConfigReadError:
            return

        if vmName:
            logging.info("{0} has already been initialized.".format(
                config.applicationName))
            logging.info(
                "If you need to start over, destroy the existing environment first.")
        else:
            vmUuid = uuid.uuid4()
            vmName = "{0}-{1}".format(config.applicationName, vmUuid)
            config.set(ConfigName.vmName, vmName)
            config.set(ConfigName.vmUuid, str(vmUuid))

    def start(self):
        pass

    def stop(self):
        pass
