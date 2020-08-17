import argparse
import logging
import uuid

from vboxmanage import VBoxManage
from config import Config, ConfigName, ConfigReadError


def init(args):
    # Check if already initialized.
    # No, Initialize.
    # Yes, Report as such. Do nothing.
    try:
        config = Config()
        vmName = config.get(ConfigName.vmName)
    except ConfigReadError:
        return

    if vmName:
        logging.info("{0} has already been initialized.".format(
            config.applicationName))
        logging.info(
            "If you need to start over, destroy the existing environment first.")
    else:
        vmUuid = uuid.uuid4()
        vmName = "{0}-{1}".format(config.applicationName, vmUuid)
        config.set(ConfigName.vmName, vmName)
        config.set(ConfigName.vmUuid, str(vmUuid))


def destroy(args):
    logging.info("Not implemented")


def up(args):
    logging.info("Not implemented")


def down(args):
    logging.warning("Not implemented: Shut down VM")


commands = {
    "up": up,
    "down": down,
    "init": init,
    "destroy": destroy
}


def setUpLogging(level="INFO"):
    logging.basicConfig(format='%(levelname)s: %(message)s', level=level)


def parseArgs():
    parser = argparse.ArgumentParser(
        description="Containerized Development Environments")

    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('command', choices=["init", "up", "down", "destroy"])

    return parser.parse_args()


if __name__ == "__main__":
    args = parseArgs()
    setUpLogging(level="DEBUG" if args.verbose else "INFO")
    try:
        commands[args.command](args)
    except KeyError:
        logging.error("Command '{0}' not found".format(args.command))
