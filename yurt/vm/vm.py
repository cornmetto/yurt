import logging
import os
import shutil
from enum import Enum

from yurt import config
from yurt import util as yurt_util
from yurt.exceptions import (ConfigReadException, ConfigWriteException,
                             VBoxException, VMException, YurtException)

from . import util, vbox


class State(Enum):
    NotInitialized = 1
    Stopped = 2
    Running = 3


def state():
    try:
        vm_name = util.vm_name()
        vm_info = vbox.get_vm_info(vm_name)
        is_running = vm_info["VMState"].strip('"') == "running"
        return State.Running if is_running else State.Stopped
    except VMException:
        return State.NotInitialized
    except (VBoxException, KeyError) as e:
        logging.debug(e)
        raise VMException("An error occurred while fetching VM status.")


def info():
    vm_state = state()
    if vm_state != State.NotInitialized:
        vm_name = util.vm_name()
        try:
            vm_info = vbox.get_vm_info(vm_name)
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
    else:
        return {"State": "Not Initialized"}


def download_image():
    if os.path.isfile(config.image) and yurt_util.is_sha256(config.image, config.image_sha256):
        logging.info("Using cached image...")
    else:
        logging.info(f"Downloading image from {config.image_url}")

        image_dir = os.path.dirname(config.image)
        if not os.path.isdir(image_dir):
            os.mkdir(image_dir)

        yurt_util.download_file(
            config.image_url, config.image, show_progress=True
        )

        if not yurt_util.is_sha256(config.image, config.image_sha256):
            raise VMException(
                "Error downloading image. Re-run 'init'.")


def init():
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
    vm_state = state()
    vm_name = util.vm_name()

    if vm_state == State.NotInitialized:
        raise VMException("VM has not yet been initialized.")

    if vm_state == State.Running:
        logging.info("VM is already running.")
        return

    try:
        logging.info("Starting up...")

        console_file_name = os.path.join(config.vm_install_dir, "console.log")
        vbox.attach_serial_console(vm_name, console_file_name)

        vbox.start_vm(vm_name)

        yurt_util.sleep_for(5, show_spinner=True)
        util.setup_port_forwarding()
        util.wait_for_ssh()

    except (VBoxException, ConfigReadException) as e:
        logging.error(e.message)
        raise VMException("Start up failed")


def ensure_is_ready(prompt_init=True, prompt_start=True):
    initialize_vm_prompt = "Yurt has not been initialized. Initialize now?"
    start_vm_prompt = "Yurt is not running. Start up now?"

    if state() == State.NotInitialized:
        if prompt_init:
            initialize_vm = yurt_util.prompt_user(
                initialize_vm_prompt, ["y", "n"]) == "y"
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
            start_vm = yurt_util.prompt_user(
                start_vm_prompt, ["y", "n"]) == "y"
        else:
            start_vm = True

        if start_vm:
            try:
                start()
                lxc.ensure_is_ready()
            except YurtException as e:
                logging.error(e.message)
        else:
            raise VMException("Not started")


def stop(force=False):
    vm_state = state()
    vm_name = util.vm_name()

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

            vbox.stop_vm(vm_name, force=force)
            yurt_util.retry(confirm_shutdown, retries=6, wait_time=10)
        except VBoxException as e:
            logging.error(e.message)
            raise VMException("Shut down failed")


def delete_instance_files():
    shutil.rmtree(config.vm_install_dir, ignore_errors=True)
    config.clear()


def destroy():
    vm_name = util.vm_name()

    try:
        vbox.destroy_vm(vm_name)
        interface_name = config.get_config(config.Key.interface)

        vbox.remove_hostonly_interface(interface_name)

        config.clear()
    except VBoxException as e:
        logging.error(e.message)
        raise VMException("Failed to destroy VM.")


def run_cmd(cmd: str, show_spinner: bool = False, stdin=None):
    """
    Run a command in the VM over SSH.
    """
    from . import ssh

    if show_spinner:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as executor:
            cmd_future = executor.submit(
                ssh.run_cmd, cmd, hide_output=show_spinner,
                stdin=stdin
            )
            executor.submit(yurt_util.async_spinner, cmd_future)
            return cmd_future.result()
    else:
        return ssh.run_cmd(cmd, stdin=stdin)


def ssh():
    import subprocess

    ssh_port = config.get_config(config.Key.ssh_port)
    subprocess.run(
        f"ssh -i {config.ssh_private_key_file} yurt@127.0.0.1 -p {ssh_port}",
    )


def put_file(local_path: str, remote_path: str):
    from . import ssh

    ssh.put_file(local_path, remote_path)


def _setup_network():
    vm_name = util.vm_name()
    try:
        interface_name = vbox.create_hostonly_interface()
        interface_info = vbox.get_interface_info(interface_name)
        ip_address = interface_info["IPAddress"]
        network_mask = interface_info["NetworkMask"]
        config.set_config(config.Key.interface, interface_name)
        config.set_config(config.Key.interface_ip_address, ip_address)
        config.set_config(config.Key.interface_netmask, network_mask)

        vbox.modify_vm(
            vm_name,
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
    vm_name = util.vm_name()
    try:
        vbox.create_disk(
            config.storage_pool_disk,
            config.storage_pool_disk_size_mb
        )
        vbox.attach_disk(vm_name, config.storage_pool_disk, 2)
    except VBoxException as e:
        logging.error(e.message)
        raise VMException("Storage setup failed")


def _attach_config_disk():
    vm_name = util.vm_name()
    try:
        vbox.clone_disk(config.config_disk_source, config.config_disk)
        vbox.attach_disk(vm_name, config.config_disk, 1)
        vbox.remove_disk(config.config_disk_source)
    except VBoxException as e:
        logging.error(e)
        raise VMException("Failed to attach config disk.")
