import logging
import uuid
import os

from .vboxmanage import VBoxManage, VBoxManageError
from config import ConfigName, ConfigReadError, ConfigWriteError


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
                    "Inconsistent environment.")
                return False
        return False

    def isRunning(self):
        try:
            vmInfo = self.vbox.vmInfo(self.vmName)
            return vmInfo["VMState"].strip('"') == "running"
        except (VBoxManageError, KeyError):
            logging.error(
                "An error occurred while trying to determine status.")

    def init(self):
        config = self.config
        applianceFile = os.path.join(self.config.artifactsDir,
                                     "{0}-{1}.ova".format(config.applicationName, config.applianceVersion))

        if self.isInitialized():
            logging.info("{0} has already been initialized.".format(
                config.applicationName))
            logging.info(
                "If you need to start over, destroy the existing environment first.")
            return

        vmName = "{0}-{1}".format(config.applicationName, uuid.uuid4())
        self.vmName = vmName

        try:
            config.set(ConfigName.vmName, vmName)
            self.vbox.importVm(
                vmName, applianceFile, config.vmInstallDir)
            self._initializeNetwork()
        except:
            logging.error("Initialization failed")
            self.destroy(force=True)

    def _initializeNetwork(self):
        try:
            interfaceName = self.vbox.createHostOnlyInterface()
            self.config.set(ConfigName.hostOnlyInterface, interfaceName)

            quotedInterfaceName = '"{}"'.format(interfaceName)
            self.vbox.modifyVm(self.vmName,
                               {
                                   'nic1': 'nat',
                                   'nictype1': 'virtio',
                                   'nic2': 'hostonly',
                                   'nictype2': 'virtio',
                                   'hostonlyadapter2': quotedInterfaceName
                               })

        except (VBoxManageError, ConfigWriteError):
            msg = "Network initialization failed"
            logging.error(msg)
            raise VBoxManageError(msg)

    def start(self):
        if self.isRunning():
            logging.info("{0} is already running".format(
                self.config.applicationName))
            return

        try:
            self.vbox.startVm(self.vmName)
        except VBoxManageError:
            logging.error("Start up failed")

    def stop(self):
        if not self.isRunning():
            logging.info("{0} is already stopped".format(
                self.config.applicationName))
            return

        try:
            self.vbox.stopVm(self.vmName)
        except VBoxManageError:
            logging.error("Shut down failed")

    def destroy(self, force=False):
        if not self.isInitialized() and not force:
            logging.warning(
                "{0} is not initialized".format(self.config.applicationName))
            return

        try:
            self.vbox.destroyVm(self.vmName)
            interfaceName = self.config.get(ConfigName.hostOnlyInterface)
            self.vbox.removeHostOnlyInterface(interfaceName)

            self.config.clear()
            self.vmName = None
        except VBoxManageError:
            logging.error("Failed to destroy {0} environment.".format(
                self.config.applicationName))
