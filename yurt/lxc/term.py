import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List

import colorama
import websockets
from websockets import WebSocketClientProtocol
from yurt import config
from yurt.exceptions import TermException


if config.system == config.System.windows:
    import msvcrt
    _getch = msvcrt.getch
else:
    # Issue #2: Support for MacOS
    raise TermException(f"Platform {config.system} not supported")


async def _user_input(process_ws: WebSocketClientProtocol):
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as executor:
        while True:
            input_bytes = await loop.run_in_executor(executor, _getch)
            try:
                await process_ws.send(input_bytes)
            except websockets.exceptions.ConnectionClosedOK:
                logging.debug("Websocket connection closed.")
                return
            except websockets.exceptions.ConnectionClosedError as e:
                logging.debug(
                    f"Websocket connection closed with an erorr: {e}")
                return


async def _remote_tty_input(process_ws: WebSocketClientProtocol):
    while True:
        try:
            input_bytes = await process_ws.recv()
            if len(input_bytes) > 0:
                _render(input_bytes)
        except websockets.exceptions.ConnectionClosedOK:
            logging.debug("Websocket connection closed.")
            return
        except websockets.exceptions.ConnectionClosedError as e:
            logging.debug(
                f"Websocket connection closed with an erorr: {e}")
            return


def _render(bytes_: bytes):
    try:
        print(bytes_.decode("utf-8"), end="")
    except UnicodeDecodeError as e:
        logging.debug(e)


async def _run(ws_url: str):
    async with websockets.connect(ws_url) as process_ws:
        io_tasks = [
            asyncio.create_task(_remote_tty_input(process_ws)),
            asyncio.create_task(_user_input(process_ws)),
        ]
        await asyncio.wait(io_tasks, return_when=asyncio.tasks.FIRST_COMPLETED)


def run(ws_url: str):
    logger = logging.getLogger()
    original_log_level = logger.getEffectiveLevel()
    logger.setLevel(logging.ERROR)
    colorama.init()

    try:
        asyncio.get_event_loop().run_until_complete(_run(ws_url))
    except websockets.exceptions.ConnectionClosedError as e:
        logger.setLevel(original_log_level)
        logging.debug(e)
        return

    colorama.deinit()
    logger.setLevel(original_log_level)
