import logging
import os
from typing import List, Dict
import pylxd

from yurt import config
from yurt.exceptions import LXCException, RemoteCommandException
from yurt.util import run, run_in_vm, put_file, find


NETWORK_NAME = "yurt-int"
PROFILE_NAME = "yurt"
REMOTES = {
    "images": {
        "Name": "images",
        "URL": "https://images.linuxcontainers.org",
    },
    "ubuntu": {
        "Name": "ubuntu",
        "URL": "https://cloud-images.ubuntu.com/releases",
    },
}


def get_pylxd_client(port: int = None):
    if not port:
        port = config.lxd_port
    try:
        return pylxd.Client(endpoint=f"http://127.0.0.1:{port}")
    except pylxd.exceptions.ClientConnectionFailed as e:
        logging.debug(e)
        raise LXCException(
            "Error connecting to LXD. Try rebooting the VM: 'yurt reboot'")


def get_instance(name: str):
    client = get_pylxd_client()
    try:
        return client.instances.get(name)  # pylint: disable=no-member
    except pylxd.exceptions.NotFound:
        raise LXCException(f"Instance {name} not found.")
    except pylxd.exceptions.LXDAPIException:
        raise LXCException(
            f"Could not fetch instance {name}. API Error.")


def is_initialized():
    return config.get_config(config.Key.is_lxd_initialized)


def get_ip_config():
    from ipaddress import ip_interface

    host_ip_address = config.get_config(
        config.Key.interface_ip_address)
    network_mask = config.get_config(
        config.Key.interface_netmask)
    if not (host_ip_address and network_mask):
        raise LXCException("Bad IP Configuration. ip: {0}, mask: {1}".format(
            host_ip_address, network_mask))

    full_host_address = ip_interface(
        "{0}/{1}".format(host_ip_address, network_mask))
    bridge_address = ip_interface(
        "{0}/{1}".format((full_host_address + 1).ip, network_mask)).exploded

    return {
        "bridgeAddress": bridge_address,
        "dhcpRangeLow": (full_host_address + 10).ip.exploded,
        "dhcpRangeHigh": (full_host_address + 249).ip.exploded
    }


def _setup_yurt_socat():
    name = "yurt-lxd-socat"
    run_in_vm("mkdir -p /tmp/yurt")
    tmp_unit_file = f"/tmp/yurt/{name}.service"
    installed_unit_file = f"/etc/systemd/system/{name}.service"
    run_in_vm("sudo apt install socat -y")
    put_file(os.path.join(config.provision_dir,
                          f"{name}.service"), tmp_unit_file)
    run_in_vm(f"sudo cp {tmp_unit_file} {installed_unit_file}")
    run_in_vm("sudo systemctl daemon-reload")
    run_in_vm(f"sudo systemctl enable {name}")
    run_in_vm(f"sudo systemctl start {name}")


def initialize_lxd():
    if is_initialized():
        return

    try:
        with open(os.path.join(config.provision_dir, "lxd-init.yaml"), "r") as f:
            init = f.read()
    except OSError as e:
        raise LXCException(f"Error reading lxd-init.yaml {e}")

    try:
        logging.info("Updating package information...")
        run_in_vm("sudo apt update", show_spinner=True)
        run_in_vm("sudo usermod yurt -a -G lxd")

        logging.info("Initializing LXD...")
        run_in_vm(
            "sudo lxd init --preseed",
            stdin=init,
            show_spinner=True
        )
        _setup_yurt_socat()

        logging.info("Done.")
        config.set_config(config.Key.is_lxd_initialized, True)
    except RemoteCommandException as e:
        logging.error(e)
        logging.info("Restart the VM to try again: 'yurt reboot'")
        raise LXCException("Failed to initialize LXD.")


def configure_network():
    client = get_pylxd_client()
    if client.networks.exists(NETWORK_NAME):  # pylint: disable=no-member
        return

    logging.info("Configuring network...")
    ip_config = get_ip_config()
    bridge_address = ip_config["bridgeAddress"]
    dhcp_range_low = ip_config["dhcpRangeLow"]
    dhcp_range_high = ip_config["dhcpRangeHigh"]

    client.networks.create(  # pylint: disable=no-member
        NETWORK_NAME, description="Yurt Network", type="bridge",
        config={
            "bridge.external_interfaces": "enp0s8",
            "ipv6.address": "none",
            "ipv4.nat": "true",
            "ipv4.dhcp": "true",
            "ipv4.dhcp.expiry": "24h",
            "ipv4.address": bridge_address,
            "ipv4.dhcp.ranges": f"{dhcp_range_low}-{dhcp_range_high}",
            "dns.domain": config.app_name
        })


def configure_profile():
    client = get_pylxd_client()
    if client.profiles.exists(PROFILE_NAME):  # pylint: disable=no-member
        return

    logging.info("Configuring profile...")
    client.profiles.create(  # pylint: disable=no-member
        PROFILE_NAME,
        devices={
            "eth0": {
                "name": "eth0",
                "nictype": "bridged",
                "parent": NETWORK_NAME,
                "type": "nic"
            },
            "root": {
                "type": "disk",
                "pool": "yurtpool",
                "path": "/"
            }
        }
    )


def shortest_alias(aliases: List[Dict[str, str]], remote: str):
    import re

    aliases = list(map(lambda a: str(a["name"]), aliases))
    if remote == "ubuntu":
        aliases = list(filter(lambda a: re.match(
            r"^\d\d\.\d\d", a), aliases))

    try:
        alias = aliases[0]
        for a in aliases:
            if len(a) < len(alias):
                alias = a
        return alias
    except (IndexError, KeyError) as e:
        logging.debug(e)
        logging.error(f"Unexpected alias schema: {aliases}")


def filter_remote_images(images: List[Dict]):
    aliased = filter(lambda i: i["aliases"],  images)
    container = filter(
        lambda i: i["type"] == "container", aliased)
    x64 = filter(
        lambda i: i["architecture"] == "x86_64", container)

    return x64


def get_remote_image_info(remote: str, image: Dict):
    try:
        return {
            "Alias": shortest_alias(image["aliases"], remote),
            "Description": image["properties"]["description"]
        }
    except KeyError as e:
        logging.debug(e)
        logging.debug(f"Unexpected image schema: {image}")


def exec_interactive(instance_name: str, cmd: List[str]):
    from yurt.lxc import term

    instance = get_instance(instance_name)
    response = instance.raw_interactive_execute(cmd)
    try:

        ws_url = f"ws://127.0.0.1:{config.lxd_port}{response['ws']}"
        term.run(ws_url)
    except KeyError as e:
        raise LXCException(f"Missing ws URL {e}")
