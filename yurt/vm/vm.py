import logging
from enum import Enum
import shutil
import os

from yurt import util, config
from . import vbox
from yurt.exceptions import (
    ConfigReadException,
    ConfigWriteException,
    VMException,
    VBoxException,
    YurtException
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
        except (VBoxException, KeyError) as e:
            logging.debug(e)
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
        except (VBoxException, KeyError) as e:
            logging.debug(e)
            raise VMException("An error occurred while fetching VM status.")

    return {"State": "Not Initialized"}


def download_image():
    if os.path.isfile(config.image) and util.is_sha256(config.image, config.image_sha256):
        logging.info("Using cached image...")
    else:
        logging.info(f"Downloading image from {config.image_url}")

        image_dir = os.path.dirname(config.image)
        if not os.path.isdir(image_dir):
            os.mkdir(image_dir)

        util.download_file(
            config.image_url, config.image, show_progress=True
        )

        if not util.is_sha256(config.image, config.image_sha256):
            raise VMException(
                "Error downloading image. Re-run 'init'.")


def init():
    global _VM_NAME
    from uuid import uuid4

    if state() is not State.NotInitialized:
        logging.info(
            "The VM has already been initialized.")
        logging.info(
            "If you need to start over, destroy the existing environment first with `yurt vm destroy`"
        )
        return

    download_image()

    vm_name = "{0}-{1}".format(config.app_name, uuid4())

    try:
        logging.info("Importing appliance...")
        vbox.import_vm(vm_name, config.image,
                       config.vm_install_dir, config.vm_memory)

        config.set_config(config.Key.vm_name, vm_name)
        _VM_NAME = vm_name

        input("""Installing VirtualBox network interface.
Accept VirtualBox's prompt to allow networking with the host.
Press enter to continue...""")
        _attach_config_disk()
        _attach_storage_pool_disk()
        _setup_network()

    except (
        ConfigWriteException,
        VBoxException,
        VMException,
    ) as e:
        logging.error(e.message)
        logging.info("Cleaning up...")
        destroy()
        delete_instance_files()
        raise VMException("Initialization failed.")
    except KeyboardInterrupt:
        logging.info("\nUser interrupted initialization. Cleaning up.")
        destroy()
        delete_instance_files()
        raise VMException("Initialization failed")


def start():
    from datetime import datetime

    vm_state = state()

    if vm_state == State.NotInitialized:
        raise VMException("VM has not yet been initialized.")

    if vm_state == State.Running:
        logging.info("VM is already running.")
        return

    try:
        logging.info("Booting up...")

        console_file_name = os.path.join(config.vm_install_dir, "console.log")
        vbox.attach_serial_console(_VM_NAME, console_file_name)

        vbox.start_vm(_VM_NAME)
        util.sleep_for(10, show_spinner=True)
        logging.info("Waiting for the machine to be ready...")
        util.sleep_for(10, show_spinner=True)

        current_port = config.get_config(config.Key.ssh_port)
        host_ssh_port = vbox.setup_ssh_port_forwarding(_VM_NAME, current_port)
        config.set_config(config.Key.ssh_port, host_ssh_port)

        vbox.setup_lxd_port_forwarding(_VM_NAME)

    except (VBoxException, ConfigReadException) as e:
        logging.error(e.message)
        raise VMException("Start up failed")


def ensure_is_ready(prompt_init=True, prompt_start=True):
    initialize_vm_prompt = "Yurt has not been initialized. Initialize now?"
    start_vm_prompt = "Yurt is not running. Boot up now?"

    if state() == State.NotInitialized:
        if prompt_init:
            initialize_vm = util.prompt_user(
                initialize_vm_prompt, ["yes", "no"]) == "yes"
        else:
            initialize_vm = True

        if initialize_vm:
            try:
                init()
                logging.info("Done.")
            except YurtException as e:
                logging.error(e.message)
        else:
            raise VMException("Not initialized")

    if state() == State.Stopped:
        from yurt import lxc

        if prompt_start:
            start_vm = util.prompt_user(
                start_vm_prompt, ["yes", "no"]) == "yes"
        else:
            start_vm = True

        if start_vm:
            try:
                start()
                lxc.configure_lxd()
            except YurtException as e:
                logging.error(e.message)
        else:
            raise VMException("Not started")


def stop(force=False):
    vm_state = state()

    def confirm_shutdown():
        if state() == State.Running:
            raise VMException("VM is still running.")

    if vm_state != State.Running:
        logging.info("Yurt is not running.")
    else:
        try:
            if force:
                logging.info("Forcing shutdown...")
            else:
                logging.info("Attempting to shut down gracefully...")

            vbox.stop_vm(_VM_NAME, force=force)
            util.retry(confirm_shutdown, retries=10, wait_time=5)
        except VBoxException as e:
            logging.error(e.message)
            raise VMException("Shut down failed")


def delete_instance_files():
    shutil.rmtree(config.vm_install_dir, ignore_errors=True)
    config.clear()


def destroy():
    global _VM_NAME

    try:
        vbox.destroy_vm(_VM_NAME)
        interface_name = config.get_config(config.Key.interface)

        vbox.remove_hostonly_interface(interface_name)

        _VM_NAME = None
        config.clear()
    except VBoxException as e:
        logging.error(e.message)
        raise VMException("Failed to destroy VM.")


def _setup_network():
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


def _attach_storage_pool_disk():
    try:
        vbox.create_disk(
            config.storage_pool_disk,
            config.storage_pool_disk_size_mb
        )
        vbox.attach_disk(_VM_NAME, config.storage_pool_disk, 2)
    except VBoxException as e:
        logging.error(e.message)
        raise VMException("Storage setup failed")


def _attach_config_disk():
    try:
        vbox.clone_disk(config.config_disk_source, config.config_disk)
        vbox.attach_disk(_VM_NAME, config.config_disk, 1)
    except VBoxException as e:
        logging.error(e)
        raise VMException("Failed to attach config disk.")
