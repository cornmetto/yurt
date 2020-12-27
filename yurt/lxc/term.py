import asyncio
from asyncio.tasks import FIRST_COMPLETED
import websockets
from websockets import WebSocketClientProtocol
import logging
import sys
from prompt_toolkit import ANSI, print_formatted_text
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

from yurt import config


class Line(object):
    def __init__(self, source: str, data: str):
        self.source = source
        self.data = data


class Source(Enum):
    remote = 1
    user = 2


async def remote_input(
    io_queue: asyncio.Queue,
    process_ws: WebSocketClientProtocol,
):
    while True:
        try:
            from_server_raw = await process_ws.recv()
            line = Line(Source.remote, from_server_raw.decode("utf-8"))
            io_queue.put_nowait(line)
        except websockets.exceptions.ConnectionClosedOK:
            return


def _read_user_input():
    line = sys.stdin.readline()
    return line


async def user_input(io_queue: asyncio.Queue):
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as executor:
        while True:
            line_str = await loop.run_in_executor(executor, _read_user_input)
            line = Line(Source.user, line_str)
            io_queue.put_nowait(line)


async def process_input(
    io_queue: asyncio.Queue,
    process_ws: WebSocketClientProtocol
):
    while True:
        line: Line = await io_queue.get()
        if line.source == Source.user:
            await process_ws.send(line.data.encode("utf-8"))
        else:
            print_formatted_text(ANSI(line.data), end="")


async def _start(process_url: str, control_url: str):
    async with websockets.connect(process_url) as process_ws:
        async with websockets.connect(control_url) as control_ws:
            try:
                io_queue = asyncio.Queue()
                io_tasks = [
                    asyncio.create_task(remote_input(io_queue, process_ws)),
                    asyncio.create_task(user_input(io_queue)),
                    asyncio.create_task(process_input(io_queue, process_ws))
                ]
                await asyncio.wait(io_tasks, return_when=asyncio.FIRST_COMPLETED)
            except KeyboardInterrupt:
                print(f"Keyboard interrupt. Send signal to {control_ws}")


def start(ws_uri: str, control_uri: str):

    logger = logging.getLogger()
    original_log_level = logger.getEffectiveLevel()
    logger.setLevel(logging.ERROR)

    process_url = f"ws://127.0.0.1:{config.lxd_port}{ws_uri}"
    control_url = f"ws://127.0.0.1:{config.lxd_port}{control_uri}"
    try:
        asyncio.get_event_loop().run_until_complete(_start(process_url, control_url))
    except websockets.exceptions.ConnectionClosedError as e:
        logger.setLevel(original_log_level)
        logging.debug(e)
        return

    logger.setLevel(original_log_level)
