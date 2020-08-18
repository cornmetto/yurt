import unittest

from config import TestConfig
from core.vmmanager import VMManager


class VMLifeCycle(unittest.TestCase):
    def test_init(self):
        config = TestConfig()
        vmManager = VMManager(config)
        vmManager.init()

    def test_start(self):
        pass

    def test_stop(self):
        pass


if __name__ == '__main__':
    unittest.main()
