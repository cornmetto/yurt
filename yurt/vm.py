import logging
from enum import Enum

import config
from config import ConfigName, ConfigWriteException

from yurt import vbox, util
from yurt.exceptions import VMException


_VM_NAME = config.getConfig(ConfigName.vmName)


class State(Enum):
    NotInitialized = 1
    Stopped = 2
    Running = 3


def state():
    if _VM_NAME:
        try:
            vmInfo = vbox.get_vm_info(_VM_NAME)
            isRunning = vmInfo["VMState"].strip('"') == "running"
            return State.Running if isRunning else State.Stopped
        except (vbox.VBoxException, KeyError):
            raise VMException("An error occurred while fetching VM status.")
    return State.NotInitialized


def info():
    if _VM_NAME:
        try:
            vmInfo = vbox.get_vm_info(_VM_NAME)
            return {
                "State": "Running" if vmInfo["VMState"].strip('"') == "running" else "Stopped",
                "Memory": vmInfo["memory"],
                "CPUs": vmInfo["cpus"]
            }
        except (vbox.VBoxException, KeyError):
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

    if state() != State.NotInitialized:
        logging.info("{0} has already been initialized.".format(
            config.applicationName))
        logging.info(
            "If you need to start over, destroy the existing environment first with `yurt machine destroy`")
        return

    vmName = "{0}-{1}".format(config.applicationName, uuid4())

    try:
        logging.info("Importing appliance...")
        vbox.import_vm(
            vmName, applianceFile, config.vmInstallDir)

        config.setConfig(ConfigName.vmName, vmName)
        _VM_NAME = vmName

        logging.info("Installing host network interface...")
        input("""VirtualBox will now ask for permission to add an interface on your machine.
Press enter to continue..."""
              )
        _initializeNetwork()

    except (ConfigWriteException, vbox.VBoxException):
        logging.error("Initialization failed")
        destroy()


def start():
    vmState = state()

    if vmState == State.NotInitialized:
        raise VMException("VM has not yet been initialized")

    if vmState == State.Running:
        logging.info("{0} is already running".format(
            config.applicationName))
        return

    try:
        logging.info("Starting up...")
        vbox.start_vm(_VM_NAME)

        util.sleep_for(2, show_spinner=True)
        logging.info("Network setup...")
        util.sleep_for(10, show_spinner=True)

        hostSSHPort = vbox.setup_ssh_port_forwarding(
            _VM_NAME)
        config.setConfig(ConfigName.hostSSHPort, hostSSHPort)

    except vbox.VBoxException as e:
        logging.error(e.message)
        raise VMException("Start up failed")


def shutdown():
    if state() == State.NotInitialized:
        logging.info(
            f"{config.applicationName} has not been initialized. Initialize with 'yurt init'.")
    elif state() == State.Stopped:
        logging.info(f"{config.applicationName} is not running")
    else:
        try:
            vbox.stop_vm(_VM_NAME)
        except vbox.VBoxException as e:
            logging.error(e.message)
            raise VMException("Shut down failed")


def force_delete_yurt_dir():
    import shutil
    config_dir = config.configDir
    shutil.rmtree(config_dir, ignore_errors=True)


def destroy():
    global _VM_NAME

    try:
        vbox.destroy_vm(_VM_NAME)
        interfaceName = config.getConfig(ConfigName.hostOnlyInterface)
        vbox.remove_hostonly_interface(interfaceName)

        _VM_NAME = None
        config.clear()
    except vbox.VBoxException as e:
        logging.error(e.message)
        raise VMException("Failed to destroy VM.")


# Utilities ###########################################################


def _initializeNetwork():
    try:
        interfaceName = vbox.create_hostonly_interface()
        interfaceInfo = vbox.get_interface_info(interfaceName)
        IPAddress = interfaceInfo['IPAddress']
        networkMask = interfaceInfo['NetworkMask']
        config.setConfig(ConfigName.hostOnlyInterface, interfaceName)
        config.setConfig(ConfigName.hostOnlyInterfaceIPAddress, IPAddress)
        config.setConfig(
            ConfigName.hostOnlyInterfaceNetworkMask, networkMask)

        vbox.modify_vm(_VM_NAME,
                       {
                           'nic1': 'nat',
                           'nictype1': 'virtio',
                           'natnet1': '10.0.2.0/24',
                           "natdnshostresolver1": "on",
                           'nic2': 'hostonly',
                           'nictype2': 'virtio',
                           'hostonlyadapter2': interfaceName,
                           'nicpromisc2': 'allow-all'
                       })

    except vbox.VBoxException as e:
        logging.error(e.message)
        raise VMException("Network initialization failed")
