import logging
import uuid
import os

from .vboxmanage import VBoxManage, VBoxManageError
from config import ConfigName, ConfigReadError


class VM:
    def __init__(self, config):
        self.config = config
        self.vbox = VBoxManage()
        self.vmName = self.config.get(ConfigName.vmName)

    def isInitialized(self):
        if self.vmName:
            try:
                self.vbox.vmInfo(self.vmName)
                return True
            except VBoxManageError:
                logging.error(
                    "Inconsistent environment. VM Name in config does not exist.")
                return False
        return False

    def isRunning(self):
        try:
            vmInfo = self.vbox.vmInfo(self.vmName)
            return vmInfo["VMState"].strip('"') == "running"
        except:
            return False

    def init(self):
        config = self.config
        applianceFile = os.path.join(self.config.artifactsDir,
                                     "{0}-{1}.ova".format(config.applicationName, config.applianceVersion))

        if self.isInitialized():
            logging.info("{0} has already been initialized.".format(
                config.applicationName))
            logging.info(
                "If you need to start over, destroy the existing environment first.")
        else:
            vmName = "{0}-{1}".format(config.applicationName, uuid.uuid4())
            self.vmName = vmName
            config.set(ConfigName.vmName, vmName)
            try:
                self.vbox.importVm(
                    vmName, applianceFile, config.vmInstallDir)
            except VBoxManageError as e:
                logging.debug(e)
                logging.error("Initialization failed")
                config.clear()

    def start(self):
        if self.isRunning():
            logging.info("{0} is already running".format(
                self.config.applicationName))
        else:
            self.vbox.startVm(self.vmName)

    def stop(self):
        if self.isRunning():
            self.vbox.stopVm(self.vmName)
        else:
            logging.info("{0} is already stopped".format(
                self.config.applicationName))

    def destroy(self):
        if self.isInitialized():
            self.vbox.destroyVm(self.vmName)
            self.config.clear()
            self.vmName = None
        else:
            logging.warning(
                "Attempting to destroy an uninitialized environment")
