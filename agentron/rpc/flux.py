from __future__ import annotations

import os
import atexit
import signal
import asyncio
import logging

from agentron.types.message import AssistantMessage, StreamingMessage
from agentron.types.core import LLMBackend, ToolSchema, StreamingMessageHandler
from agentron.model import Model
from agentron.rpc.client import JsonRpcClient, JsonRpcError
from agentron.rpc.utils import get_safe_socket_path
from agentron.rpc import api
from agentron.path import get_flux_path

logger = logging.getLogger(__name__)


class BackendError(RuntimeError): ...


class FluxBackend(LLMBackend):
    def __init__(
        self,
        model: Model,
        tools: list[ToolSchema],
        api_key: api.ApiKeySource | None,
    ) -> None:
        self.model = model
        self.tools = tools
        self.api_key = api_key
        self._server: FluxRpcServer | None = None
        self._initialized_sessions = set[str]()
        self._streaming_handlers: dict[str, StreamingMessageHandler] = {}

    async def __call__(
        self,
        *,
        session_id: str,
        messages: list[api.AgentMessage],
        reasoning: api.ModelReasoningLevel | None,
        on_streaming_message: StreamingMessageHandler,
    ) -> AssistantMessage:
        if self._server is None:
            # Lazily acquire the RPC server on the first request.
            self._server = await FluxRpcServer.get()

        if session_id not in self._initialized_sessions:
            await self._initialize_session(session_id)
            self._initialized_sessions.add(session_id)

        try:
            self._streaming_handlers[session_id] = on_streaming_message
            return await self._server.rpc.request(
                method=api.RequestKind.TRANSMIT,
                params=api.TransmitRequest(
                    session_id=session_id,
                    messages=messages,
                    reasoning=reasoning,
                ),
            )
        except JsonRpcError as err:
            raise BackendError(err.message) from err
        finally:
            self._streaming_handlers.pop(session_id, None)

    async def _initialize_session(
        self,
        session_id: str,
    ) -> None:
        assert self._server is not None
        await self._server.rpc.request(
            method=api.RequestKind.SESSION_START,
            params=api.SessionStartRequest(
                session_id=session_id,
                model=self.model,
                tools=self.tools,
                api_key=self.api_key,
            ),
        )
        # TODO: Unregister the streaming message handler when the session ends
        self._server.rpc.on_notification(
            method=api.NotificationKind.STREAMING_MESSAGE,
            handler=self._dispatch_streaming_message,
        )

    def _dispatch_streaming_message(self, message: StreamingMessage) -> None:
        handler = self._streaming_handlers.get(message['session_id'])
        if handler is not None:
            handler(message)


class FluxRpcServer:
    _shared_instance: FluxRpcServer | None = None
    _instance_lock = asyncio.Lock()

    @classmethod
    async def get(cls) -> FluxRpcServer:
        """
        Returns a singleton instance of the Flux RPC server.
        The first invocation creates the instance and starts the Flux process.
        """
        if cls._shared_instance is not None:
            return cls._shared_instance

        async with cls._instance_lock:
            if cls._shared_instance is not None:
                return cls._shared_instance

            instance = FluxRpcServer()
            await instance.start()
            cls._shared_instance = instance

        return cls._shared_instance

    def __init__(self):
        self.process = FluxProcess()
        self.rpc = JsonRpcClient(
            socket_path=self.process.socket_path,
            response_timeout=None,
        )
        self.streaming_message_handlers: dict[str, StreamingMessageHandler] = {}

    async def start(self) -> None:
        await self.process.start()
        await self.rpc.connect()


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
            'rpc',
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
