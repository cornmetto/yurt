import logging
import uuid
import os
import time

from .vboxmanage import VBoxManage
from .exceptions import (LXDException, VBoxManageException,
                         ConfigReadException, ConfigWriteException, VMException)
from .lxd import LXD
from config import ConfigName


class VM:
    def __init__(self, config):
        self.config = config
        self.vbox = VBoxManage()
        self.vmName = self.config.get(ConfigName.vmName)

        self.lxd = None
        if self.isInitialized() and self.isRunning():
            self.lxd = LXD(self.config)

    def isInitialized(self):
        if self.vmName:
            try:
                self.vbox.getVmInfo(self.vmName)
                return True
            except VBoxManageException:
                logging.error(
                    "Inconsistent environment.")
                return False
        return False

    def isRunning(self):
        try:
            vmInfo = self.vbox.getVmInfo(self.vmName)
            return vmInfo["VMState"].strip('"') == "running"
        except (VBoxManageException, KeyError):
            logging.error(
                "An error occurred while trying to determine status.")

    def init(self, applianceVersion=None):
        config = self.config

        if not applianceVersion:
            applianceVersion = config.applianceVersion

        applianceFile = os.path.join(self.config.artifactsDir,
                                     "{0}-{1}.ova".format(config.applicationName, applianceVersion))

        if self.isInitialized():
            logging.info("{0} has already been initialized.".format(
                config.applicationName))
            logging.info(
                "If you need to start over, destroy the existing environment first with `yurt machine destroy`")
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
            interfaceInfo = self.vbox.getInterfaceInfo(interfaceName)
            IPAddress = interfaceInfo['IPAddress']
            networkMask = interfaceInfo['NetworkMask']
            self.config.set(ConfigName.hostOnlyInterface, interfaceName)
            self.config.set(ConfigName.hostOnlyInterfaceIPAddress, IPAddress)
            self.config.set(
                ConfigName.hostOnlyInterfaceNetworkMask, networkMask)

            quotedInterfaceName = '"{}"'.format(interfaceName)
            self.vbox.modifyVm(self.vmName,
                               {
                                   'nic1': 'nat',
                                   'nictype1': 'virtio',
                                   'natnet1': '10.0.2.0/24',
                                   "natdnshostresolver1": "on",
                                   'nic2': 'hostonly',
                                   'nictype2': 'virtio',
                                   'hostonlyadapter2': quotedInterfaceName,
                                   'nicpromisc2': 'allow-all'
                               })

        except (VBoxManageException, ConfigWriteException):
            msg = "Network initialization failed"
            logging.error(msg)
            raise VBoxManageException(msg)

    def start(self):
        config = self.config

        if not self.isInitialized():
            raise VMException("VM has not yet been initialized")

        if self.isRunning():
            logging.info("{0} is already running".format(
                config.applicationName))
            return

        try:
            logging.info("{0} is starting up...".format(
                config.applicationName))
            self.vbox.startVm(self.vmName)
            time.sleep(2)
            logging.info("Network setup...")
            time.sleep(10)

            hostSSHPort = self.vbox.setUpSSHPortForwarding(
                self.vmName, config)
            hostLXDPort = self.vbox.setUpLXDPortForwarding(
                self.vmName, config)
            config.set(ConfigName.hostSSHPort, hostSSHPort)
            config.set(ConfigName.hostLXDPort, hostLXDPort)

            self.lxd = LXD(config)
            self.lxd.setUp()

        except (VBoxManageException, ConfigWriteException, LXDException) as e:
            logging.error(e.message)
            logging.error("Start up failed")

    def stop(self):
        if not self.isRunning():
            logging.info("{0} is already stopped".format(
                self.config.applicationName))
            return

        try:
            self.vbox.stopVm(self.vmName)
        except VBoxManageException:
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
            self.lxd = None
        except VBoxManageException:
            logging.error("Failed to destroy {0} environment.".format(
                self.config.applicationName))
