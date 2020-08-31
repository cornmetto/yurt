import unittest
import logging
import time

from yurt import vm
from yurt.vm import VMState

logging.basicConfig(format='%(levelname)s: %(message)s', level="INFO")


class SmokeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        vm.init()
        logging.info("Waiting for VM to be registered...")
        time.sleep(3)

    def test_start(self):

        vm.start()

        timeOut = 30
        retryStep = 5
        while timeOut > 0:
            if vm.state() == VMState.Running:
                break
            logging.info(
                "Not running. Retrying in {0} seconds...".format(retryStep))
            time.sleep(retryStep)
            timeOut -= retryStep

        self.assertTrue(vm.state() == VMState.Running)


if __name__ == '__main__':
    unittest.main()
