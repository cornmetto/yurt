import logging
import os
from enum import Enum
import platform

from yurt.exceptions import ConfigReadException, ConfigWriteException

app_name = "yurt"
appliance_version = "0.1.4"


class Key(Enum):
    vm_name = 1
    interface = 2
    interface_ip_address = 3
    interface_netmask = 4
    ssh_port = 5


YURT_ENV = os.environ.get("YURT_ENV")


if YURT_ENV == "development":
    _config_dir_name = f".{app_name}-dev"
elif YURT_ENV == "test":
    _config_dir_name = f".{app_name}-test"
else:
    _config_dir_name = f".{app_name}"


try:
    if platform.system() == "Windows":
        config_dir = os.path.join(
            os.environ['HOMEPATH'], f"{_config_dir_name}")
    else:
        config_dir = os.path.join(os.environ['HOME'], f"{_config_dir_name}")
except KeyError:
    import sys

    logging.error("HOME environment variable is not set")
    sys.exit(1)


# VM Configuration ##########################################################
image_url = "https://cloud-images.ubuntu.com/releases/bionic/release-20200922/ubuntu-18.04-server-cloudimg-amd64.ova"
image_sha256 = "015616de6eea3cde980f6de052bc1c8918e7c401f997327be265359dd541c85d"
vm_memory = 2048  # MB
storage_pool_disk_size_mb = 64000  # MB
ssh_user_name = "yurt"


# Instance Paths ############################################################
_config_file = os.path.join(config_dir, "config.json")
vm_install_dir = os.path.join(config_dir, "vm")
image = os.path.join(config_dir, "image",
                     "ubuntu-18.04-server-cloudimg-amd64.ova")
storage_pool_disk = os.path.join(vm_install_dir, "yurt-storage-pool.vmdk")
config_disk = os.path.join(vm_install_dir, "yurt-config.vmdk")


# Source Paths ##############################################################
_src_home = os.path.dirname(__file__)
bin_dir = os.path.join(_src_home, "bin")
_provision_dir = os.path.join(_src_home, "provision")
config_disk_source = os.path.join(_provision_dir, "yurt-config.vmdk")
ssh_private_key_file = os.path.join(_provision_dir, "id_rsa")


# Utilities ###############################################################
def _ensure_config_file_exists():
    if not os.path.isdir(config_dir):
        os.makedirs(config_dir)

    if not os.path.isfile(_config_file):
        with open(_config_file, 'w') as f:
            f.write('{}')


def _read_config():
    import json

    try:
        _ensure_config_file_exists()
        with open(_config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        msg = 'Config file not found'
        logging.error(msg)
        raise ConfigReadException(msg)
    except json.JSONDecodeError:
        msg = f"Malformed config file: {_config_file}"
        logging.error(msg)
        raise ConfigReadException(msg)


def _write_config(config):
    import json

    try:
        _ensure_config_file_exists()
        with open(_config_file, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        logging.error(f"Error writing config: {e}")
        raise ConfigWriteException(e)


def get_config(key: Key):
    config = _read_config()
    if config:
        return config.get(key.name, None)


def set_config(key: Key, value: str):
    old = _read_config()

    if old is None:
        return

    new = old.copy()
    new[key.name] = value

    try:
        _write_config(new)
    except ConfigWriteException:
        _write_config(old)
        raise ConfigWriteException


def clear():
    logging.debug("Clearing config")
    _write_config({})
