import platform
import os
import time
import subprocess
from ipaddress import ip_interface
import logging
import json

from yurt.exceptions import YurtException
import config


class LXCException(YurtException):
    pass


NETWORK_NAME = "yurt-int"
PROFILE_NAME = "yurt"


def getLXCExecutable():
    system = platform.system()
    if system == "Windows":
        return os.path.join(config.binDir, "lxc.exe")
    else:
        raise LXCException("Executable not found for platform")


def run(args, stdin=None):

    lxc = getLXCExecutable()
    cmd = [lxc] + args

    logging.debug(f"Running: {cmd}")

    env = dict(os.environ)
    env['HOME'] = config.configDir

    res = subprocess.run(cmd, capture_output=True,
                         text=True, env=env, input=stdin)

    try:
        res.check_returncode()
        return res.stdout
    except subprocess.CalledProcessError as e:
        logging.debug(e)
        raise LXCException(res.stderr)


def isRemoteAdded():
    result = run(["remote", "list", "--format", "json"])
    remotes = json.loads(result)
    return bool(remotes.get("yurt"))


def isNetworkConfigured():
    networks = json.loads(run(["network", "list", "--format", "json"]))
    return NETWORK_NAME in list(map(lambda n: n["name"], networks))


def isProfileConfigured():
    profiles = json.loads(run(["profile", "list", "--format", "json"]))
    return PROFILE_NAME in list(map(lambda p: p["name"], profiles))


def getIPConfig():
    hostIPAddress = config.getConfig(
        config.ConfigName.hostOnlyInterfaceIPAddress)
    networkMask = config.getConfig(
        config.ConfigName.hostOnlyInterfaceNetworkMask)
    if not (hostIPAddress and networkMask):
        raise LXCException("Bad IP Configuration. ip: {0}, mask: {1}".format(
            hostIPAddress, networkMask))

    fullHostAddress = ip_interface(
        "{0}/{1}".format(hostIPAddress, networkMask))
    bridgeAddress = ip_interface(
        "{0}/{1}".format((fullHostAddress + 1).ip, networkMask)).exploded

    return {
        "bridgeAddress": bridgeAddress,
        "dhcpRangeLow": (fullHostAddress + 10).ip.exploded,
        "dhcpRangeHigh": (fullHostAddress + 249).ip.exploded
    }


def configureNetwork():
    if isNetworkConfigured():
        print("network is defined")
        return

    ipConfig = getIPConfig()
    bridgeAddress = ipConfig["bridgeAddress"]
    dhcpRangeLow = ipConfig["dhcpRangeLow"]
    dhcpRangeHigh = ipConfig["dhcpRangeHigh"]

    run(["network", "create", NETWORK_NAME,
         "bridge.external_interfaces=enp0s8",
         "ipv6.address=none",
         "ipv4.nat=true",
         "ipv4.dhcp=true",
         "ipv4.dhcp.expiry=48h",
         f"ipv4.address={bridgeAddress}",
         f"ipv4.dhcp.ranges={dhcpRangeLow}-{dhcpRangeHigh}",
         f"dns.domain={config.applicationName}"
         ]
        )


def configureProfile():
    profileConfig = f"""name: {PROFILE_NAME}
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

    run(["profile", "create", PROFILE_NAME])
    run(["profile", "edit", PROFILE_NAME], stdin=profileConfig)


def addRemote():
    run(["remote", "add", "yurt", "localhost",
         "--password", "yurtsecret", "--accept-certificate"])
    run(["remote", "switch", "yurt"])
