import asyncio
import websockets
from websockets import WebSocketClientProtocol
import logging
import re
import os
from prompt_toolkit import PromptSession, ANSI, print_formatted_text
from prompt_toolkit.patch_stdout import patch_stdout

from yurt import config


async def _eval_loop(process_ws: WebSocketClientProtocol, control_ws: WebSocketClientProtocol) -> bool:
    session = PromptSession()
    from_server_raw = await process_ws.recv()
    print(f"--from_server_raw: {from_server_raw}")

    if len(from_server_raw) == 0:
        return False
    elif (
        from_server_raw.endswith(b" # \x1b[6n") or
        from_server_raw.endswith(b" $ \x1b[6n")
    ):
        from_server_str = re.sub(
            "\r", "",
            from_server_raw.decode("utf-8")
        )
        cmd = await session.prompt_async(ANSI(from_server_str))
        await process_ws.send(f"{cmd}\n".encode('utf-8'))

    return True


async def _interact(process_url: str, control_url: str):
    async with websockets.connect(process_url) as process_ws:
        async with websockets.connect(control_url) as control_ws:
            with patch_stdout():
                loop = True
                while loop:
                    loop = await _eval_loop(process_ws, control_ws)


def interact(ws_uri: str, control_uri: str):

    logger = logging.getLogger()
    original_log_level = logger.getEffectiveLevel()
    logger.setLevel(logging.ERROR)

    process_url = f"ws://127.0.0.1:{config.lxd_port}{ws_uri}"
    control_url = f"ws://127.0.0.1:{config.lxd_port}{control_uri}"
    try:
        asyncio.get_event_loop().run_until_complete(_interact(process_url, control_url))
    except websockets.exceptions.ConnectionClosedError as e:
        logging.debug(e)
        return

    logger.setLevel(original_log_level)
