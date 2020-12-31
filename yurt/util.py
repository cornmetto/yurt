import logging
import os
from typing import List

from yurt.exceptions import CommandException, CommandTimeout, YurtException


def download_file(url: str, destination: str, show_progress=False):
    import shutil

    import requests
    from click import progressbar

    try:
        with requests.get(url, stream=True) as r:
            with open(destination, 'wb') as f:
                total_bytes = r.headers.get("content-length")

                if total_bytes is None or not show_progress:
                    shutil.copyfileobj(r.raw, f)
                else:
                    with progressbar(length=int(total_bytes)) as bar:
                        for chunk in r.iter_content(chunk_size=4096):
                            f.write(chunk)
                            bar.update(len(chunk))
    except (
        requests.Timeout,
        requests.ConnectionError,
        requests.HTTPError,
        requests.TooManyRedirects
    ) as e:
        logging.debug(e)
        if os.path.isfile(destination):
            os.remove(destination)

        raise YurtException("Download error")
    except OSError as e:
        logging.debug(e)
        if os.path.isfile(destination):
            os.remove(destination)

        raise YurtException("Write error")


def is_sha256(file_path: str, sha256: str):
    import hashlib

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest() == sha256


def retry(fn, retries=3, wait_time=5, message=None):
    while True:
        try:
            return fn()
        except Exception as e:
            if retries > 0:
                retries -= 1
                if message:
                    logging.info(message)
                sleep_for(wait_time, show_spinner=True)
            else:
                raise e


def find(fn, iterable, default):
    return next(filter(lambda i: fn(i), iterable), default)


def _spinner():
    frames = [
        "⣾",
        "⣽",
        "⣻",
        "⢿",
        "⡿",
        "⣟",
        "⣯",
        "⣷"
    ]

    frame = 0
    while True:
        if frame >= len(frames):
            frame = 0

        yield frames[frame]
        frame += 1


def _render_spinner(spinner, clear=False):
    import shutil
    import sys

    columns, _ = shutil.get_terminal_size()

    width = columns - 5
    if clear:
        print(f"\r{' ' * width}\r", end="", file=sys.stderr)
    elif spinner:
        frame = next(spinner)
        print(f"\r{frame}{' ' * (width - len(frame))}]",
              end="", file=sys.stderr)


def async_spinner(worker_future):
    import time

    frame_step = 0.075
    spinner = _spinner()

    _render_spinner(None, clear=True)
    while not worker_future.done():
        _render_spinner(spinner)
        time.sleep(frame_step)
    _render_spinner(None, clear=True)


def sleep_for(timeout: float, show_spinner=False):
    import time

    if show_spinner:
        _render_spinner(None, clear=True)
        frame_step = 0.1
        spinner = _spinner()
        while timeout > 0:
            _render_spinner(spinner)
            time.sleep(frame_step)
            timeout -= frame_step
        _render_spinner(None, clear=True)
    else:
        time.sleep(timeout)


def _run(cmd, stdin=None, capture_output=True, timeout=None, env=None):
    import subprocess

    logging.debug(f"Running: {cmd}")

    new_env = dict(os.environ)
    if env:
        new_env.update(env)

    try:
        res = subprocess.run(cmd, capture_output=capture_output,
                             text=True, check=True, env=new_env, input=stdin, timeout=timeout)
        return res.stdout

    except subprocess.CalledProcessError as e:
        if e.stdout:
            logging.debug(f"{os.path.basename(cmd[0])}: {e.stdout}")

        error_message = "Command failed."
        if e.stderr:
            logging.debug(f"{os.path.basename(cmd[0])}: {e.stderr}")
            error_message = e.stderr
        raise CommandException(error_message)

    except subprocess.TimeoutExpired as e:
        logging.debug(e)
        raise CommandTimeout("Operation timed out.")

    except KeyboardInterrupt:
        logging.error("Operation Aborted")


def run(cmd: List[str], show_spinner: bool = False, **kwargs):
    """
    Run a command.
    - cmd: List[str]
        The command to be run.
    - capture_output: bool = True
        Capture stdout and stderr. Return stdout and log stderr.
    - show_spinner: bool = False
        Show a spinner while command runs.
        Spinner is shown only if capture_output=True.
    - timeout: float
        Cancel command if it runs for more than this.
    """
    if show_spinner:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as executor:
            cmd_future = executor.submit(_run, cmd, **kwargs)
            executor.submit(async_spinner, cmd_future)
            return cmd_future.result()

    else:
        return _run(cmd, **kwargs)


def random_string(length=10):
    import random
    import string

    alphabet = string.ascii_lowercase + string.digits
    return ''.join(random.choices(alphabet, k=length))


def prompt_user(message: str, options: List[str] = None):
    try:
        if options:
            options_str = "/".join(options)
            user_input = input(f"{message} [{options_str}] ")
            choice = find(lambda o: o.lower() ==
                          user_input.lower(), options, None)
            if not choice:
                raise YurtException(f"Unexpected response: {user_input}")
            return choice
        else:
            return input(message)

    except KeyboardInterrupt:
        raise YurtException("User Canceled")
