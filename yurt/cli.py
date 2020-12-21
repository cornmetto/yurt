import logging
import click
from tabulate import tabulate

from yurt.exceptions import YurtException
from yurt import vm, lxc, config


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("--debug", is_flag=True, help="Increase verbosity.")
@click.version_option(version=config.version, prog_name="yurt")
def main(debug):
    """
    Linux Containers for Development.

    Yurt sets up a virtual machine with a pre-configured LXD server.
    Services in containers can be accessed directly from the host using
    the listed IP addresses. See 'yurt list'.

    A selection of LXD's commonly used features are exposed through the
    following commands. For help, use either -h or --help on any
    of the commands. e.g 'yurt launch --help'.

    For simplicity, only images at https://images.linuxcontainers.org are
    supported at this time.


    EXAMPLES:

    \b
    $ yurt launch alpine/3.11 c1     -   Launch an alpine/3.11 instances named c1
    $ yurt stop c1                          -   Stop instnace c1
    $ yurt delete c1                        -   Delete instnce c1

    """

    console_handler = logging.StreamHandler()
    if config.YURT_ENV == "development":
        logLevel = logging.DEBUG
        log_formatter = logging.Formatter(
            "%(levelname)s-%(name)s: %(message)s")
    else:
        log_formatter = logging.Formatter("%(message)s")
        if debug:
            logLevel = logging.DEBUG
        else:
            console_handler.addFilter(logging.Filter("root"))
            logLevel = logging.INFO

    console_handler.setFormatter(log_formatter)
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.setLevel(logLevel)


@main.command()
def init():
    """
    Initialize the Yurt VM.
    """

    try:
        vm.ensure_is_ready(prompt_init=False, prompt_start=True)
    except YurtException as e:
        logging.error(e.message)


@main.command()
def boot():
    """
    Start up the Yurt VM.
    """

    try:
        if vm.state() == vm.State.Running:
            logging.info("Yurt is already running.")
        else:
            vm.ensure_is_ready(prompt_init=True, prompt_start=False)
    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.option("-f", "--force", is_flag=True, help="Force shutdown.")
def reboot(force):
    """
    Reboot the Yurt VM.
    """

    try:
        if vm.state() == vm.State.Running:
            vm.stop(force=force)
        vm.ensure_is_ready(prompt_init=True, prompt_start=False)
    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Delete VM resources belonging to yurt even if destroy fails.",
)
def destroy(force):
    """
    Destroy the Yurt VM. Deletes all resources.
    """

    try:
        vm_state = vm.state()

        if vm_state == vm.State.NotInitialized:
            logging.info(
                "The VM has not been initialized. Initialize with 'yurt vm init'."
            )
        elif vm_state == vm.State.Running:
            logging.error(
                "Cannot destroy while VM is running. Stop it first with 'yurt shutdown'"
            )
        else:
            vm.destroy()
            lxc.destroy()
    except YurtException as e:
        if force:
            vm.delete_instance_files()
        else:
            logging.error(e.message)
            logging.info(
                "Run 'yurt vm destroy --force' to force deletion of VM resources belonging to Yurt."
            )
    except Exception:
        if force:
            vm.delete_instance_files()


@main.command()
@click.option("-f", "--force", is_flag=True, help="Force shutdown.")
def shutdown(force):
    """
    Shutdown the yurt VM.
    """

    try:
        vm.stop(force=force)
    except YurtException as e:
        logging.error(e.message)
        if not force:
            logging.info(
                "Try forcing shutdown with 'yurt shutdown --force'.")


# Instances #############################################################


@main.command()
@click.argument("image", metavar="<alias>")
@click.argument("name")
def launch(image, name):
    """
    Create and start an instance.

    \b
    <alias>     -   Alias of image to use as source. e.g. ubuntu/18.04 or
                    alpine/3.11.
                    Only images in https://images.linuxcontainers.org
                    are supported at this time. Run 'yurt images' to list them.
    NAME        -   Instance name

    \b
    Instance names must:
    * be between 1 and 63 characters long
    * be made up exclusively of letters, numbers and dashes from the ASCII table
    * not start with a digit or a dash
    * not end with a dash

    EXAMPLES:

    \b
    $ yurt launch ubuntu/18.04 c1       -   Create and start an ubuntu 18.04 instance.

    """

    try:
        vm.ensure_is_ready()

        lxc.launch(f"images:{image}", name)

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
        vm.ensure_is_ready()

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
        vm.ensure_is_ready()

        click.echo(lxc.stop(list(instances), force=force))

    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.argument("instances", metavar="<instance>...", nargs=-1)
@click.option(
    "-f", "--force", help="Force deletion of a running instance", is_flag=True
)
def delete(instances, force):
    """
    Delete an instance.
    """

    full_help_if_missing(instances)

    try:
        vm.ensure_is_ready()

        lxc.delete(list(instances), force=force)

    except YurtException as e:
        logging.error(e.message)


@main.command()
def info():
    """
    Show information about the Yurt VM.
    """

    try:
        for k, v in vm.info().items():
            click.echo(f"{k}: {v}")

        vm.ensure_is_ready()
    except YurtException as e:
        logging.error(e.message)


@main.command(name="list")
def list_():
    """
    List instances.
    """

    try:
        vm.ensure_is_ready()

        instances = tabulate(lxc.list_(), headers="keys")
        if instances:
            click.echo(instances)
        else:
            click.echo(
                "No instances found. Create one with 'yurt launch <image> <name>'")

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
        vm.ensure_is_ready()
        lxc.shell(instance)
    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.option("-c", "--cached", is_flag=True, help="List cached images only.")
def images(cached):
    """
    List available images.

    At this time, only images at https://images.linuxcontainers.org are supported.
    """

    remote = "images"
    try:
        vm.ensure_is_ready()

        if cached:
            images = tabulate(
                lxc.list_cached_images(), headers="keys", disable_numparse=True
            )
        else:
            images = tabulate(
                lxc.list_remote_images(remote), headers="keys", disable_numparse=True
            )

        click.echo(images)

    except YurtException as e:
        logging.error(e.message)


# CLI Utilities ########################################################

def full_help_if_missing(arg):
    if not arg:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
