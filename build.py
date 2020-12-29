import PyInstaller.__main__
import os

from yurt import config

PyInstaller.__main__.run([
    "--name=yurt",
    "--noconfirm",
    f"--add-data={config.provision_dir}{os.pathsep}provision",
    os.path.join(os.path.dirname(__file__), "./yurt/cli.py")
])
