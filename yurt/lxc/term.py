import asyncio
import logging
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import List

import pyte
import websockets
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.renderer import Renderer
from prompt_toolkit.styles import DummyStyle
from websockets import WebSocketClientProtocol
from yurt import config
from yurt.exceptions import TermException


class Term(object):
    def __init__(self, process_uri: str, control_uri: str):
        self.process_url = f"ws://127.0.0.1:{config.lxd_port}{process_uri}"
        self.control_url = f"ws://127.0.0.1:{config.lxd_port}{control_uri}"

        columns, rows = shutil.get_terminal_size()
        self.screen = pyte.screens.Screen(columns, rows)
        self.stream = pyte.Stream(self.screen)

        if config.system == config.System.windows:
            import msvcrt

            from prompt_toolkit.output.win32 import Win32Output

            self._getch = msvcrt.getch
            self._output = Win32Output(sys.stdout)
        else:
            # Issue #2: Support for MacOS
            raise TermException(f"Platform {config.system} not supported")

        self._renderer = Renderer(DummyStyle, self._output)
        self._root_container = Window(content=BufferControl(buffer=Buffer()))
        self._layout = Layout(self._root_container)
        self._app = Application(full_screen=True)

    async def _user_input(self, process_ws: WebSocketClientProtocol):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            while True:
                input_bytes = await loop.run_in_executor(executor, self._getch)
                try:
                    await process_ws.send(input_bytes)
                except websockets.exceptions.ConnectionClosedOK:
                    logging.debug("Websocket connection closed.")
                    return
                except websockets.exceptions.ConnectionClosedError as e:
                    logging.debug(
                        f"Websocket connection closed with an erorr: {e}")
                    return

    async def _remote_tty_input(self, process_ws: WebSocketClientProtocol):
        while True:
            try:
                input_bytes = await process_ws.recv()
                if len(input_bytes) > 0:
                    self.stream.feed(input_bytes.decode("utf-8"))
                    self._render()
            except websockets.exceptions.ConnectionClosedOK:
                logging.debug("Websocket connection closed.")
                return
            except websockets.exceptions.ConnectionClosedError as e:
                logging.debug(
                    f"Websocket connection closed with an erorr: {e}")
                return

    def _clip_bottom(self, lines: List[str]):
        i, j = 0, 0
        while j < len(lines):
            if len(lines[j].strip()) > 0:
                i = j
            j += 1
        return lines[0:i+1]

    def _write_at(self, row: int, column: int, line: str):
        self._output.write(line)

    def _reset_cursor(self, row: int, column: int):
        pass

    def _render(self):
        columns, rows = shutil.get_terminal_size()
        self.screen.resize(columns, rows)

        lines = self._clip_bottom(self.screen.display)
        for i in self.screen.dirty:
            if i < len(lines):
                self._write_at(i, 0, lines[i])

        prompt_row, prompt_col = len(lines) - 1, len(lines[-1])
        self._reset_cursor(prompt_row, prompt_col)

        self.screen.dirty.clear()
        self._renderer.render(self._app, layout=Layout(self._root_container))

    def _run_app(self):

    async def _run(self):
        async with websockets.connect(self.process_url) as process_ws:
            async with websockets.connect(self.control_url) as control_ws:

                io_tasks = [
                    asyncio.create_task(self._remote_tty_input(process_ws)),
                    asyncio.create_task(self._user_input(process_ws)),
                ]
                await asyncio.wait(io_tasks, return_when=asyncio.tasks.FIRST_COMPLETED)

    def run(self):
        logger = logging.getLogger()
        original_log_level = logger.getEffectiveLevel()
        logger.setLevel(logging.ERROR)

        try:
            asyncio.get_event_loop().run_until_complete(self._run())
        except websockets.exceptions.ConnectionClosedError as e:
            logger.setLevel(original_log_level)
            logging.debug(e)
            return

        logger.setLevel(original_log_level)
