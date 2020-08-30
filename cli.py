import argparse
import logging
import uuid
import click

from yurt.vm import VM
from yurt.lxd import LXDError
from config import Config

config = Config(env="prod")


logger = logging.getLogger()

baseIndent = " " * 4


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('-v', is_flag=True, help="Increase verbosity.")
@click.version_option()
@click.pass_context
def yurt(ctx, v):
    """
    Linux Containers for Development.

    Yurt sets up a virtual machine with a configured LXD environment.

    A selection of LXD's commonly used features are exposed through the
    following commands. For help, use either -h or --help flags with any
    of the commands. e.g 'yurt launch --help'
    """
    logLevel = logging.DEBUG if v else logging.INFO
    consoleHandler = logging.StreamHandler()
    logFormatter = logging.Formatter("-> %(levelname)s-%(name)s: %(message)s")
    consoleHandler.setFormatter(logFormatter)

    if not v:
        consoleHandler.addFilter(logging.Filter('root'))

    logger.handlers.clear()
    logger.addHandler(consoleHandler)
    logger.setLevel(logLevel)
    ctx.obj = VM(config)


# VM #################################################################
@yurt.command()
@click.pass_context
def setup(ctx):
    """
    Initialize yurt VM.
    """
    ctx.obj.init()


@yurt.command()
@click.pass_context
def destroy(ctx):
    """
    Delete all resources including the yurt VM.
    """
    ctx.obj.destroy()


@yurt.command()
@click.pass_context
def up(ctx):
    """
    Start yurt VM
    """
    ctx.obj.start()


@yurt.command()
@click.pass_context
def shutdown(ctx):
    """
    Shut down yurt VM
    """

    ctx.obj.stop()


# Instance Commands ##################################################
def validate_image(ctx, param, value):
    try:
        server, alias = value.split(":")
        return (server, alias)
    except ValueError:
        raise click.BadParameter(
            "Use the format <server>:<alias> to specify the image. See 'yurt launch -h'")


@yurt.command()
@click.argument("image", callback=validate_image)
@click.argument("name")
@click.pass_context
def launch(ctx, image, name):
    """
    Create and start a container instance.

    \b
    IMAGE - Image to use as source. Uses <remote>:<alias> LXC syntax.
            e.g. ubuntu:18.04 or images:alpine/3.11
            Run 'yurt images' to see all available options.
    NAME  - Container name

    """

    if not isReady(ctx.obj, baseIndent):
        return

    server, alias = image
    lxd = ctx.obj.lxd
    lxd.createInstance(name, server, alias)


@yurt.command()
@click.argument("name")
@click.pass_context
def start(ctx, name):
    """
    Start instance.

    Start a container instance called NAME
    """
    click.echo()

    lxd = ctx.obj.lxd
    try:
        lxd.startInstance(name)
    except LXDError as e:
        logging.error(e.message)

    click.echo()


@yurt.command()
@click.argument("name")
@click.pass_context
def stop(ctx, name):
    """
    Stop instance.

    Stop a container called NAME
    """

    lxd = ctx.obj.lxd
    try:
        lxd.stopInstance(name)
    except LXDError as e:
        logging.error(e.message)


@yurt.command()
@click.argument("name")
@click.pass_context
def delete(ctx, name):
    """
    Delete instance.
    """
    lxd = ctx.obj.lxd
    try:
        lxd.deleteInstance(name)
    except LXDError as e:
        logging.error(e.message)


@yurt.command()
@click.pass_context
def status(ctx):
    """
    List instances.
    """

    click.echo()

    vm = ctx.obj
    lxd = vm.lxd
    if isReady(vm, baseIndent):
        try:
            instances = lxd.listInstances()
        except LXDError as e:
            logging.error(e.message)
            return

        if len(instances) > 0:
            for i in instances:
                print(i)
        else:
            logging.info("No instances found.")
            logging.info("Run 'yurt launch -h' for help getting started.")

    click.echo()


@yurt.command()
@click.pass_context
def images(ctx):
    """
    List available images
    """
    logging.warning("Not implemented")


# Interface Utilities
def isReady(vm, indent):
    if not vm.isInitialized():
        click.echo(
            f"{indent}yurt is not initialized. Initialize with 'yurt init'.")
        return False
    elif not vm.isRunning():
        click.echo(f"{indent}yurt is not running. Start with 'yurt up'.")
        return False

    return True
