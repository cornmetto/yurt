import logging
from enum import Enum

import config
from yurt import util
from . import vbox
from yurt.exceptions import (
    ConfigReadException,
    ConfigWriteException,
    VMException,
    VBoxException,
)

_VM_NAME = config.get_config(config.Key.vm_name)


class State(Enum):
    NotInitialized = 1
    Stopped = 2
    Running = 3


def state():
    if _VM_NAME:
        try:
            vm_info = vbox.get_vm_info(_VM_NAME)
            is_running = vm_info["VMState"].strip('"') == "running"
            return State.Running if is_running else State.Stopped
        except (VBoxException, KeyError):
            raise VMException("An error occurred while fetching VM status.")
    return State.NotInitialized


def info():
    if _VM_NAME:
        try:
            vm_info = vbox.get_vm_info(_VM_NAME)
            return {
                "State": "Running"
                if vm_info["VMState"].strip('"') == "running"
                else "Stopped",
                "Memory": vm_info["memory"],
                "CPUs": vm_info["cpus"],
            }
        except (VBoxException, KeyError):
            raise VMException("An error occurred while fetching VM status.")

    return {"State": "Not Initialized"}


def init(appliance_version=None):
    global _VM_NAME
    from uuid import uuid4
    from os import path

    if not appliance_version:
        appliance_version = config.appliance_version

    appliance_file = path.join(
        config.artifacts_dir, "{0}-{1}.ova".format(
            config.app_name, appliance_version)
    )

    if state() != State.NotInitialized:
        logging.info(
            "{0} has already been initialized.".format(config.app_name))
        logging.info(
            "If you need to start over, destroy the existing environment first with `yurt machine destroy`"
        )
        return

    vm_name = "{0}-{1}".format(config.app_name, uuid4())

    try:
        logging.info("Importing appliance...")
        vbox.import_vm(vm_name, appliance_file, config.vm_install_dir)

        config.set_config(config.Key.vm_name, vm_name)
        _VM_NAME = vm_name

        input("Installing network interface on host. Press enter to continue...")
        _initialize_network()

    except (ConfigWriteException, VBoxException):
        logging.error("Initialization failed")
        destroy()


def start():
    vm_state = state()

    if vm_state == State.NotInitialized:
        raise VMException("VM has not yet been initialized.")

    if vm_state == State.Running:
        logging.info("VM is already running.")
        return

    try:
        logging.info("Starting up...")
        vbox.start_vm(_VM_NAME)

        util.sleep_for(5, show_spinner=True)
        logging.info("Setting up networking...")
        util.sleep_for(5, show_spinner=True)

        current_port = config.get_config(config.Key.ssh_port)
        host_ssh_port = vbox.setup_ssh_port_forwarding(_VM_NAME, current_port)
        config.set_config(config.Key.ssh_port, host_ssh_port)

    except (VBoxException, ConfigReadException) as e:
        logging.error(e.message)
        raise VMException("Start up failed")


def stop():
    vm_state = state()

    if vm_state == State.NotInitialized:
        logging.info(
            "The VM has not been initialized. Initialize with 'yurt vm init'.")
    elif vm_state == State.Stopped:
        logging.info("The VM is not running")
    else:
        try:
            vbox.stop_vm(_VM_NAME)
        except VBoxException as e:
            logging.error(e.message)
            raise VMException("Shut down failed")


def force_delete_yurt_dir():
    import shutil

    shutil.rmtree(config.config_dir, ignore_errors=True)


def destroy():
    global _VM_NAME

    try:
        vbox.destroy_vm(_VM_NAME)
        interface_name = config.get_config(config.Key.interface)

        input("Removing network interface on host. Press enter to continue...")
        vbox.remove_hostonly_interface(interface_name)

        _VM_NAME = None
        config.clear()
    except VBoxException as e:
        logging.error(e.message)
        raise VMException("Failed to destroy VM.")


def _initialize_network():
    try:
        interface_name = vbox.create_hostonly_interface()
        interface_info = vbox.get_interface_info(interface_name)
        ip_address = interface_info["IPAddress"]
        network_mask = interface_info["NetworkMask"]
        config.set_config(config.Key.interface, interface_name)
        config.set_config(config.Key.interface_ip_address, ip_address)
        config.set_config(config.Key.interface_netmask, network_mask)

        vbox.modify_vm(
            _VM_NAME,
            {
                "nic1": "nat",
                "nictype1": "virtio",
                "natnet1": "10.0.2.0/24",
                "natdnshostresolver1": "on",
                "nic2": "hostonly",
                "nictype2": "virtio",
                "hostonlyadapter2": interface_name,
                "nicpromisc2": "allow-all",
            },
        )

    except VBoxException as e:
        logging.error(e.message)
        raise VMException("Network initialization failed")
