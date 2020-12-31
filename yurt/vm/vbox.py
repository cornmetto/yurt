import os
import logging
import re
from typing import Dict, List

from yurt import config
from yurt import util as yurt_util
from yurt.exceptions import VBoxException, CommandException


def _get_vboxmanage_executable_windows():
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

    raise VBoxException("VBoxManage executable not found")


def _get_vboxmanage_executable():
    if config.system == config.System.windows:
        return _get_vboxmanage_executable_windows()
    else:
        # Issue #2: Support for MacOS.
        raise VBoxException(f"Platform {config.system} not supported")


def _run_vbox(args: List[str], **kwargs):
    """
    See yurt.util.run for **kwargs documentation.
    """

    executable = _get_vboxmanage_executable()
    cmd = [executable, "-q"] + args

    try:
        return yurt_util.run(cmd, **kwargs)
    except CommandException as e:
        raise VBoxException(e.message)


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

    _run_vbox(cmd, show_spinner=True)


def modify_vm(vm_name: str, settings: Dict[str, str]):
    options = []
    for k, v in settings.items():
        options.append(f"--{k}")
        options.append(v)

    cmd = ["modifyvm", vm_name] + options
    _run_vbox(cmd)


def list_vms():
    def parse_line(line):
        match = re.search(r'"(.*)" \{(.*)\}', line)
        return match.groups()

    output = _run_vbox(["list",  "vms"])
    return list(map(parse_line, output.splitlines()))


def get_vm_info(vm_name: str):
    cmd = ["showvminfo", vm_name, "--machinereadable"]
    output = _run_vbox(cmd)
    info_list = map(lambda l: l.split("=", 1), output.splitlines())
    return dict(info_list)


def attach_serial_console(vm_name: str, console_file_path: str):
    _run_vbox(["modifyvm", vm_name, "--uart1", "0x3F8", "4"])
    _run_vbox(["modifyvm", vm_name, "--uartmode1", "file", console_file_path])


def start_vm(vm_name: str):
    cmd = ["startvm", vm_name, "--type", "headless"]
    _run_vbox(cmd, show_spinner=True)


def stop_vm(vm_name: str, force=False):
    if force:
        cmd = ["controlvm", vm_name, "poweroff"]
    else:
        cmd = ["controlvm", vm_name, "acpipowerbutton"]

    _run_vbox(cmd)


def list_host_only_interfaces():
    def get_iface_name(line):
        match = re.search(r"^Name: +(.*)", line)
        if match:
            return match.group(1)

    interfaces = map(
        get_iface_name,
        _run_vbox(["list", "hostonlyifs"]).splitlines()
    )
    return list(filter(None, interfaces))


def get_interface_info(interface_name: str):
    lines = _run_vbox(["list", "hostonlyifs"]).splitlines()

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
    _run_vbox(["hostonlyif", "create"])
    new_interfaces = set(list_host_only_interfaces())
    try:
        return new_interfaces.difference(old_interfaces).pop()
    except KeyError:
        logging.error("Host-Only interface not properly initialized")


def remove_hostonly_interface(interface_name: str):
    if interface_name:
        _run_vbox(["hostonlyif", "remove", f"{interface_name}"])
    else:
        logging.debug(
            "vbox.remove_hostonly_interface: Unexpected interface_name 'None'")


def create_disk(file_name: str, size_mb: int):
    _run_vbox(
        [
            "createmedium", "disk",
            "--filename", file_name,
            "--size", str(size_mb),
            "--format", "VMDK",
        ]
    )


def attach_disk(vm_name: str, file_name: str, port: int):
    _run_vbox(
        [
            "storageattach", vm_name,
            "--storagectl", "SCSI",
            "--medium", file_name,
            "--port", str(port),
            "--type", "hdd"
        ]
    )


def clone_disk(src: str, dst: str):
    _run_vbox(["clonemedium", src, dst])


def remove_disk(path: str, delete: bool = False):
    cmd = ["closemedium", "disk", path]

    if delete:
        cmd.append("--delete")
    _run_vbox(cmd)


def destroy_vm(vm_name: str):
    if vm_name:
        _run_vbox(["unregistervm", "--delete", vm_name])
    else:
        logging.debug("vbox.destroy_vm: Unexpected vm_name 'None'.")


def setup_port_forwarding(
    vm_name: str,
    rule_name: str,
    host_port: int,
    guest_port: int
):

    try:
        _run_vbox(["controlvm", vm_name, "natpf1", "delete", rule_name])
    except:
        pass

    rule = f"{rule_name},tcp,,{host_port},,{guest_port}"
    _run_vbox(["controlvm", vm_name, "natpf1", rule])
