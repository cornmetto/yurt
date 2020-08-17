import argparse
import logging

from vboxmanage import VBoxManage


def up(args):
    logging.info("Not implemented")


def down(args):
    logging.warning("Not implemented: Shut down VM")


commands = {
    "up": up,
    "down": down
}


def setUpLogging(level="INFO"):
    logging.basicConfig(format='%(levelname)s: %(message)s', level=level)


def parseArgs():
    parser = argparse.ArgumentParser(
        description="Containerized Development Environments")

    parser.add_argument('command', choices=["up", "down"])

    return parser.parse_args()


if __name__ == "__main__":
    setUpLogging()
    args = parseArgs()
    try:
        commands[args.command](args)
    except KeyError:
        logging.error("Error: Command '{0}' not found".format(args.command))
