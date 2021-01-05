import logging
import click
import os
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
    Containers can be accessed directly from the host using the listed
    IP addresses. See 'yurt list'.

    Only images at https://images.linuxcontainers.org are supported at
    this time.

    For help on a specific command, run 'yurt <cmd> -h'.


    NOTE:

    A handful of LXD's basic features are exposed in this CLI.
    Should you need more functionality, 'yurt vm ssh' will launch an
    interactive shell in     the Yurt VM. However, you will be on your
    own as changes you make to the system may affect how Yurt works.
    A reasonable use for this would be if you need to load extra kernel modules
    for use in containers.




    EXAMPLES:

    \b
    $ yurt launch ubuntu/20.04 c1           -   Launch an ubuntu/20.04 container named c1
    $ yurt stop c1                          -   Stop container c1
    $ yurt delete c1                        -   Delete container c1

    """

    console_handler = logging.StreamHandler()

    log_level = logging.INFO
    log_formatter = log_formatter = logging.Formatter("%(message)s")

    if debug:
        log_level = logging.DEBUG
        log_formatter = logging.Formatter(
            "%(levelname)s-%(name)s: %(message)s")
    else:
        os.environ["PYLXD_WARNINGS"] = "none"
        console_handler.addFilter(logging.Filter("root"))

    console_handler.setFormatter(log_formatter)
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.setLevel(log_level)


@main.group(name="vm")
def vm_():
    """
    Manage the Yurt VM.
    """


@vm_.command()
def init():
    """
    Initialize the VM.
    """

    try:
        vm.ensure_is_ready(prompt_init=False, prompt_start=True)
    except YurtException as e:
        logging.error(e.message)


@vm_.command(name="start")
def start_vm():
    """
    Start up the VM.
    """

    try:
        if vm.state() == vm.State.Running:
            logging.info("Yurt is already running.")
        else:
            vm.ensure_is_ready(prompt_init=True, prompt_start=False)
    except YurtException as e:
        logging.error(e.message)


@vm_.command()
def ssh():
    """
    SSH into the VM.
    """
    try:
        vm.ensure_is_ready()
        vm.launch_ssh()
    except YurtException as e:
        logging.error(e.message)


@vm_.command()
@click.option("-f", "--force", is_flag=True, help="Force shutdown.")
def restart(force):
    """
    Restart the VM.
    """

    try:
        if vm.state() == vm.State.Running:
            vm.stop(force=force)
        vm.ensure_is_ready(prompt_init=True, prompt_start=False)
    except YurtException as e:
        logging.error(e.message)


@vm_.command()
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Delete VM resources belonging to yurt even if destroy fails.",
)
def destroy(force):
    """
    Destroy the VM. Deletes all resources. Start over with 'yurt vm init'.
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


@vm_.command()
@click.option("-f", "--force", is_flag=True, help="Force shutdown.")
def halt(force):
    """
    Shut down the VM.
    """

    try:
        vm.stop(force=force)
    except YurtException as e:
        logging.error(e.message)
        if not force:
            logging.info(
                "Try forcing shutdown with 'yurt shutdown --force'.")


@vm_.command()
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


# Instances #############################################################


@main.command()
@click.argument("image", metavar="<image>")
@click.argument("name")
def launch(image, name):
    """
    Create and start a container.

    \b
    <image>     -   Image to use as source. e.g. ubuntu/18.04 or alpine/3.11.
                    Only images in https://images.linuxcontainers.org
                    are supported at this time. Run 'yurt images' to list them.
    NAME        -   Container name

    \b
    Container names must:
    * be between 1 and 63 characters long
    * be made up exclusively of letters, numbers and dashes from the ASCII table
    * not start with a digit or a dash
    * not end with a dash

    EXAMPLES:

    \b
    $ yurt launch ubuntu/18.04 c1       -   Create and start an ubuntu 18.04 container.

    """

    try:
        vm.ensure_is_ready()

        lxc.launch("images", image, name)

    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.argument("instances", metavar="<name>...", nargs=-1)
def start(instances):
    """
    Start one or more containers.
    """

    full_help_if_missing(instances)

    try:
        vm.ensure_is_ready()

        lxc.start(list(instances))

    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.argument("instances", metavar="<name>...", nargs=-1)
def stop(instances):
    """
    Stop one or more containers.
    """

    full_help_if_missing(instances)

    try:
        vm.ensure_is_ready()

        click.echo(lxc.stop(list(instances)))

    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.argument("instances", metavar="<name>...", nargs=-1)
def delete(instances):
    """
    Delete one or more containers.
    """

    full_help_if_missing(instances)

    try:
        vm.ensure_is_ready()

        lxc.delete(list(instances))

    except YurtException as e:
        logging.error(e.message)


@main.command(name="list")
def list_():
    """
    List containers.
    """

    try:
        vm.ensure_is_ready()

        instances = tabulate(lxc.list_(), headers="keys")
        if instances:
            click.echo(instances)
        else:
            click.echo(
                "No containers found. Create one with 'yurt launch <image> <name>'")

    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.argument("instance", metavar="<name>")
def shell(instance):
    """
    Start a shell in a container as root.

    The interactive terminal launched is not very sophisticated and is intended for
    bootstrapping your container. It starts a shell as root in <name>.
    Use it to create and configure users who can SSH using the container's
    IP address.
    """

    try:
        vm.ensure_is_ready()
        lxc.shell(instance)
    except YurtException as e:
        logging.error(e.message)


@main.command()
@click.option("-r", "--remote", is_flag=True, help="List remote images. Only images at https://images.linuxcontainers.org are supported at this time.")
def images(remote):
    """
    List images that can be used to launch a container.

    """

    remote_server = "images"
    try:
        vm.ensure_is_ready()

        if remote:
            images = tabulate(
                lxc.list_remote_images(remote_server), headers="keys", disable_numparse=True
            )
        else:
            images = tabulate(
                lxc.list_cached_images(), headers="keys", disable_numparse=True
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
