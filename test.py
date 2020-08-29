import unittest
import logging
import time

from config import TestConfig
from yurt.vm import VM

logging.basicConfig(format='%(levelname)s: %(message)s', level="INFO")

config = TestConfig()


class SmokeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        vm = VM(config)
        vm.init()
        logging.info("Waiting for VM to be registered...")
        time.sleep(3)

    def test_start(self):
        vm = VM(config)

        vm.start()

        timeOut = 30
        retryStep = 5
        while timeOut > 0:
            if vm.isRunning():
                break
            logging.info(
                "Not running. Retrying in {0} seconds...".format(retryStep))
            time.sleep(retryStep)
            timeOut -= retryStep

        self.assertTrue(vm.isRunning())


if __name__ == '__main__':
    unittest.main()
