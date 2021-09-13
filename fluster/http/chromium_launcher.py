# Fluster - testing framework for decoders conformance
# Copyright (C) 2021, Fluendo, S.A.
#  Author: Manuel Jimeno Martínez <mjimeno@fluendo.com>, Fluendo, S.A.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import asyncio
import os
import subprocess
from asyncio.subprocess import Process

from typing import Optional, Tuple


class ChromiumLauncher:
    """A wrapper to start/stop the Chrome browser"""

    WEB_CODECS = "--enable-blink-features=WebCodecs"
    ENABLE_HARDWARE_ACCELERATION = (
        "--enable-features=VaapiVideoDecoder --ignore-gpu-blocklist --use-gl=desktop"
    )
    CHROMIUM = "/opt/google/chrome/chrome"
    CHROMIUM_UNSTABLE = "/opt/google/chrome-unstable/chrome"
    _terminate_timeout = 2

    def __init__(
        self,
        server_address: Tuple[str, int] = ("localhost", 8000),
        environment: Optional[str] = None,
        hardware_acceleration: bool = False,
        unstable: bool = False,
    ):
        self._environment: Optional[str] = environment
        self._server_address: Tuple[str, int] = server_address
        self._hardware_acceleration: bool = hardware_acceleration
        self._process: Optional[Process] = None
        self._unstable: bool = unstable

    async def run_async(self) -> None:
        """We start the asynchronous execution of the browser."""
        command: str = ""
        server_address = self._server_address[0]
        if server_address == "0.0.0.0":
            server_address = "localhost"

        if self._environment:
            command = self._environment + " "

        if self._unstable:
            command += f"{ChromiumLauncher.CHROMIUM_UNSTABLE} "
        else:
            command += f"{ChromiumLauncher.CHROMIUM} "

        command += f"{ChromiumLauncher.WEB_CODECS} "

        if self._hardware_acceleration:
            command += f"{ChromiumLauncher.ENABLE_HARDWARE_ACCELERATION} "

        command += f"http://{server_address}:{self._server_address[1]}"

        self._process = await asyncio.create_subprocess_shell(command)

    async def stop_async(self) -> None:
        """We kill all the instances of the browser."""
        cmd = ["ps", "-A"]
        with subprocess.Popen(cmd, stdout=subprocess.PIPE) as process:
            output, _ = process.communicate()
            target_process = "chrome"
            for line in output.splitlines():
                if target_process in str(line):
                    pid = int(line.split(None, 1)[0])
                    if self._process and pid == self._process.pid:
                        self._process.kill()
                    else:
                        os.kill(pid, 9)

    def run(self) -> None:
        """Calling the asynchronous run function from synchronous run function"""
        asyncio.run(self.run_async())

    def stop(self) -> None:
        """Calling the asynchronous stop function from synchronous stop function"""
        asyncio.run(self.stop_async())
