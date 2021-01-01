import time
import logging
import os
import unittest

from yurt import util as yurt_util
from yurt import vm, lxc, config
from yurt.exceptions import YurtException


os.environ["PYLXD_WARNINGS"] = "none"
logging.basicConfig(format='%(levelname)s-%(name)s: %(message)s', level="INFO")
logging.captureWarnings(True)
logging.getLogger("py.warnings").setLevel(logging.ERROR)
logging.getLogger("ws4py").setLevel(logging.ERROR)


class YurtTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.discard_vm = os.environ.get(
            "YURT_TEST_DISCARD_VM_POLICY"
        ) == "discard"

        if cls.discard_vm:
            if vm.state() == vm.State.Running:
                vm.stop(force=True)
            if vm.state() == vm.State.Stopped:
                vm.destroy()

        if vm.state() == vm.State.NotInitialized:
            vm.init()
            logging.info("Waiting for VM registration...")
            time.sleep(3)

        if vm.state() == vm.State.Stopped:
            vm.start()
            lxc.ensure_is_ready()

        def check_if_running():
            if vm.state() != vm.State.Running:
                raise YurtException("VM Not running")
        yurt_util.retry(check_if_running)

    @classmethod
    def tearDownClass(cls):
        if cls.discard_vm:
            vm.stop(force=True)
            vm.destroy()


def ping(ip_address: str):
    if config.system == config.System.windows:
        packets_number_option = "-n"
    else:
        packets_number_option = "-c"
    cmd = ["ping", packets_number_option, "1", ip_address]

    try:
        yurt_util.run(cmd)
        return True
    except YurtException as e:
        logging.error(e)
        return False


def generate_instance_name():
    return f"test-{yurt_util.random_string()}"


def mark(title: str):
    title_str = f"=> {title} "
    print(f"\n{title_str}{'-' * (70 - len(title_str))}")
