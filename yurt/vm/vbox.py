import os
import logging
import re
from typing import Dict, List

from yurt.util import is_ssh_available, run, CommandException
from yurt.exceptions import VBoxException


def import_vm(vm_name: str, appliance_file: str, base_folder, memory):
    settings_file = os.path.join(base_folder, "{}.vbox".format(vm_name))

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


def attach_serial_console(vm_name: str, console_file_path: str):
    run_vbox(["modifyvm", vm_name, "--uart1", "0x3F8", "4"])
    run_vbox(["modifyvm", vm_name, "--uartmode1", "file", console_file_path])


def start_vm(vm_name: str):
    cmd = ["startvm", vm_name, "--type", "headless"]
    run_vbox(cmd, show_spinner=True)


def stop_vm(vm_name: str, force=False):
    if force:
        cmd = ["controlvm", vm_name, "poweroff"]
    else:
        cmd = ["controlvm", vm_name, "acpipowerbutton"]

    run_vbox(cmd)


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
    if interface_name:
        run_vbox(["hostonlyif", "remove", f"{interface_name}"])
    else:
        logging.debug(
            "vbox.remove_hostonly_interface: Unexpected interface_name 'None'")


def create_disk(file_name: str, size_mb: int):
    run_vbox(
        [
            "createmedium", "disk",
            "--filename", file_name,
            "--size", str(size_mb),
            "--format", "VMDK",
        ]
    )


def attach_disk(vm_name: str, file_name: str, port: int):
    run_vbox(
        [
            "storageattach", vm_name,
            "--storagectl", "SCSI",
            "--medium", file_name,
            "--port", str(port),
            "--type", "hdd"
        ]
    )


def clone_disk(src: str, dst: str):
    run_vbox(["clonemedium", src, dst])


def destroy_vm(vm_name: str):
    if vm_name:
        run_vbox(["unregistervm", "--delete", vm_name])
    else:
        logging.debug("vbox.destroy_vm: Unexpected vm_name 'None'.")


def get_vboxmanage_executable_windows():
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
        else:
            raise VBoxException("VBoxManage executable not found")


def get_vboxmanage_executable():
    from yurt import config

    if config.platform == "windows":
        return get_vboxmanage_executable_windows()
    else:
        raise VBoxException(f"Platform {config.platform} not supported")


def run_vbox(args: List[str], **kwargs):
    """
    See yurt.util.run for **kwargs documentation.
    """

    executable = get_vboxmanage_executable()
    cmd = [executable, "-q"] + args

    try:
        return run(cmd, **kwargs)
    except CommandException as e:
        raise VBoxException(e.message)


def setup_lxd_port_forwarding(vm_name: str):
    try:
        run_vbox(["controlvm", vm_name, "natpf1", "lxd,tcp,,8443,,8443"])
    except VBoxException as e:
        logging.debug(e)


def setup_ssh_port_forwarding(
    vm_name: str,
    initial_host_port: int,
):
    import time
    import random

    rule_name = "ssh"
    guest_port = 22
    retry_count, retry_wait_time = (5, 7)
    low_port, high_port = (4000, 4099)
    host_port = initial_host_port or low_port
    connected = is_ssh_available(host_port)

    while (retry_count > 0) and not connected:
        add_rule_cmd = ["controlvm", vm_name, "natpf1",
                        f"{rule_name},tcp,,{host_port},,{guest_port}"]
        remove_rule_cmd = ["controlvm", vm_name, "natpf1", "delete", rule_name]

        logging.debug(
            f"Setting up forwarding rule: {rule_name},{host_port}:{guest_port} ...")
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
        connected = is_ssh_available(host_port)
        if not connected:
            retry_count -= 1
            logging.info(f"Waiting for {rule_name}...")
            time.sleep(retry_wait_time)
            host_port = random.randrange(low_port, high_port)

    if connected:
        return host_port
    else:
        raise VBoxException(
            f"Set up {rule_name} forwarding but service does not appear to be available.")
