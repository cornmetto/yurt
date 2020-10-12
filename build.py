import PyInstaller.__main__
import os
import tempfile

from yurt import config, vm

PyInstaller.__main__.run([
    "--name=yurt",
    "--noconfirm",
    f"--add-binary={config.bin_dir}{os.pathsep}bin",
    f"--add-data={config.provision_dir}{os.pathsep}provision",
    os.path.join(os.path.dirname(__file__), "./yurt/cli.py")
])
