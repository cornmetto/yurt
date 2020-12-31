import click
import logging


from yurt import config, util, exceptions


@click.group()
def main():
    console_handler = logging.StreamHandler()

    log_level = logging.DEBUG
    log_formatter = logging.Formatter(
        "%(levelname)s-%(name)s: %(message)s")

    console_handler.setFormatter(log_formatter)
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.setLevel(log_level)


@main.command()
def ssh_vm():
    import subprocess

    ssh_port = config.get_config(config.Key.ssh_port)
    subprocess.run(
        f"ssh -i {config.ssh_private_key_file} yurt@localhost -p {ssh_port}",
    )


if __name__ == "__main__":
    main()
