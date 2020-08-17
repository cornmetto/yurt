import os
from subprocess import check_output, CalledProcessError
import logging


class VBoxManage:
    __instance = None

    class __VBoxManage:
        def __init__(self):
            self.executable = self.getVBoxManagePathWindows()

        def list(self, args: str):
            cmd = "list {0}".format(args)
            output = self._run(cmd)
            return output

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
            try:
                return check_output(fullCmd, text=True)
            except CalledProcessError as e:
                logging.error(e)

        def __repr__(self):
            return "VBoxManage Executable: {0}".format(self.executable)

    def __init__(self):
        if not VBoxManage.__instance:
            VBoxManage.__instance = VBoxManage.__VBoxManage()

    def __getattr__(self, name):
        return getattr(self.__instance, name)

    def __repr__(self):
        return self.__instance.__repr__()
