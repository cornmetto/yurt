from paramiko import SSHClient, AuthenticationException, client
from paramiko.ssh_exception import SSHException
import socket
import logging
import os
import requests
import shutil
from pylxd import Client


def isSSHAvailableOnPort(port, config):
    ssh = SSHClient()
    if not os.path.isfile(config.SSHHostKeysFile):
        with open(config.SSHHostKeysFile, "w") as f:
            f.write("")

    try:
        ssh.load_host_keys(config.SSHHostKeysFile)
        ssh.set_missing_host_key_policy(client.AutoAddPolicy)
        ssh.connect("127.0.0.1", port, username=config.SSHUserName,
                    key_filename=config.SSHPrivateKeyFile, look_for_keys=False)
        return True
    except (AuthenticationException,
            SSHException, socket.error):
        logging.debug("SSH not available on port {}".format(port))
    except socket.timeout:
        logging.debug("SSH probe timed out")
    except:
        logging.debug("SSH probe failed with unknown error")

    return False


def isLXDAvailableOnPort(port, config):
    try:
        client = Client(
            endpoint="https://localhost:{}".format(port),
            cert=(config.LXDTLSCert, config.LXDTLSKey),
            verify=False
        )
        return True
    except Exception as e:
        logging.error(e)
        return False

def downloadFile(url, destination):
    with requests.get(url, stream=True) as r:
        with open(destination, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
