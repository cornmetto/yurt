import argparse
import logging
import uuid

from core.vmmanager import VMManager
from config import Config


def init(args):
    config = Config()
    vmManager = VMManager(config)
    vmManager.init()


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
