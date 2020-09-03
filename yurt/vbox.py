import os
import logging
import re
from typing import Dict, List

import config
from config import ConfigName

from yurt.util import is_ssh_available, run, YurtCalledProcessException
from yurt.exceptions import VBoxException


def import_vm(vm_name: str, appliance_file: str, base_folder):
    settings_file = os.path.join(base_folder, "{}.vbox".format(vm_name))
    memory = 1024

    cmd = [
        "import", appliance_file,
        "--options", "keepnatmacs",
        "--vsys", "0", "--vmname", vm_name,
        "--vsys", "0", "--settingsfile", settings_file,
        "--vsys", "0", "--basefolder", base_folder,
        "--vsys", "0", "--memory", str(memory),
    ]

    run_vbox(cmd, show_spinner=True)


def modify_vm(vm_name: str, settings: Dict[str, str]):
    options = []
    for k, v in settings.items():
        options.append(f"--{k}")
        options.append(v)

    cmd = ["modifyvm", vm_name] + options
    run_vbox(cmd)


def list_vms():
    def parse_line(line):
        match = re.search(r'"(.*)" \{(.*)\}', line)
        return match.groups()

    output = run_vbox(["list",  "vms"])
    return list(map(parse_line, output.splitlines()))


def get_vm_info(vm_name: str):
    cmd = ["showvminfo", vm_name, "--machinereadable"]
    output = run_vbox(cmd)
    info_list = map(lambda l: l.split("=", 1), output.splitlines())
    return dict(info_list)


def start_vm(vm_name: str):
    cmd = ["startvm", vm_name, "--type", "headless"]
    run_vbox(cmd, show_spinner=True)


def stop_vm(vm_name: str):
    cmd = ["controlvm", vm_name, "acpipowerbutton"]
    run_vbox(cmd)


def setup_ssh_port_forwarding(vm_name: str):
    current_port = config.getConfig(ConfigName.hostSSHPort)
    return _setup_port_forwarding(vm_name, "ssh", current_port, 22, is_ssh_available)


def _setup_port_forwarding(
    vm_name: str,
    rule_name: str,
    initial_host_port: int,
    guest_port: int,
    is_service_available_on_port
):
    import time
    import random

    retry_count, retry_wait_time = (5, 7)
    low_port, high_port = (4000, 4099)
    host_port = initial_host_port or low_port
    connected = is_service_available_on_port(host_port)

    while (retry_count > 0) and not connected:
        add_rule_cmd = ["controlvm", vm_name, "natpf1",
                        f"{rule_name},tcp,,{host_port},,{guest_port}"]
        remove_rule_cmd = ["controlvm", vm_name, "natpf1", "delete", rule_name]

        logging.info(
            f"Attempting to set up {rule_name} on port {host_port}...")
        logging.debug(
            "Setting up forwarding {0},{1}:{2} ...".format(rule_name, host_port, guest_port))
        try:
            run_vbox(remove_rule_cmd)
        except:
            pass

        try:
            run_vbox(add_rule_cmd)
        except VBoxException:
            raise VBoxException(
                "An error occurred while setting up SSH")

        time.sleep(2)
        connected = is_service_available_on_port(host_port)
        if not connected:
            retry_count -= 1
            time.sleep(retry_wait_time)
            host_port = random.randrange(low_port, high_port)

    if connected:
        return host_port
    else:
        raise VBoxException(
            "Set up SSH forwarding but service in guest does not appear to be available.")


def list_host_only_interfaces():
    def get_iface_name(line):
        match = re.search(r"^Name: +(.*)", line)
        if match:
            return match.group(1)

    interfaces = map(
        get_iface_name,
        run_vbox(["list", "hostonlyifs"]).splitlines()
    )
    return list(filter(None, interfaces))


def get_interface_info(interface_name: str):
    lines = run_vbox(["list", "hostonlyifs"]).splitlines()

    interface_info: Dict[str, str] = {}
    processing_interface_values = False
    for line in lines:
        match = re.search(r"^Name: +{}$".format(interface_name), line)
        if match:
            processing_interface_values = True

        try:
            if processing_interface_values:
                if len(line) == 0:
                    return interface_info
                key, value = line.split(":", 1)
                key, value = key.strip(), value.strip()
                interface_info[key] = value

        except ValueError as e:
            logging.error(
                "Error processing line {0}: {1}".format(line, e))
            raise VBoxException(
                "Unexpected result from 'list hostonlyifs'")

    raise VBoxException(
        "Interface {} not found".format(interface_name))


def create_hostonly_interface():
    old_interfaces = set(list_host_only_interfaces())
    run_vbox(["hostonlyif", "create"])
    new_interfaces = set(list_host_only_interfaces())
    try:
        return new_interfaces.difference(old_interfaces).pop()
    except KeyError:
        logging.error("Host-Only interface not properly initialized")


def remove_hostonly_interface(interface_name: str):
    run_vbox(["hostonlyif", "remove", f"{interface_name}"])


def destroy_vm(vm_name: str):
    run_vbox(["unregistervm", "--delete", vm_name])


def get_vboxmanage_path_windows():
    base_dirs = []

    environment_dirs = os.environ.get('VBOX_INSTALL_PATH') \
        or os.environ.get('VBOX_MSI_INSTALL_PATH')

    if environment_dirs:
        base_dirs.extend(environment_dirs.split(';'))

    # Other possible locations.
    base_dirs.extend([
        os.path.expandvars(
            r'${SYSTEMDRIVE}\Program Files\Oracle\VirtualBox'),
        os.path.expandvars(
            r'${SYSTEMDRIVE}\Program Files (x86)\Oracle\VirtualBox'),
        os.path.expandvars(r'${PROGRAMFILES}\Oracle\VirtualBox')
    ])

    for base_dir in base_dirs:
        path = os.path.join(base_dir, "VBoxManage.exe")
        if os.path.exists(path):
            return path


def run_vbox(args: List[str], **kwargs):
    """
    See yurt.util.run for **kwargs documentation.
    """

    executable = get_vboxmanage_path_windows()
    cmd = [executable, "-q"] + args

    try:
        return run(cmd, **kwargs)
    except YurtCalledProcessException as e:
        raise VBoxException(e.message)
