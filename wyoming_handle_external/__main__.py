#!/usr/bin/env python3
import argparse
import asyncio
import logging
import shlex
import time
from functools import partial
from pathlib import Path

from wyoming.asr import Transcript
from wyoming.event import Event
from wyoming.handle import Handled, NotHandled
from wyoming.info import Attribution, Describe, HandleModel, HandleProgram, Info
from wyoming.server import AsyncEventHandler, AsyncServer

_LOGGER = logging.getLogger()
_DIR = Path(__file__).parent


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--program", required=True, help="Program to run with arguments"
    )
    parser.add_argument(
        "--language", required=True, action="append", help="Supported language(s)"
    )
    parser.add_argument(
        "--info-name", default="external", help="Name used in Wyoming info message"
    )
    parser.add_argument("--uri", default="stdio://", help="unix:// or tcp://")
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    wyoming_info = Info(
        handle=[
            HandleProgram(
                name=args.info_name,
                description="Handle intents with an external program",
                attribution=Attribution(name="", url=""),
                installed=True,
                models=[
                    HandleModel(
                        name=args.info_name,
                        description="External program to handle intents",
                        attribution=Attribution(name="", url=""),
                        installed=True,
                        languages=args.language,
                    )
                ],
            )
        ],
    )

    _LOGGER.info("Ready")

    # Start server
    server = AsyncServer.from_uri(args.uri)

    try:
        await server.run(partial(ExternalEventHandler, wyoming_info, args))
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------


class ExternalEventHandler(AsyncEventHandler):
    """Event handler for clients."""

    def __init__(
        self,
        wyoming_info: Info,
        cli_args: argparse.Namespace,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.cli_args = cli_args
        self.wyoming_info_event = wyoming_info.event()
        self.client_id = str(time.monotonic_ns())
        self.command = shlex.split(self.cli_args.program)

        _LOGGER.debug("Client connected: %s", self.client_id)

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            _LOGGER.debug("Sent info to client: %s", self.client_id)
            return True

        if Transcript.is_type(event.type):
            transcript = Transcript.from_event(event)
            _LOGGER.debug("Running %s", self.command)
            proc = await asyncio.create_subprocess_exec(
                self.command[0],
                *self.command[1:],
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            input_text = transcript.text or ""
            stdout, stderr = await proc.communicate(input=input_text.encode("utf-8"))
            output_text = stdout.decode("utf-8")
            _LOGGER.debug(output_text)

            if proc.returncode == 0:
                await self.write_event(Handled(output_text).event())
            else:
                _LOGGER.error(stderr.decode("utf-8"))
                await self.write_event(NotHandled(output_text).event())

            return False

        if Transcript.is_type(event.type):
            await self.write_event(Handled("test").event())

        _LOGGER.debug("Unexpected event: type=%s, data=%s", event.type, event.data)

        return True


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
