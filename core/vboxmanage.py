import os
from subprocess import check_output, CalledProcessError
import logging
import re
from typing import Dict
import random
import time

from .utils import isSSHAvailableOnPort


class VBoxManageError(Exception):
    def __init__(self, message):
        self.message = message


class VBoxManage:
    __instance = None

    class __VBoxManage:
        def __init__(self):
            self.executable = self.getVBoxManagePathWindows()

        def _list(self, args: str):
            cmd = "list {0}".format(args)
            return self._run(cmd)

        # Return Id ???
        def importVm(self, vmName, applianceFile, baseFolder):
            settingsFile = os.path.join(baseFolder, "{}.vbox".format(vmName))
            memory = 2048

            cmd = " ".join([
                "import {0}".format(applianceFile),
                "--options keepnatmacs",
                "--vsys 0 --vmname {0}".format(vmName),
                "--vsys 0 --settingsfile {0}".format(settingsFile),
                "--vsys 0 --basefolder {0}".format(baseFolder),
                "--vsys 0 --memory {0}".format(memory),
            ])

            self._run(cmd)

        def modifyVm(self, vmName, settings: Dict[str, str]):
            options = map(
                lambda option: "--{0} {1}".format(option[0], option[1]),
                settings.items())

            cmd = "modifyvm {0} {1}".format(vmName, " ".join(options))

            self._run(cmd)

        def listVms(self):
            def parseLine(line):
                match = re.search(r'"(.*)" \{(.*)\}', line)
                return match.groups()

            output = self._list("vms")
            vmList = [(vmName, vmId)
                      for vmName, vmId in map(parseLine, output.splitlines())]
            return vmList

        def listHostOnlyInterfaces(self):
            def getIfaceName(line):
                match = re.search(r"^Name: +(.*)", line)
                if match:
                    return match.group(1)

            interfaces = map(getIfaceName, self._run(
                "list hostonlyifs").splitlines())
            return list(filter(None, interfaces))

        def vmInfo(self, vmName: str):
            cmd = "showvminfo {0} --machinereadable".format(vmName)
            output = self._run(cmd)
            infoList = map(lambda l: l.split("=", 1), output.splitlines())
            return dict(infoList)

        def startVm(self, vmName: str):
            cmd = "startvm {0} --type headless".format(vmName)
            self._run(cmd)

        def stopVm(self, vmName: str):
            cmd = "controlvm {0} acpipowerbutton".format(vmName)
            self._run(cmd)

        def setUpNATPortForwarding(self, vmName: str, config):
            retryCount, retryWaitTime = (5, 7)
            lowPort, highPort = (4022, 4099)
            hostPort = lowPort
            connected = isSSHAvailableOnPort(hostPort, config)

            while (retryCount > 0) and not connected:
                addRuleCmd = 'controlvm {0} natpf1 "ssh,tcp,,{1},,22"'.format(
                    vmName, hostPort)
                removeRuleCmd = 'controlvm {0} natpf1 delete ssh'.format(
                    vmName)

                logging.debug(
                    "Attempting to forward SSH on port {0}...".format(hostPort))
                try:
                    self._run(removeRuleCmd)
                except:
                    pass

                try:
                    self._run(addRuleCmd)
                    time.sleep(2)  # Give it time.
                    connected = isSSHAvailableOnPort(hostPort, config)
                    if not connected:
                        hostPort = random.randrange(lowPort, highPort)
                        retryCount -= 1
                        time.sleep(retryWaitTime)

                except VBoxManageError:
                    raise VBoxManageError(
                        "An error occurred while setting up SSH")

            if connected:
                return hostPort
            else:
                raise VBoxManageError(
                    "Failed to set up SSH port forwarding")

        def createHostOnlyInterface(self):
            oldInterfaces = set(self.listHostOnlyInterfaces())
            self._run("hostonlyif create")
            newInterfaces = set(self.listHostOnlyInterfaces())
            try:
                return newInterfaces.difference(oldInterfaces).pop()
            except KeyError:
                logging.error("Host-Only interface not properly initialized")

        def removeHostOnlyInterface(self, interfaceName: str):
            self._run('hostonlyif remove "{0}"'.format(interfaceName))

        def destroyVm(self, vmName: str):
            cmd = "unregistervm --delete {0}".format(vmName)
            self._run(cmd)

        def getVBoxManagePathWindows(self):
            baseDirs = []

            environmentDirs = os.environ.get('VBOX_INSTALL_PATH') \
                or os.environ.get('VBOX_MSI_INSTALL_PATH')

            if environmentDirs:
                baseDirs.extend(environmentDirs.split(';'))

            # Other possible locations.
            baseDirs.extend([
                os.path.expandvars(
                    r'${SYSTEMDRIVE}\Program Files\Oracle\VirtualBox'),
                os.path.expandvars(
                    r'${SYSTEMDRIVE}\Program Files (x86)\Oracle\VirtualBox'),
                os.path.expandvars(r'${PROGRAMFILES}\Oracle\VirtualBox')
            ])

            for baseDir in baseDirs:
                path = os.path.join(baseDir, "VBoxManage.exe")
                if os.path.exists(path):
                    return path

        def _run(self, cmd: str):
            fullCmd = "{0} -q {1}".format(self.executable, cmd)
            output = ""
            try:
                output = check_output(fullCmd, text=True)
                return output
            except CalledProcessError as e:
                logging.debug(output)
                logging.debug(e)
                msg = "{0} failed".format(cmd)
                logging.debug(msg)
                raise VBoxManageError(msg)

        def __repr__(self):
            return "VBoxManage Executable: {0}".format(self.executable)

    def __init__(self):
        if not VBoxManage.__instance:
            VBoxManage.__instance = VBoxManage.__VBoxManage()

    def __getattr__(self, name):
        return getattr(self.__instance, name)

    def __repr__(self):
        return self.__instance.__repr__()
