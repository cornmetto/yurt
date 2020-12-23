import logging
from typing import List
import os
from pylxd.exceptions import LXDAPIException

from yurt import config
from yurt.exceptions import LXCException, CommandException
from yurt.util import retry, find
from .util import *  # pylint: disable=unused-wildcard-import


def configure_lxd():
    initialize_lxd()

    def check_config():
        configure_network()
        configure_profile()

    retry(check_config, retries=10, wait_time=6)


def destroy():
    import shutil

    lxc_config_dir = os.path.join(config.config_dir, ".config", "lxc")
    shutil.rmtree(lxc_config_dir, ignore_errors=True)


def list_():
    def get_ipv4_address(instance):
        ipv4_address = ""

        state = instance.state()
        if state.network:
            try:
                addresses = state.network["eth0"]["addresses"]
                ipv4_info = find(
                    lambda a: a["family"] == "inet", addresses, {})
                ipv4_address = ipv4_info.get("address", "")
            except KeyError as e:
                logging.debug(f"Missing instance data: {e}")

        return ipv4_address

    def get_image(instance):
        config = instance.config
        try:
            arch, os_, release = config['image.architecture'], config['image.os'], config['image.release']
            return f"{os_}/{release} ({arch})"
        except KeyError as e:
            logging.error(e)
            return ""

    client = get_pylxd_client()
    instances = []
    for instance in client.instances.all():  # pylint: disable=no-member
        instances.append({
            "Name": instance.name,
            "Status": instance.status,
            "IP Address": get_ipv4_address(instance),
            "Image": get_image(instance)
        })

    return instances


def start(names: List[str]):
    for name in names:
        instance = get_instance(name)
        try:
            instance.start()
        except LXDAPIException as e:
            raise LXCException(f"Error starting instance: {e}")


def stop(names: List[str], force=False):
    for name in names:
        instance = get_instance(name)
        try:
            instance.stop()
        except LXDAPIException as e:
            raise LXCException(f"Error stopping instance: {e}")


def delete(names: List[str], force=False):
    for name in names:
        instance = get_instance(name)
        try:
            instance.delete()
        except LXDAPIException as e:
            raise LXCException(f"Error deleting instance: {e}")


def launch(remote: str, image: str, name: str):
    # https://linuxcontainers.org/lxd/docs/master/instances
    # Valid instance names must:
    #   - Be between 1 and 63 characters long
    #   - Be made up exclusively of letters, numbers and dashes from the ASCII table
    #   - Not start with a digit or a dash
    #   - Not end with a dash

    client = get_pylxd_client()
    try:
        server_url = REMOTES[remote]["URL"]
    except KeyError:
        raise LXCException(f"Unsupported remote {remote}")

    try:
        logging.info(f"Launching {name}. This might take a few minutes...")
        client.instances.create({  # pylint: disable=no-member
            "name": name,
            "source": {
                "type": "image",
                "alias": image,
                "mode": "pull",
                "server": server_url,
                "protocol": "simplestreams"
            }
        },
            wait=True
        )

    except LXDAPIException as e:
        logging.error(e)
        raise LXCException(f"Failed to launch instance {name}")


def shell(instance: str):
    run_lxc([
        "exec", instance,
        "--env", r"PS1=\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\] \# ",
        "--", "su", "root"],
        capture_output=False)


def exec_(instance: str, exec_cmd: List[str]):
    if exec_cmd:
        cmd = ["exec", instance, "--"]
        cmd.extend(exec_cmd)
        run_lxc(cmd, capture_output=False)


def list_remote_images(remote: str):
    from functools import partial

    try:
        output = run_lxc(["image", "list", f"{remote}:",
                          "--format", "json"], show_spinner=True)

        images = filter_remote_images(json.loads(output))

        images_info = filter(
            None,
            map(partial(get_remote_image_info, remote), images)
        )

        if remote == "ubuntu":
            return sorted(images_info, key=lambda i: i["Alias"], reverse=True)
        else:
            return sorted(images_info, key=lambda i: i["Alias"])

    except CommandException as e:
        raise LXCException(f"Could not fetch images: {e.message}")


def list_cached_images():
    try:
        output = run_lxc(["image", "list", "yurt:",
                          "--format", "json"], show_spinner=True)

        images_info = filter(
            None, map(get_cached_image_info, json.loads(output)))
        return list(images_info)
    except CommandException as e:
        raise LXCException(f"Could not fetch images - {e.message}")
