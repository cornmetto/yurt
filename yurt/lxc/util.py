import json
import logging
import os
from typing import List, Dict
import pylxd

from yurt import config
from yurt.exceptions import LXCException, RemoteCommandException
from yurt.util import run, run_in_vm, find


NETWORK_NAME = "yurt-int"
PROFILE_NAME = "yurt"
REMOTES = [
    {
        "Name": "images",
        "URL": "https://images.linuxcontainers.org",
    },
    {
        "Name": "ubuntu",
        "URL": "https://cloud-images.ubuntu.com/releases",
    },
]


def get_pylxd_client(port: int):
    return pylxd.Client(endpoint=f"http://127.0.0.1:{port}")


def get_lxc_executable():
    if config.system == config.System.windows:
        lxc_executable = os.path.join(config.bin_dir, "lxc.exe")
        if os.path.isfile(lxc_executable):
            return lxc_executable
        else:
            raise LXCException(
                f"{lxc_executable} does not exist.")
    else:
        raise LXCException(
            f"LXC executable not found for platform: {config.system}")


def is_initialized():
    return config.get_config(config.Key.is_lxd_initialized)


def is_remote_configured():
    result = run_lxc(["remote", "list", "--format", "json"])
    remotes = json.loads(result)
    return bool(remotes.get("yurt"))


def is_network_configured():
    networks = json.loads(run_lxc(["network", "list", "--format", "json"]))
    return NETWORK_NAME in list(map(lambda n: n["name"], networks))


def is_profile_configured():
    profiles = json.loads(run_lxc(["profile", "list", "--format", "json"]))
    return PROFILE_NAME in list(map(lambda p: p["name"], profiles))


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


def initialize_lxd():
    lxd_init = """config:
  core.https_address: '[::]:8443'
  core.trust_password: yurtsecret
networks: []
storage_pools:
- config:
    source: /dev/sdc
  description: ""
  name: yurtpool
  driver: zfs
profiles:
- config: {}
  description: ""
  devices:
    root:
      path: /
      pool: yurtpool
      type: disk
  name: default
cluster: null
    """

    try:
        logging.info("Installing LXD. This might take a few minutes...")
        run_in_vm("sudo snap install lxd", show_spinner=True)
        logging.info("LXD installed. Configuring...")

        run_in_vm("sudo lxd.migrate -yes", show_spinner=True)
        run_in_vm(
            "sudo lxd init --preseed",
            stdin=lxd_init,
            show_spinner=True
        )
        logging.info("Done.")
        config.set_config(config.Key.is_lxd_initialized, True)
    except RemoteCommandException as e:
        logging.error(e)
        logging.info("Restart the VM to try again: 'yurt shutdown; yurt boot'")
        raise LXCException("Failed to initialize LXD.")


def configure_network():
    if is_network_configured():
        print("network is defined")
        return

    ip_config = get_ip_config()
    bridge_address = ip_config["bridgeAddress"]
    dhcp_range_low = ip_config["dhcpRangeLow"]
    dhcp_range_high = ip_config["dhcpRangeHigh"]

    run_lxc(["network", "create", NETWORK_NAME,
             "bridge.external_interfaces=enp0s8",
             "ipv6.address=none",
             "ipv4.nat=true",
             "ipv4.dhcp=true",
             "ipv4.dhcp.expiry=24h",
             f"ipv4.address={bridge_address}",
             f"ipv4.dhcp.ranges={dhcp_range_low}-{dhcp_range_high}",
             f"dns.domain={config.app_name}"
             ]
            )


def configure_profile():
    profile_config = f"""name: {PROFILE_NAME}
config: {{}}
description: Yurt Default Profile
devices:
    eth0:
        name: eth0
        nictype: bridged
        parent: {NETWORK_NAME}
        type: nic
    root:
        path: /
        pool: yurtpool
        type: disk"""

    run_lxc(["profile", "create", PROFILE_NAME])
    run_lxc(["profile", "edit", PROFILE_NAME], stdin=profile_config)


def configure_remote():
    run_lxc(["remote", "add", "yurt", "localhost",
             "--password", "yurtsecret", "--accept-certificate"])
    run_lxc(["remote", "switch", "yurt"])


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


def get_cached_image_info(image: Dict):
    try:
        alias = image["update_source"]["alias"]
        server = image["update_source"]["server"]
        remote = find(lambda r: r["URL"] == server, REMOTES, None)

        if remote:
            source = f"{remote['Name']}:{alias}"
        else:
            raise LXCException("Unexpected source server: {}")

        return {
            "Alias": source,
            "Description": image["properties"]["description"]
        }

    except KeyError as e:
        logging.debug(e)
        logging.debug(f"Unexpected image schema: {image}")


def run_lxc(args: List[str], **kwargs):
    """
    See yurt.util.run for **kwargs documentation.
    """

    lxc = get_lxc_executable()
    cmd = [lxc] + args

    lxc_env = {
        "HOME": config.config_dir
    }

    return run(cmd, env=lxc_env, **kwargs)
