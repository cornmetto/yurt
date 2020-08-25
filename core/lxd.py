import logging
from pylxd import Client

from config import ConfigName


class LXDError(Exception):
    def __init__(self, message):
        self.message = message


class LXD:
    def __init__(self, config):
        hostPort = config.get(ConfigName.hostLXDPort)
        if not hostPort:
            raise LXDError("LXD Port is not set up properly")

        self.client = Client(
            endpoint="https://localhost:{}".format(hostPort),
            cert=(config.LXDTLSCert, config.LXDTLSKey),
            verify=False
        )

    def setUp(self):
        self._setUpContainerNetwork()
        self._setUpProfile()

    def _setUpContainerNetwork(self):
        raise LXDError("_setUpNetwork: Not implemented")

    def _setUpProfile(self):
        raise LXDError("_setUpProfile: configure profile")
