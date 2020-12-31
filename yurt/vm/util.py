from yurt import config, util
from yurt.exceptions import VMException
from . import vbox


def _ports_in_use():
    ports = set()
    if config.system == config.System.windows:
        for line in util.run(["netstat", "-qnp", "TCP"]).split("\n"):
            cols = line.split()
            if len(cols) > 2 and cols[0] == "TCP":
                _, port = cols[1].split(":")
                ports.add(port)
    else:
        raise VMException(f"Unsupported platform: {config.system}")

    return ports


def _get_unused_port():
    import random

    ports_in_use = _ports_in_use()
    while True:
        port = random.randint(config.port_range[0], config.port_range[1])
        if port not in ports_in_use:
            return port


def vm_name():
    name = config.get_config(config.Key.vm_name)
    if not name:
        raise VMException("VM name has not yet been set.")
    return name


def is_ssh_available():
    from . import ssh

    try:
        ssh.run_cmd("hostname", hide_output=True)
        return True
    except VMException:
        return False


def wait_for_ssh():
    def check_ssh():
        if not is_ssh_available():
            raise VMException("SSH is unreachable.")

    util.retry(
        check_ssh, retries=30, wait_time=3,
        message="SSH is not yet available. Retrying..."
    )


def setup_port_forwarding():
    ssh_port = _get_unused_port()
    vm_name_ = vm_name()

    vbox.setup_port_forwarding(vm_name_, "ssh", ssh_port, 22)
    config.set_config(config.Key.ssh_port, ssh_port)

    lxd_port = _get_unused_port()
    vbox.setup_port_forwarding(vm_name_, "lxd", lxd_port, 80)
    config.set_config(config.Key.lxd_port, lxd_port)
