import logging
from pylxd import Client, models, exceptions
import ipaddress
import time
from enum import Enum
import urllib3
import os
from ws4py.client import WebSocketBaseClient
import json

from config import ConfigName

urllib3.disable_warnings()


class LXDError(Exception):
    def __init__(self, message):
        self.message = message


class LXDStatusCode(Enum):
    OperationCreated = 100
    Started = 101
    Stopped = 102
    Running = 103
    Cancelling = 104
    Pending = 105
    Starting = 106
    Stopping = 107
    Aborting = 108
    Freezing = 109
    Frozen = 110
    Thawed = 111
    Success = 200
    Failure = 400
    Cancelled = 401

    @staticmethod
    def get(numericStatusCode):
        try:
            return LXDStatusCode(numericStatusCode)
        except ValueError:
            logging.error(f"Unexpected status code {numericStatusCode}")
            return numericStatusCode


class LXDOperationProgress(WebSocketBaseClient):
    def __init__(self, wsURL, operationId):
        super().__init__(wsURL)
        self.operationId = operationId

    def handshake_ok(self):
        self.messages = []

    def received_message(self, message):
        json_message = json.loads(message.data.decode('utf-8'))
        print(json_message)


class LXD:
    def __init__(self, config):
        self.config = config
        self.networkName = "yurt-int"

    def _getClient(self):
        hostPort = self.config.get(ConfigName.hostLXDPort)
        hostPort = 8433
        if not hostPort:
            raise LXDError("LXD Port is missing.")

        return Client(
            endpoint="http://localhost:{}".format(hostPort),
            cert=(self.config.LXDTLSCert, self.config.LXDTLSKey),
            verify=False
        )

    def setUp(self):
        client = self._getClient()
        try:
            self._setUpNetwork(client)
            self._setUpProfile(client)
        except Exception as e:
            raise LXDError("LXD set up failed: {}".format(e))

    def _setUpNetwork(self, client):
        if models.Network.exists(client, self.networkName):
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

        models.Network.create(client, self.networkName, type="bridge",
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

    def _setUpProfile(self, client):
        defaultProfile = client.profiles.get("default")
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

    def _waitForOperationWithConsoleUpdates(self, client, operationId: str):
        import random
        os.environ["PYLXD_WARNINGS"] = "none"

        retry = 3
        operation = None
        while operation == None and retry > 0:
            try:
                operation = client.operations.get(operationId)
            except exceptions.NotFound:
                logging.debug(
                    f"Operation {operationId} not found. Retrying...")
                time.sleep(3)
                retry -= 1

        logging.info(operation.description)
        lastStatusStr = ""
        while LXDStatusCode.get(operation.status_code) in (
            LXDStatusCode.OperationCreated,
            LXDStatusCode.Started,
            LXDStatusCode.Running,
            LXDStatusCode.Cancelling,
            LXDStatusCode.Pending,
            LXDStatusCode.Starting,
            LXDStatusCode.Stopping,
            LXDStatusCode.Aborting,
            LXDStatusCode.Freezing,
        ):
            if operation.metadata:
                statusStr = ", ".join(
                    f"{k}: {v}" for k, v in operation.metadata.items())
                if statusStr != lastStatusStr:
                    logging.info(f"{statusStr}")
                    lastStatusStr = statusStr

            time.sleep(random.randrange(5, 10))
            try:
                operation = client.operations.get(operationId)
            except exceptions.NotFound:
                break

        os.environ.pop("PYLXD_WARNINGS")

    def createInstance(self, instanceName: str, server: str, alias: str):
        # https://linuxcontainers.org/lxd/docs/master/instances
        # Valid instance names must:
        #   - Be between 1 and 63 characters long
        #   - Be made up exclusively of letters, numbers and dashes from the ASCII table
        #   - Not start with a digit or a dash
        #   - Not end with a dash

        client = self._getClient()
        if server in ("ubuntu", "images", "ubuntu-daily"):
            serverUrl = {"ubuntu": "https://cloud-images.ubuntu.com/releases",
                         "ubuntu-daily": "https://cloud-images.ubuntu.com/daily",
                         "images": "https://images.linuxcontainers.org",
                         }[server]
        else:
            serverUrl = server

        try:
            logging.info(
                "Creating intance {} using image alias {} from {}".format(instanceName, alias, serverUrl))
            logging.info(
                "This might take a few minutes...")
            response = client.api.instances.post(json={
                "name": instanceName,
                "source": {
                    "type": "image",
                    "alias": alias,
                    "mode": "pull",
                    "server": serverUrl,
                    "protocol": "simplestreams"
                }
            })
            operation = response.json()['operation']
            self._waitForOperationWithConsoleUpdates(client, operation)
        except Exception as e:
            logging.error(e)
            raise LXDError(
                "Failed to create instance {} using image alias {} from {}".format(instanceName, alias, serverUrl))

    def _getInstance(self, instanceName: str):
        client = self._getClient()
        try:
            return client.instances.get(instanceName)
        except exceptions.NotFound:
            raise LXDError(f"Instance {instanceName} not found.")
        except exceptions.LXDAPIException:
            raise LXDError(
                f"Could not fetch instance {instanceName}. Something went wrong")

    def startInstance(self, instanceName: str):
        instance = self._getInstance(instanceName)
        try:
            instance.start()
        except Exception as e:
            logging.error(e)
            raise LXDError("Failed to start instance")

    def stopInstance(self, instanceName: str):
        instance = self._getInstance(instanceName)
        try:
            instance.stop()
        except Exception as e:
            logging.error(e)
            raise LXDError("Failed to stop instance")

    def deleteInstance(self, instanceName: str):
        instance = self._getInstance(instanceName)
        try:
            instance.delete()
        except Exception as e:
            logging.error(e)
            raise LXDError("Failed to delete instance")

    def listInstances(self):
        client = self._getClient()

        def extractInstanceInfo(instance):
            try:
                addresses = instance.state().network["eth0"]["addresses"]
            except TypeError:
                addresses = []

            ipv4 = ""
            for address in addresses:
                if address["family"] == "inet":
                    ipv4 = address["address"]
                    break

            config = instance.config
            arch, os, release = config['image.architecture'], config['image.os'], config['image.release']
            return {
                "name": instance.name,
                "status": instance.status,
                "image": f"{os}/{release} ({arch})",
                "ipv4": ipv4
            }

        try:
            return list(map(extractInstanceInfo, client.containers.all()))
        except exceptions.LXDAPIException as e:
            logging.error(e)
            raise LXDError("Failed to fetch instances")

    def listImages(self):
        raise LXDError("Not implemented")
