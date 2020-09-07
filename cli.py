import logging
import click
from tabulate import tabulate

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

    Yurt sets up a virtual machine with a pre-configured LXD server.
    Containers can be accessed directly from the host using the listed IP
    addresses.

    A selection of LXD's commonly used features are exposed through the
    following commands. For help, use either -h or --help on any
    of the commands. e.g 'yurt launch --help'.


    EXAMPLES:

    \b
    $ yurt vm init                          -   Initialize the VM.
    $ yurt vm start                         -   Start the VM
    $ yurt launch images:alpine/3.11 c1     -   Launch an alpine/3.11 instances named c1  
    $ yurt stop c1                          -   Stop instnace c1
    $ yurt delete c1                        -   Delete instnce c1

    """

    console_handler = logging.StreamHandler()
    log_formatter = logging.Formatter("-> %(levelname)s-%(name)s: %(message)s")
    console_handler.setFormatter(log_formatter)
    if config.YURT_ENV == "development":
        logLevel = logging.DEBUG
    else:
        if verbose:
            logLevel = logging.DEBUG
        else:
            console_handler.addFilter(logging.Filter('root'))
            logLevel = logging.INFO

    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.setLevel(logLevel)


# VM #################################################################
@main.group(name="vm")
def vm_cmd():
    """
    Manage the Yurt VM.
    """
    pass


@vm_cmd.command()
def init():
    """
    Initialize yurt VM.
    """

    try:
        vm.init()
    except YurtException as e:
        logging.error(e.message)


@vm_cmd.command()
@click.option("-f", "--force", is_flag=True, help="Delete VM resources belonging to yurt even if destroy fails.")
def destroy(force):
    """
    Delete all resources including the yurt VM.
    """

    try:
        vm_state = vm.state()

        if vm_state == vm.State.NotInitialized:
            logging.info("yurt has not been initialized.")
        elif vm_state == vm.State.Running:
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
                "Yurt VM has not been initialized. Initialze with 'yurt vm init'.")
        elif vm_state == vm.State.Running:
            logging.info("VM is already running")
        else:
            vm.start()
            lxc.ensure_setup_is_complete()

    except YurtException as e:
        logging.error(e.message)


@vm_cmd.command(name="stop")
def stop_vm():
    """
    Shut down yurt VM
    """

    try:
        vm.stop()
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
@click.argument("image", metavar="<remote>:<alias>")
@click.argument("name")
def launch(image, name):
    """
    Create and start an instance.

    \b
    <remote>:<alias>    -   Remote and alias of image to use as source.
                            e.g. ubuntu:18.04 or images:alpine/3.11
                            Refer to 'yurt remotes' and 'yurt images' for
                            more information
    NAME                -   Container name

    \b
    Instance names must:
    * be between 1 and 63 characters long
    * be made up exclusively of letters, numbers and dashes from the ASCII table
    * not start with a digit or a dash
    * not end with a dash

    EXAMPLES:

    \b
    $ yurt launch ubuntu:18.04 c1       -   Create and start an ubuntu 18.04 instance.

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

    full_help_if_missing(instances)

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
    full_help_if_missing(instances)

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
    full_help_if_missing(instances)

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
def list_():
    """
    List instances.
    """

    try:
        check_vm()

        instances = tabulate(lxc.list_(), headers="keys")
        click.echo(instances)

    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.argument("instance", metavar="<instance>")
def shell(instance):
    """
    Start a shell in an instance.

    This is intended for bootstrapping your instances. It starts a shell 
    as root in <instance>.
    Use it to create and configure users who can SSH using the instance's
    IP address.
    """
    try:
        check_vm()
        lxc.shell(instance)
    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.argument("remote", metavar="<remote>")
def images(remote):
    """
    List images that are available on <remote>.

    Run 'yurt remotes' to view available sources.

    If <remote> is 'cached', images cached on the local server are listed.

    EXAMPLES:

    \b
    $ yurt images ubuntu        -       List images from 'ubuntu' remote.
    $ yurt images cached        -       List cached images.

    """
    try:
        check_vm()

        if remote == "cached":
            images = tabulate(
                lxc.list_cached_images(),
                headers="keys",
                disable_numparse=True
            )
        else:
            images = tabulate(
                lxc.list_remote_images(remote),
                headers="keys",
                disable_numparse=True
            )

        click.echo(images)

    except YurtException as e:
        logging.error(e.message)


@main.command()
def remotes():
    """
    List remotes available for use as image sources.
    """
    try:
        click.echo(tabulate(lxc.remotes(), headers="keys"))

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


def full_help_if_missing(arg):
    if not arg:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()
