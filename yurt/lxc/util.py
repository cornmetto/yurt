import platform
import os
import time
from ipaddress import ip_interface
import logging
import json
from typing import List

from yurt.exceptions import LXCException
from yurt.util import run
import config


NETWORK_NAME = "yurt-int"
PROFILE_NAME = "yurt"


def get_lxc_executable():
    system = platform.system()
    if system == "Windows":
        return os.path.join(config.bin_dir, "lxc.exe")
    else:
        raise LXCException("Executable not found for platform")


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
        pool: yurt
        type: disk"""

    run_lxc(["profile", "create", PROFILE_NAME])
    run_lxc(["profile", "edit", PROFILE_NAME], stdin=profile_config)


def configure_remote():
    run_lxc(["remote", "add", "yurt", "localhost",
             "--password", "yurtsecret", "--accept-certificate"])
    run_lxc(["remote", "switch", "yurt"])


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
