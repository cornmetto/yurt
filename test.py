import unittest
import logging
import time

from config import TestConfig
from core.vm import VM

logging.basicConfig(format='%(levelname)s: %(message)s', level="INFO")


class VMLifeCycle(unittest.TestCase):

    def setUp(self):
        self.config = TestConfig()
        self.vm = VM(self.config)

    def test_init_destroy(self):
        self.vm.init()

        logging.info("Waiting for VM to be registered")
        time.sleep(3)
        self.assertTrue(self.vm.isInitialized())

        self.vm.destroy()

        logging.info("Waiting for VM to be unregistered")
        time.sleep(3)
        self.assertFalse(self.vm.isInitialized())

    def test_start(self):
        pass

    def test_stop(self):
        pass


if __name__ == '__main__':
    unittest.main()
