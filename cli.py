import logging
import click

import config

from yurt.exceptions import YurtException
from yurt import vm
from yurt import lxc


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("-v", "--verbose", is_flag=True, help="Increase verbosity.")
@click.version_option()
def main(verbose):
    """
    Linux Containers for Development.

    Yurt sets up a virtual machine with a pre-configured LXD Server.
    Containers can be accessed directly from the host using their assigned
    IP addresses. Run 'yurt ssh <instance>' to quickly SSH into a running
    instance.

    A selection of LXD's commonly used features are exposed through the
    following commands. For help, use either -h or --help on any
    of the commands. e.g 'yurt launch --help'.

    """

    console_handler = logging.StreamHandler()
    log_formatter = logging.Formatter("-> %(levelname)s-%(name)s: %(message)s")
    console_handler.setFormatter(log_formatter)
    if config.YURT_ENV == "development":
        logLevel = logging.DEBUG
    else:
        if verbose:
            console_handler.addFilter(logging.Filter('root'))
            logLevel = logging.DEBUG
        else:
            logLevel = logging.INFO

    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.setLevel(logLevel)


# VM #################################################################
@main.group(name="vm")
@click.pass_context
def vm_cmd(ctx):
    """
    Manage the Yurt VM.
    """
    pass


@vm_cmd.command()
@click.pass_context
def init(ctx):
    """
    Initialize yurt VM.
    """

    try:
        vm.init()
    except YurtException as e:
        logging.error(e.message)


@vm_cmd.command()
@click.option("-f", "--force", is_flag=True, help="Force deletion of VM resources belonging to yurt.")
def destroy(force):
    """
    Delete all resources including the yurt VM.
    """

    try:
        vm_state = vm.state()

        if vm_state == vm.State.NotInitialized and not force:
            logging.info("yurt has not been initialized.")
        elif vm_state == vm.State.Running and not force:
            logging.error(
                "Cannot destroy while VM is running. Stop it first with 'yurt vm stop'")
        else:
            vm.destroy()
            lxc.destroy()
    except YurtException as e:
        if force:
            vm.force_delete_yurt_dir()
        else:
            logging.error(e.message)
            logging.info(
                "Run 'yurt vm delete --force' to force deletion of VM resources belonging to Yurt.")
    except Exception:
        if force:
            vm.force_delete_yurt_dir()


@vm_cmd.command(name="start")
def start_vm():
    """
    Start yurt VM
    """

    try:
        vm_state = vm.state()

        if vm_state == vm.State.NotInitialized:
            logging.info(
                "Yurt VM has not been initialized. Initialze with 'yurt init'.")
        elif vm_state == vm.State.Running:
            logging.info("VM is already running")
        else:
            vm.start()
            lxc.ensureSetupIsComplete()

    except YurtException as e:
        logging.error(e.message)


@vm_cmd.command(name="stop")
def stop_vm():
    """
    Shut down yurt VM
    """

    try:
        vm.shutdown()
    except YurtException as e:
        logging.error(e.message)


@vm_cmd.command(name="info")
def vm_info():
    """
    Show information about the Yurt VM.
    """

    try:
        for k, v in vm.info().items():
            print(f"{k}: {v}")
    except YurtException as e:
        logging.error(e.message)


# Instances #############################################################


@main.command()
@click.argument("image")
@click.argument("name")
@click.pass_context
def launch(ctx, image, name):
    """
    Create and start an instance.

    \b
    IMAGE - Image to use as source. Uses <remote>:<alias> LXC syntax.
            e.g. ubuntu:18.04 or images:alpine/3.11
            Run 'yurt images' to see all available options.
    NAME  - Container name

    """

    try:
        check_vm()

        lxc.launch(image, name)

    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.argument("instances", metavar="<instance>...", nargs=-1)
def start(instances):
    """
    Start a 'Stopped' instance.
    """

    check_variadic_argument(instances)

    try:
        check_vm()

        lxc.start(list(instances))

    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.argument("instances", metavar="<instance>...", nargs=-1)
@click.option("-f", "--force", help="Force the instance to shutdown", is_flag=True)
def stop(instances, force):
    """
    Stop an instance.
    """
    check_variadic_argument(instances)

    try:
        check_vm()

        print(lxc.stop(list(instances), force=force))

    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.argument("instances", metavar="<instance>...", nargs=-1)
@click.option("-f", "--force", help="Force deletion of a running instance", is_flag=True)
def delete(instances, force):
    """
    Delete an instance.
    """
    check_variadic_argument(instances)

    try:
        check_vm()

        lxc.delete(list(instances), force=force)

    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.argument("instance", metavar="<instance>")
def info(instance):
    """
    Show information about an instance.
    """

    try:
        check_vm()

        lxc.info(instance)

    except YurtException as e:
        logging.error(e.message)


@main.command(name="list")
@click.pass_context
def list_(ctx):
    """
    List instances.
    """

    try:
        check_vm()

        from tabulate import tabulate

        instances = tabulate(lxc.list_(), headers="keys")
        print(instances)

    except YurtException as e:
        logging.error(e.message)


# CLI Utilities ########################################################


def check_vm():
    """
    Raise YurtException with the appropriate message if the VM is not
    initialized and running.
    """

    vm_state = vm.state()
    if vm_state == vm.State.NotInitialized:
        raise YurtException(
            "The VM has not been initialized. Initialize with 'yurt vm init'")
    if vm_state == vm.State.Stopped:
        raise YurtException(
            "The VM is not running. Start it up with 'yurt vm start'")


def check_variadic_argument(arg):
    if not arg:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()
