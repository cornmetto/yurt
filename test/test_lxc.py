import unittest
import logging

from yurt import lxc, util

from test.yurt_test_util import YurtTest, ping


class LXCTest(YurtTest):

    def test_launch(self):
        instance_name = f"test-instance-{util.random_string()}"

        logging.info(f"Test launch: {instance_name}.")
        lxc.launch("images:alpine/3.10", instance_name)
        instance = util.find(
            lambda i: i["Name"] == instance_name and i["Status"] == "Running",
            lxc.list_(),
            None
        )
        self.assertIsNotNone(instance)

    def test_stop(self):
        instance_name = f"test-instance-{util.random_string()}"
        lxc.launch("images:alpine/3.10", instance_name)

        logging.info(f"Test stop: {instance_name}.")
        lxc.stop([instance_name])
        instance = util.find(
            lambda i: i["Name"] == instance_name and i["Status"] == "Stopped",
            lxc.list_(),
            None
        )
        self.assertIsNotNone(instance)

    def test_start(self):
        instance_name = f"test-instance-{util.random_string()}"
        lxc.launch("images:alpine/3.10", instance_name)
        lxc.stop([instance_name])

        logging.info(f"Test start: {instance_name}.")
        lxc.start([instance_name])
        instance = util.find(
            lambda i: i["Name"] == instance_name and i["Status"] == "Running",
            lxc.list_(),
            None
        )
        self.assertIsNotNone(instance)

    def test_delete(self):
        instance_name = f"test-instance-{util.random_string()}"
        lxc.launch("images:alpine/3.10", instance_name)
        lxc.stop([instance_name])
        lxc.delete([instance_name])

        instance = util.find(
            lambda i: i["Name"] == instance_name,
            lxc.list_(),
            None
        )
        self.assertIsNone(instance)

    def test_ping_from_host(self):
        instance_name = f"test-instance-{util.random_string()}"
        lxc.launch("images:alpine/3.10", instance_name)
        instance = util.find(
            lambda i: i["Name"] == instance_name and i["Status"] == "Running",
            lxc.list_(),
            None
        )
        self.assertIsNotNone(instance)

        logging.info(f"Test ping: {instance_name}")
        ip_address = instance["IP Address"]
        self.assertTrue(ping(ip_address))

    def test_ping_between_instances(self):
        instance1_name = f"test-instance-{util.random_string()}"
        instance2_name = f"test-instance-{util.random_string()}"
        lxc.launch("images:alpine/3.10", instance1_name)
        lxc.launch("images:alpine/3.10", instance2_name)

        lxc.exec_(instance1_name, ["ping", "-c1", instance2_name])


if __name__ == '__main__':
    unittest.main()
