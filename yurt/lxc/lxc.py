import logging
import os
from typing import List

import config
from config import ConfigName

from yurt.exceptions import LXCException, YurtCalledProcessException
from yurt.lxc.util import *  # pylint: disable=unused-wildcard-import
from yurt.util import retry, find


def ensureSetupIsComplete():
    # Usually called immediately after boot. Retry a few times before giving up.
    logging.info("Making sure LXD is ready...")

    def runSetupOperations():
        if not isRemoteAdded():
            addRemote()
        if not isNetworkConfigured():
            configureNetwork()
        if not isProfileConfigured():
            configureProfile()

    retries, waitTime = 4, 5
    retry(runSetupOperations, retries, waitTime)


def destroy():
    lxcConfigDir = os.path.join(config.configDir, ".config", "lxc")

    import shutil
    shutil.rmtree(lxcConfigDir, ignore_errors=True)


def list_():
    import json

    def getInfo(instance):
        try:
            addresses = instance["state"]["network"]["eth0"]["addresses"]
            ipv4Info = find(lambda a: a["family"] == "inet", addresses, {})
            ipv4Address = ipv4Info.get("address", "")
        except KeyError as e:
            logging.debug(f"Key Error: {e}")
            ipv4Address = ""
        except TypeError:
            ipv4Address = ""

        instanceConfig = instance["config"]
        architecture = instanceConfig.get("image.architecture", "")
        os_ = instanceConfig.get("image.os", "")
        release = instanceConfig.get("image.release", "")

        return {
            "Name": instance["name"],
            "Status": instance["state"]["status"],
            "IP Address": ipv4Address,
            "Image": f"{os_}/{release} ({architecture})"

        }
    try:
        output = run_lxc(["list", "--format", "json"], show_spinner=True)
        instances = json.loads(output)
        return list(map(getInfo, instances))
    except YurtCalledProcessException as e:
        raise LXCException(f"Failed to list networks: {e.message}")


def start(names: List[str]):
    cmd = ['start'] + names
    return run_lxc(cmd)


def stop(names: List[str], force=False):
    cmd = ["stop"] + names
    if force:
        cmd.append("--force")
    return run_lxc(cmd)


def delete(names: List[str], force=False):
    cmd = ["delete"] + names
    if force:
        cmd.append("--force")
    return run_lxc(cmd)


def info(name: str):
    return run_lxc(["info", name])


def launch(image: str, name: str):
    # https://linuxcontainers.org/lxd/docs/master/instances
    # Valid instance names must:
    #   - Be between 1 and 63 characters long
    #   - Be made up exclusively of letters, numbers and dashes from the ASCII table
    #   - Not start with a digit or a dash
    #   - Not end with a dash

    logging.info("This might take a few minutes...")
    run_lxc(["launch", image, name,
             "--profile=default",
             f"--profile={PROFILE_NAME}"], capture_output=False, timeout=None)
