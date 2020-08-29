import argparse
import logging
import uuid
import click

from yurt.vm import VM
from config import Config

config = Config(env="prod")


logger = logging.getLogger()


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('-v', is_flag=True)
@click.version_option()
def yurt(v):
    """
    Linux Containers for Development.
    """
    logLevel = logging.DEBUG if v else logging.INFO
    consoleHandler = logging.StreamHandler()
    logFormatter = logging.Formatter("%(levelname)s: %(message)s")
    consoleHandler.setFormatter(logFormatter)

    logger.handlers.clear()
    logger.addHandler(consoleHandler)
    logger.setLevel(logLevel)


# Machine Commands #######################################################
@yurt.group()
def env():
    """
    Manage the yurt environment on your machine.
    """
    pass


@env.command()
def init():
    """
    Initialize yurt environment.
    """
    vm = VM(config)
    vm.init()


@env.command()
def destroy():
    """
    Destroy environment
    """
    vm = VM(config)
    vm.destroy()


@env.command(name="start")
def startVM():
    """
    Start environment
    """
    vm = VM(config)
    vm.start()


@env.command(name="stop")
def stopVM():
    """
    Shut down environment
    """
    vm = VM(config)
    vm.stop()


# Instance Commands ##################################################
@yurt.command()
@click.argument("image")
@click.argument("name")
def launch():
    """
    Create and start an instance called NAME from the specified IMAGE
    """
    logging.warning("yurt create - Not implemented")


@yurt.command()
def start():
    logging.warning("yurt stat - Not implemented")


@yurt.command()
def stop():
    logging.warning("yurt stop - Not implemented")


@yurt.command()
def delete():
    logging.warning("yurt delete - Not implemented")


@yurt.command(name="list")
def listInstances():
    logging.warning("Not implemented")
