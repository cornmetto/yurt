import logging


class LXDError(Exception):
    def __init__(self, message):
        self.message = message


class LXD:
    def __init__(self):
        pass

    def setUp(self):
        self._setUpNetwork()
        self._setUpProfile()

    def _setUpNetwork(self):
        raise LXDError("_setUpNetwork: Not implemented")

    def _setUpProfile(self):
        raise LXDError("_setUpProfile: configure profile")
