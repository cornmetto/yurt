import logging
import time
from enum import Enum

from yurt.vboxmanage import VBoxManage
from yurt.exceptions import (
    VBoxManageException,
    ConfigReadException,
    ConfigWriteException,
    VMException
)
import config
from config import ConfigName


vbox = VBoxManage()


_VM_NAME = config.getConfig(ConfigName.vmName)


class VMState(Enum):
    NotInitialized = 1
    Stopped = 2
    Running = 3


def state():
    if _VM_NAME:
        try:
            vmInfo = vbox.getVmInfo(_VM_NAME)
            isRunning = vmInfo["VMState"].strip('"') == "running"
            return VMState.Running if isRunning else VMState.Stopped
        except (VBoxManageException, KeyError):
            raise VMException("An error occurred while fetching VM status.")
    return VMState.NotInitialized


def info():
    if _VM_NAME:
        try:
            vmInfo = vbox.getVmInfo(_VM_NAME)
            return {
                "State": "Running" if vmInfo["VMState"].strip('"') == "running" else "Stopped",
                "Memory": vmInfo["memory"],
                "CPUs": vmInfo["cpus"]
            }
        except (VBoxManageException, KeyError):
            raise VMException("An error occurred while fetching VM status.")

    return {
        "State": "Not Initialized"
    }


def init(applianceVersion=None):
    global _VM_NAME
    from uuid import uuid4
    from os import path

    if not applianceVersion:
        applianceVersion = config.applianceVersion

    applianceFile = path.join(config.artifactsDir,
                              "{0}-{1}.ova".format(config.applicationName, applianceVersion))

    if state() != VMState.NotInitialized:
        logging.info("{0} has already been initialized.".format(
            config.applicationName))
        logging.info(
            "If you need to start over, destroy the existing environment first with `yurt machine destroy`")
        return

    vmName = "{0}-{1}".format(config.applicationName, uuid4())

    try:
        vbox.importVm(
            vmName, applianceFile, config.vmInstallDir)

        config.setConfig(ConfigName.vmName, vmName)
        _VM_NAME = vmName

        _initializeNetwork()

    except (ConfigWriteException, VBoxManageException):
        logging.error("Initialization failed")
        destroy(force=True)


def start():
    vmState = state()

    if vmState == VMState.NotInitialized:
        raise VMException("VM has not yet been initialized")

    if vmState == VMState.Running:
        logging.info("{0} is already running".format(
            config.applicationName))
        return

    try:
        logging.info("{0} is starting up...".format(
            config.applicationName))
        vbox.startVm(_VM_NAME)
        time.sleep(2)
        logging.info("Network setup...")
        time.sleep(10)

        hostSSHPort = vbox.setUpSSHPortForwarding(
            _VM_NAME)
        config.setConfig(ConfigName.hostSSHPort, hostSSHPort)

    except VBoxManageException as e:
        logging.error(e.message)
        raise VMException("Start up failed")


def shutdown():
    if state() == VMState.NotInitialized:
        logging.info(
            f"{config.applicationName} has not been initialized. Initialize with 'yurt init'.")
    elif state() == VMState.Stopped:
        logging.info(f"{config.applicationName} is not running")
    else:
        try:
            vbox.stopVm(_VM_NAME)
        except VBoxManageException as e:
            logging.error(e.message)
            raise VMException("Shut down failed")


def destroy(force=False):
    global _VM_NAME
    if state() == VMState.NotInitialized and not force:
        logging.warning(
            f"{config.applicationName} is not initialized")
        return

    try:
        vbox.destroyVm(_VM_NAME)
        interfaceName = config.getConfig(ConfigName.hostOnlyInterface)
        vbox.removeHostOnlyInterface(interfaceName)

        _VM_NAME = None
        config.clear()
    except VBoxManageException as e:
        logging.error(e.message)
        raise VMException(
            f"Failed to destroy {config.applicationName} environment.")


# Utilities ###########################################################


def _initializeNetwork():
    try:
        interfaceName = vbox.createHostOnlyInterface()
        interfaceInfo = vbox.getInterfaceInfo(interfaceName)
        IPAddress = interfaceInfo['IPAddress']
        networkMask = interfaceInfo['NetworkMask']
        config.setConfig(ConfigName.hostOnlyInterface, interfaceName)
        config.setConfig(ConfigName.hostOnlyInterfaceIPAddress, IPAddress)
        config.setConfig(
            ConfigName.hostOnlyInterfaceNetworkMask, networkMask)

        quotedInterfaceName = '"{}"'.format(interfaceName)
        vbox.modifyVm(_VM_NAME,
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

    except VBoxManageException as e:
        logging.error(e.message)
        raise VMException("Network initialization failed")
