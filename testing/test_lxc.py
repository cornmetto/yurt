import logging

from testing import util
from yurt import util as yurt_util
from yurt import lxc


class LXCTest(util.YurtTest):

    def test_launch(self):
        util.mark("test_launch")

        instance_name = util.generate_instance_name()
        lxc.launch("images", "alpine/3.10", instance_name)
        instance = yurt_util.find(
            lambda i: i["Name"] == instance_name and i["Status"] == "Running",
            lxc.list_(),
            None
        )
        self.assertIsNotNone(instance)

    def test_stop(self):
        util.mark("test_stop")

        instance_name = util.generate_instance_name()
        lxc.launch("images", "alpine/3.10", instance_name)

        lxc.stop([instance_name])
        instance = yurt_util.find(
            lambda i: i["Name"] == instance_name and i["Status"] == "Stopped",
            lxc.list_(),
            None
        )
        self.assertIsNotNone(instance)

    def test_start(self):
        util.mark("test_start")

        instance_name = util.generate_instance_name()
        lxc.launch("images", "alpine/3.10", instance_name)
        lxc.stop([instance_name])

        lxc.start([instance_name])
        instance = yurt_util.find(
            lambda i: i["Name"] == instance_name and i["Status"] == "Running",
            lxc.list_(),
            None
        )
        self.assertIsNotNone(instance)

    def test_delete(self):
        util.mark("test_delete")

        instance_name = util.generate_instance_name()
        lxc.launch("images", "alpine/3.10", instance_name)
        lxc.stop([instance_name])
        lxc.delete([instance_name])

        instance = yurt_util.find(
            lambda i: i["Name"] == instance_name,
            lxc.list_(),
            None
        )
        self.assertIsNone(instance)

    def test_ping_from_host(self):
        util.mark("test_ping_from_host")

        instance_name = util.generate_instance_name()
        lxc.launch("images", "alpine/3.10", instance_name)
        instance = yurt_util.find(
            lambda i: i["Name"] == instance_name and i["Status"] == "Running",
            lxc.list_(),
            None
        )
        self.assertIsNotNone(instance)

        logging.info(f"Test ping: {instance_name}")
        ip_address = instance["IP Address"]
        self.assertTrue(util.ping(ip_address))

    def test_ping_between_instances(self):
        util.mark("test_ping_between_instances")

        instance1_name = util.generate_instance_name()
        instance2_name = util.generate_instance_name()
        lxc.launch("images", "alpine/3.10", instance1_name)
        lxc.launch("images", "alpine/3.10", instance2_name)

        res = lxc.exec_(instance1_name, ["ping", "-c1", instance2_name])
        self.assertTrue(res.exit_code == 0)
