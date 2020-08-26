import logging
from pylxd import Client, models
import ipaddress

from config import ConfigName


class LXDError(Exception):
    def __init__(self, message):
        self.message = message


class LXD:
    def __init__(self, config):
        hostPort = config.get(ConfigName.hostLXDPort)
        if not hostPort:
            raise LXDError("LXD Port is missing.")

        self.config = config
        self.client = Client(
            endpoint="https://localhost:{}".format(hostPort),
            cert=(config.LXDTLSCert, config.LXDTLSKey),
            verify=False
        )

        # Some constants
        self.networkName = "yurt-int"

    def setUp(self):
        try:
            self._setUpNetwork()
            self._setUpProfile()
        except Exception as e:
            raise LXDError("LXD set up failed: {}".format(e))

    def _setUpNetwork(self):
        if models.Network.exists(self.client, self.networkName):
            return

        ipAddress = self.config.get(ConfigName.hostOnlyInterfaceIPAddress)
        networkMask = self.config.get(ConfigName.hostOnlyInterfaceNetworkMask)
        if not (ipAddress and networkMask):
            raise LXDError("Bad IP Configuration. ip: {0}, mask: {1}".format(
                ipAddress, networkMask))

        fullHostAddress = ipaddress.ip_interface(
            "{0}/{1}".format(ipAddress, networkMask))

        guestBridgeAddress = ipaddress.ip_interface(
            "{0}/{1}".format((fullHostAddress + 1).ip, networkMask)).exploded
        dhcpRangeLow = (fullHostAddress + 10).ip.exploded
        dhcpRangeHigh = (fullHostAddress + 249).ip.exploded

        models.Network.create(self.client, self.networkName, type="bridge",
                              config={
                                  "bridge.external_interfaces": "enp0s8",
                                  "ipv4.nat": "true",
                                  "ipv4.dhcp": "true",
                                  "ipv4.address": guestBridgeAddress,
                                  "ipv4.dhcp.expiry": "48h",
                                  "ipv4.dhcp.ranges": "{0}-{1}".format(dhcpRangeLow, dhcpRangeHigh),
                                  "dns.domain": self.config.applicationName,
                                  "ipv6.address": "none"
                              })

    def _setUpProfile(self):
        defaultProfile = self.client.profiles.get("default")
        defaultProfile.devices.update({
            "eth0": {
                "type": "nic",
                "name": "eth0",
                "nictype": "bridged",
                "parent": "yurt-int",
            },
            "root": {
                "type": "disk",
                "path": "/",
                "pool": "yurt"
            }
        })

        defaultProfile.save()
