import logging
import click

from yurt.exceptions import YurtException
import config


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("-v", "--verbose", is_flag=True, help="Increase verbosity.")
@click.version_option()
def yurt(verbose):
    """
    Linux Containers for Development.

    Yurt sets up a virtual machine with a pre-configured LXD environment.

    A selection of LXD's commonly used features are exposed through the
    following commands. For help, use either -h or --help on any
    of the commands. e.g 'yurt launch --help'
    """

    consoleHandler = logging.StreamHandler()
    logFormatter = logging.Formatter("-> %(levelname)s-%(name)s: %(message)s")
    consoleHandler.setFormatter(logFormatter)
    if config.YURT_ENV == "development":
        logLevel = logging.DEBUG
    else:
        if verbose:
            consoleHandler.addFilter(logging.Filter('root'))
            logLevel = logging.DEBUG
        else:
            logLevel = logging.INFO

    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(consoleHandler)
    logger.setLevel(logLevel)


# VM #################################################################
@yurt.group()
@click.pass_context
def vm(ctx):
    """
    Manage the Yurt VM.
    """
    pass


@vm.command()
@click.pass_context
def init(ctx):
    """
    Initialize yurt VM.
    """
    from yurt import vm
    try:
        vm.init()
    except YurtException as e:
        logging.error(e.message)


@vm.command()
def destroy():
    """
    Delete all resources including the yurt VM.
    """
    from yurt import vm
    from yurt import lxc
    try:
        vm.destroy()
        lxc.destroy()
    except YurtException as e:
        logging.error(e.message)


@vm.command(name="start")
def start_vm():
    """
    Start yurt VM
    """
    from yurt import vm
    from yurt import lxc
    try:
        vm.start()
        lxc.ensureSetupIsComplete()
    except YurtException as e:
        logging.error(e.message)


@vm.command(name="stop")
def stop_vm():
    """
    Shut down yurt VM
    """
    from yurt import vm
    try:
        vm.shutdown()
    except YurtException as e:
        logging.error(e.message)


@vm.command(name="info")
def vm_info():
    """
    Show information about the Yurt VM.
    """
    from yurt import vm

    try:
        for k, v in vm.info().items():
            print(f"{k}: {v}")
    except YurtException as e:
        logging.error(e.message)


# Instances #############################################################


@yurt.command()
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
        checkVm()

        from yurt import lxc
        lxc.launch(image, name)

    except YurtException as e:
        logging.error(e.message)


@yurt.command()
@click.argument("instances", metavar="<instance>...", nargs=-1)
def start(instances):
    """
    Start a 'Stopped' instance.
    """

    checkVariadicArgument(instances)

    try:
        checkVm()

        from yurt import lxc
        lxc.start(list(instances))

    except YurtException as e:
        logging.error(e.message)


@yurt.command()
@click.argument("instances", metavar="<instance>...", nargs=-1)
@click.option("-f", "--force", help="Force the instance to shutdown", is_flag=True)
def stop(instances, force):
    """
    Stop an instance.
    """
    checkVariadicArgument(instances)

    try:
        checkVm()

        from yurt import lxc
        print(lxc.stop(list(instances), force=force))

    except YurtException as e:
        logging.error(e.message)


@yurt.command()
@click.argument("instances", metavar="<instance>...", nargs=-1)
@click.option("-f", "--force", help="Force deletion of a running instance", is_flag=True)
def delete(instances, force):
    """
    Delete an instance.
    """
    checkVariadicArgument(instances)

    try:
        checkVm()

        from yurt import lxc
        lxc.delete(list(instances), force=force)

    except YurtException as e:
        logging.error(e.message)


@yurt.command()
@click.argument("instance", metavar="<instance>")
def info(instance):
    """
    Show information about an instance.
    """

    try:
        checkVm()

        from yurt import lxc
        lxc.info(instance)

    except YurtException as e:
        logging.error(e.message)


@yurt.command(name="list")
@click.pass_context
def list_(ctx):
    """
    List instances.
    """

    try:
        checkVm()

        from tabulate import tabulate
        from yurt import lxc

        instances = tabulate(lxc.list_(), headers="keys")
        print(instances)

    except YurtException as e:
        logging.error(e.message)


# CLI Utilities ########################################################


def checkVm():
    """
    Raise YurtException with the appropriate message if the VM is not
    initialized and running.
    """
    from yurt import vm

    vmState = vm.state()
    if vmState == vm.VMState.NotInitialized:
        raise YurtException(
            "The Yurt VM has not been initialized. Initialize with 'yurt vm init'")
    if vmState == vm.VMState.Stopped:
        raise YurtException(
            "The Yurt VM is not running. Start it up with 'yurt vm start'")


def checkVariadicArgument(arg):
    if not arg:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()
