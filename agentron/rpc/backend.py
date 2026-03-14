from __future__ import annotations

import os
import atexit
import signal
import asyncio
import logging

from typing import Callable
from pathlib import Path

from agentron.messages import AssistantMessage, StreamingMessage
from agentron.typing import ToolSchema
from agentron.model import Model
from agentron.rpc.client import JsonRpcClient
from agentron.rpc.utils import get_safe_socket_path
from agentron.rpc import api
from agentron.path import get_flux_root

logger = logging.getLogger(__name__)

type StreamingMessageHandler = Callable[[StreamingMessage], None]


class FluxBackend:
    _shared_instance: FluxBackend | None = None
    _instance_lock = asyncio.Lock()

    @classmethod
    async def get(cls):
        """
        Returns the singleton instance of this backend.
        The first invocation creates the instance and starts the Flux process.
        """
        if cls._shared_instance is not None:
            return cls._shared_instance

        async with cls._instance_lock:
            if cls._shared_instance is not None:
                return cls._shared_instance

            instance = cls()
            await instance.process.start()
            await instance.rpc.connect()
            cls._shared_instance = instance

        return cls._shared_instance

    def __init__(self):
        self.process = FluxProcess()
        self.rpc = JsonRpcClient(
            socket_path=self.process.socket_path,
            response_timeout=5 * 60,
        )
        self.rpc.on_notification(
            method=api.NotificationKind.STREAMING_MESSAGE,
            handler=self._dispatch_streaming_message,
        )
        self.streaming_message_handlers: dict[str, StreamingMessageHandler] = {}

    async def start_session(
        self,
        session_id: str,
        model: Model,
        tools: list[ToolSchema],
        api_key: str | None,
    ) -> None:
        await self.rpc.request(
            method=api.RequestKind.SESSION_START,
            params=api.SessionStartRequest(
                session_id=session_id,
                model=model,
                tools=tools,
                api_key=api_key,
            ),
        )

    async def transmit(
        self,
        messages: list[api.AgentMessage],
        *,
        session_id: str,
        reasoning_level: api.ModelReasoningLevel,
    ) -> AssistantMessage:
        return await self.rpc.request(
            method=api.RequestKind.TRANSMIT,
            params=api.TransmitRequest(
                session_id=session_id,
                messages=messages,
                reasoning=reasoning_level,
            ),
        )

    def _dispatch_streaming_message(self, message: StreamingMessage) -> None:
        handler = self.streaming_message_handlers.get(message['session_id'])
        if handler is not None:
            handler(message)


class FluxTransmitter:
    def __init__(
        self,
        session_id: str,
        tools: list[ToolSchema],
        model: Model,
        reasoning_level: api.ModelReasoningLevel,
        api_key: str | None = None,
    ):
        self.session_id = session_id
        self.backend: FluxBackend | None = None
        self.tools = tools
        self.model = model
        self.api_key = api_key
        self.initialization_lock = asyncio.Lock()
        self.reasoning_level = reasoning_level
        self.on_streaming_message: StreamingMessageHandler | None = None

    async def __call__(self, messages: list[api.AgentMessage]) -> AssistantMessage:
        if self.backend is None:
            await self._initialize()
            assert self.backend is not None

        return await self.backend.transmit(
            session_id=self.session_id,
            messages=messages,
            reasoning_level=self.reasoning_level,
        )

    async def _initialize(self):
        assert self.backend is None
        async with self.initialization_lock:
            if self.backend is not None:
                return
            self.backend = await FluxBackend.get()
            await self.backend.start_session(
                session_id=self.session_id,
                model=self.model,
                tools=self.tools,
                api_key=self.api_key,
            )

            assert self.on_streaming_message is not None
            self.backend.streaming_message_handlers[self.session_id] = self.on_streaming_message


class FluxProcess:
    def __init__(self):
        self.socket_path = get_safe_socket_path('agentron-flux')
        self.process: asyncio.subprocess.Process | None = None
        atexit.register(self.close)

    async def start(self) -> None:
        if self.process is not None and self.process.returncode is None:
            return

        logger.debug(f'Starting Flux process with socket path: {self.socket_path}')
        self.process = await asyncio.create_subprocess_exec(
            'node',
            str(get_flux_path()),
            '--ipc',
            self.socket_path,
            stdout=asyncio.subprocess.PIPE,
            # Create a new process group to ensure proper cleanup via killpg.
            start_new_session=True,
        )
        await self._wait_until_server_is_ready()

    def close(self):
        if self.process is None:
            return

        atexit.unregister(self.close)

        if self.process.returncode is not None:
            # Process already exited
            logger.debug('Flux process already exited.')
            return
        try:
            # Kill process group
            os.killpg(self.process.pid, signal.SIGTERM)
            logger.debug('Sent SIGTERM to Flux process group.')
        except Exception as e:
            logger.debug(f'Exception encountered while killing flux process group: {e}')

    async def _wait_until_server_is_ready(self):
        proc = self.process
        assert proc is not None
        proc_stdout = proc.stdout
        assert proc_stdout is not None

        while True:
            line = await proc_stdout.readline()
            if not line:
                raise RuntimeError('Flux process exited unexpectedly while waiting for READY signal.')

            if line.strip() == b'READY':
                break

        logger.debug('Received READY signal from Flux process.')


class FluxExistingProcess:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path

    async def start(self) -> None:
        logger.debug(f'Using existing Flux process with socket path: {self.socket_path}')

    async def close(self):
        pass


def get_flux_path() -> Path:
    return get_flux_root() / 'main.js'
