import os
from subprocess import check_output, CalledProcessError
import logging
import re


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
                "--vsys 0 --vmname {0}".format(vmName),
                "--vsys 0 --settingsfile {0}".format(settingsFile),
                "--vsys 0 --basefolder {0}".format(baseFolder),
                "--vsys 0 --memory {0}".format(memory),
            ])

            self._run(cmd)

        def listVms(self):
            def parseLine(line):
                match = re.search(r'"(.*)" \{(.*)\}', line)
                return match.groups()

            output = self._list("vms").strip()
            vmList = [(vmName, vmId)
                      for vmName, vmId in map(parseLine, output.split('\n'))]
            return vmList

        def vmInfo(self, vmName):
            cmd = "showvminfo {0} --machinereadable".format(vmName)
            try:
                return self._run(cmd)
            except VBoxManageError:
                logging.info("VM {0} not found".format(vmName))

        def destroyVm(self, vmName):
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
                raise VBoxManageError("{0} failed".format(cmd))

        def __repr__(self):
            return "VBoxManage Executable: {0}".format(self.executable)

    def __init__(self):
        if not VBoxManage.__instance:
            VBoxManage.__instance = VBoxManage.__VBoxManage()

    def __getattr__(self, name):
        return getattr(self.__instance, name)

    def __repr__(self):
        return self.__instance.__repr__()
