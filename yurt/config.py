import logging
import os
from enum import Enum
import platform
import sys

from yurt.exceptions import ConfigReadException, ConfigWriteException

app_name = "yurt"
version = "0.1.0"


class Key(Enum):
    vm_name = 1
    interface = 2
    interface_ip_address = 3
    interface_netmask = 4
    ssh_port = 5
    is_lxd_initialized = 6
    lxd_port = 7


class System(Enum):
    windows = 1
    macos = 2
    linux = 3


_raw_system = platform.system().lower()

if _raw_system == "windows":
    system = System.windows
elif _raw_system == "darwin":
    system = System.macos
elif _raw_system == "linux":
    system = System.linux
else:
    logging.error(f"Unknown system: {_raw_system}")
    sys.exit(1)


YURT_ENV = os.environ.get("YURT_ENV", "")
_app_dir_name = f"{app_name}-{YURT_ENV}"


try:
    if system == System.windows:
        config_dir = os.path.join(
            os.environ['LOCALAPPDATA'], f"{_app_dir_name}")
    else:
        config_dir = os.path.join(os.environ['HOME'], f".{_app_dir_name}")
except KeyError as e:
    logging.error(f"{e} environment variable is not set.")
    sys.exit(1)


# VM Configuration ##########################################################
image_url = "https://cloud-images.ubuntu.com/releases/focal/release-20201210/ubuntu-20.04-server-cloudimg-amd64.ova"
image_sha256 = "8a79978328c7eb25fb86d84967415cea329d5c540b01bea55262f6df61b7fc64"
vm_memory = 2048  # MB
storage_pool_disk_size_mb = 64000  # MB
user_name = "yurt"
port_range = (55000, 59999)


# Instance Paths ############################################################
_config_file = os.path.join(config_dir, "config.json")
vm_install_dir = os.path.join(config_dir, "vm")
image = os.path.join(config_dir, "image", os.path.basename(image_url))
storage_pool_disk = os.path.join(vm_install_dir, "yurt-storage-pool.vmdk")
config_disk = os.path.join(vm_install_dir, "yurt-config.vmdk")
remote_tmp = "/tmp/yurt"


# Source Paths ##############################################################
src_home = os.path.dirname(__file__)
provision_dir = os.path.join(src_home, "provision")
config_disk_source = os.path.join(provision_dir, "yurt-config.vmdk")
ssh_private_key_file = os.path.join(provision_dir, "id_rsa")


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
