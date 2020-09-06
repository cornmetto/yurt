import logging
from typing import List
import os

import config

from yurt.exceptions import LXCException, YurtCalledProcessException
from yurt.util import retry, find
from .util import *  # pylint: disable=unused-wildcard-import


def ensure_setup_is_complete():
    # Usually called immediately after boot. Retry a few times before giving up.
    logging.info("Making sure LXD is ready...")

    def run_setup_operations():
        if not is_remote_configured():
            configure_remote()
        if not is_network_configured():
            configure_network()
        if not is_profile_configured():
            configure_profile()

    retry(run_setup_operations, retries=6, wait_time=5)


def destroy():
    import shutil

    lxc_config_dir = os.path.join(config.config_dir, ".config", "lxc")
    shutil.rmtree(lxc_config_dir, ignore_errors=True)


def list_():
    import json

    def get_info(instance):
        try:
            addresses = instance["state"]["network"]["eth0"]["addresses"]
            ipv4_info = find(lambda a: a["family"] == "inet", addresses, {})
            ipv4_address = ipv4_info.get("address", "")
        except KeyError as e:
            logging.debug(f"Key Error: {e}")
            ipv4_address = ""
        except TypeError:
            ipv4_address = ""

        instance_config = instance["config"]
        architecture = instance_config.get("image.architecture", "")
        os_ = instance_config.get("image.os", "")
        release = instance_config.get("image.release", "")

        return {
            "Name": instance["name"],
            "Status": instance["state"]["status"],
            "IP Address": ipv4_address,
            "Image": f"{os_}/{release} ({architecture})"

        }
    try:
        output = run_lxc(["list", "--format", "json"], show_spinner=True)
        instances = json.loads(output)
        return list(map(get_info, instances))
    except YurtCalledProcessException as e:
        raise LXCException(f"Failed to list networks: {e.message}")


def start(names: List[str]):
    cmd = ['start'] + names
    return run_lxc(cmd, show_spinner=True)


def stop(names: List[str], force=False):
    cmd = ["stop"] + names
    if force:
        cmd.append("--force")
    return run_lxc(cmd, show_spinner=True)


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
             f"--profile={PROFILE_NAME}"], capture_output=False)


def shell(instance: str):
    run_lxc([
        "exec", instance,
        "--env", r"PS1=\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\] \# ",
        "--", "su", "root"],
        capture_output=False)