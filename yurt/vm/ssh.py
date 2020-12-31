from io import StringIO
import logging
from contextlib import contextmanager

from fabric import Connection as FabricConnection
from invoke.exceptions import Failure, ThreadException, UnexpectedExit
from paramiko import ssh_exception
from yurt import config
from yurt.exceptions import VMException


@contextmanager
def _connection():
    connection = FabricConnection(
        "localhost",
        user=config.user_name,
        port=config.get_config(config.Key.ssh_port),
        connect_kwargs={"key_filename": config.ssh_private_key_file}
    )
    try:
        yield connection
    finally:
        connection.close()


def _connection_exec(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except ssh_exception.NoValidConnectionsError:
        raise VMException("SSH connection failed")
    except ssh_exception.SSHException as e:
        logging.debug(e)
        raise VMException("SSH connection failed")
    except UnexpectedExit as e:
        logging.debug(e)
        raise VMException("Nonzero exit code")
    except Failure as e:
        logging.debug(e)
        raise VMException("Command was not completed")
    except ThreadException as e:
        logging.debug(e)
        raise VMException(
            "Background I/O threads encountered exceptions.")


def run_cmd(cmd, hide_output=False, stdin=None):
    in_stream = None
    if stdin:
        in_stream = StringIO(initial_value=stdin)

    with _connection() as connection:
        result = _connection_exec(
            connection.run, cmd, hide=hide_output, in_stream=in_stream
        )

        return (result.stdout, result.stderr)


def put_file(local_path: str, remote_path: str):
    with _connection() as connection:
        _connection_exec(connection.put, local_path, remote_path)
