from paramiko import SSHClient, AuthenticationException, client
from paramiko.ssh_exception import SSHException
import socket
import logging
import os
import requests
import shutil
import time

import config


def isSSHAvailableOnPort(port):
    ssh = SSHClient()
    if not os.path.isfile(config.SSHHostKeysFile):
        with open(config.SSHHostKeysFile, "w") as f:
            f.write("")

    try:
        ssh.load_host_keys(config.SSHHostKeysFile)
        ssh.set_missing_host_key_policy(client.AutoAddPolicy)
        ssh.connect("localhost", port, username=config.SSHUserName,
                    key_filename=config.SSHPrivateKeyFile, look_for_keys=False)
        return True
    except (AuthenticationException,
            SSHException, socket.error) as e:
        logging.debug(e)
        logging.debug("SSH not available on port {}".format(port))
    except socket.timeout:
        logging.error("SSH probe timed out")
    except Exception as e:
        logging.debug(e)
        logging.error("SSH probe failed with an unknown error")

    return False


def downloadFile(url, destination):
    with requests.get(url, stream=True) as r:
        with open(destination, 'wb') as f:
            shutil.copyfileobj(r.raw, f)


def retry(fn, retries, waitTime):
    while True:
        try:
            return fn()
        except Exception as e:
            if retries > 0:
                retries -= 1
                time.sleep(waitTime)
            else:
                raise e


def find(fn, iterable, default):
    return next(filter(lambda i: fn(i), iterable), default)
