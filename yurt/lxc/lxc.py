import logging
from typing import List
from pylxd.exceptions import LXDAPIException

from yurt.exceptions import LXCException, VMException
from yurt import vm
from yurt import util as yurt_util
from . import util


def ensure_is_ready():
    yurt_util.retry(
        util.initialize_lxd,
        retries=3, wait_time=3,
        message="LXD init failed. Retrying..."
    )

    # wait for LXD to be available
    yurt_util.retry(
        util.get_pylxd_client,
        retries=3, wait_time=3,
        message="LXD is not yet available. Retrying..."
    )
    util.check_network_config()
    util.check_profile_config()


def list_():
    def get_ipv4_address(instance):
        ipv4_address = ""

        state = instance.state()
        if state.network:
            try:
                addresses = state.network["eth0"]["addresses"]
                ipv4_info = yurt_util.find(
                    lambda a: a["family"] == "inet", addresses, {}
                )
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

    client = util.get_pylxd_client()
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
        instance = util.get_instance(name)
        try:
            instance.start(wait=True)
        except LXDAPIException as e:
            raise LXCException(f"Error starting instance: {e}")


def stop(names: List[str]):
    for name in names:
        instance = util.get_instance(name)
        try:
            instance.stop(wait=True)
        except LXDAPIException as e:
            raise LXCException(f"Error stopping instance: {e}")


def delete(names: List[str]):
    for name in names:
        instance = util.get_instance(name)
        try:
            instance.delete(wait=True)
        except LXDAPIException as e:
            raise LXCException(f"Error deleting instance: {e}")


def launch(remote: str, image: str, name: str):
    # https://linuxcontainers.org/lxd/docs/master/instances
    # Valid instance names must:
    #   - Be between 1 and 63 characters long
    #   - Be made up exclusively of letters, numbers and dashes from the ASCII table
    #   - Not start with a digit or a dash
    #   - Not end with a dash

    client = util.get_pylxd_client()
    try:
        server_url = util.REMOTES[remote]["URL"]
    except KeyError:
        raise LXCException(f"Unsupported remote {remote}")

    try:
        logging.info(
            f"Launching container '{name}'. This might take a few minutes...")
        response = client.api.instances.post(json={
            "name": name,
            "profiles": [util.PROFILE_NAME],
            "source": {
                "type": "image",
                "alias": image,
                "mode": "pull",
                "server": server_url,
                "protocol": "simplestreams"
            }
        })

        util.follow_operation(
            response.json()["operation"],
            unpack_metadata=util.unpack_download_operation_metadata
        )

        logging.info(f"Starting container")
        instance = util.get_instance(name)
        instance.start(wait=True)
    except LXDAPIException as e:
        logging.error(e)
        raise LXCException(f"Failed to launch instance {name}")


def exec_(instance_name: str, cmd: List[str]):
    instance = util.get_instance(instance_name)
    return instance.execute(cmd)


def shell(instance_name: str):
    util.exec_interactive(instance_name, ["su", "root"])


def list_remote_images(remote: str):
    from functools import partial
    import json

    try:
        # We'd have to implement simplestreams ourselves as this call is handled
        # entirely by the client. Let's cheat.
        output, error = vm.run_cmd(
            f"lxc image list {remote}: --format json", show_spinner=True)
        if error:
            logging.error(error)

        images = util.filter_remote_images(json.loads(output))

        images_info = filter(
            None,
            map(partial(util.get_remote_image_info, remote), images)
        )

        if remote == "ubuntu":
            return sorted(images_info, key=lambda i: i["Alias"], reverse=True)
        else:
            return sorted(images_info, key=lambda i: i["Alias"])

    except VMException as e:
        message = f"Could not fetch remote images: {e.message}"
        logging.error("Please confirm that you're connected to the internet.")
        raise LXCException(message)


def list_cached_images():
    def get_cached_image_info(image):
        try:
            return {
                "Alias": image.update_source["alias"],
                "Description": image.properties["description"]
            }
        except KeyError as e:
            logging.debug(f"Error {e}: Unexpected image schema: {image}")

    client = util.get_pylxd_client()
    images = client.images.all()  # pylint: disable=no-member
    images_info = filter(None, map(get_cached_image_info, images))
    return list(images_info)
