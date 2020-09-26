import unittest
import logging

from yurt import lxc, util

from test.yurt_test import YurtTest


class LXCTest(YurtTest):

    def test_launch(self):
        vm_name = f"test-lxc-{util.random_string()}"
        lxc.launch("images:alpine/3.10", vm_name)


if __name__ == '__main__':
    unittest.main()
