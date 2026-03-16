from __future__ import annotations

import asyncio
import json
import logging

from collections.abc import Callable, Coroutine
from typing import Any

logger = logging.getLogger(__name__)

type NotificationHandler = Callable[..., None | Coroutine[Any, Any, None]]


class JsonRpcError(Exception):
    """Raised when the server returns a JSON-RPC error object."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f'[{code}] {message}')
        self.code = code
        self.message = message
        self.data = data


class JsonRpcClient:
    """
    Async JSON-RPC 2.0 client that communicates over a Unix domain socket.

    Usage::

        async with JsonRpcClient("/run/my-service.sock") as client:
            client.on_notification("update", handle_update)
            result = await client.request("add", {"a": 1, "b": 2})

    The client reads from the socket in a background task.  Each line is
    expected to be a complete, newline-delimited JSON object (NDJSON framing).
    """

    def __init__(
        self,
        socket_path: str,
        *,
        encoding: str = 'utf-8',
        response_timeout: float = 600,  # 10 minutes
    ) -> None:
        self._socket_path = socket_path
        self._encoding = encoding
        self._response_timeout = response_timeout

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._next_id: int = 1
        # Pending requests: id -> Future that will receive the result/error
        self._pending: dict[int | str, asyncio.Future[Any]] = {}
        # Notification handlers keyed by method name; None key = catch-all
        self._notification_handlers: dict[str | None, list[NotificationHandler]] = {}
        self._reader_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Context-manager helpers
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the Unix socket connection and start the background reader."""
        self._reader, self._writer = await asyncio.open_unix_connection(self._socket_path)
        self._reader_task = asyncio.create_task(self._read_loop(), name='jsonrpc-reader')
        logger.debug('Connected to %s', self._socket_path)

    async def close(self) -> None:
        """Shut down the connection and cancel the background reader."""
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None

        # Fail any still-pending requests
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(ConnectionError('Client closed'))
        self._pending.clear()
        logger.debug('Disconnected from %s', self._socket_path)

    async def __aenter__(self) -> JsonRpcClient:
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def request(self, method: str, params: Any = None) -> Any:
        """
        Send a JSON-RPC request and wait for the response.

        Args:
            method: The remote method name.
            params: Positional (list) or named (dict) parameters, or None.

        Returns:
            The `result` field from the server response.

        Raises:
            JsonRpcError: If the server returns an error object.
            asyncio.TimeoutError: If no response arrives within *response_timeout*.
        """
        rpc_id = self._next_id
        self._next_id += 1

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        self._pending[rpc_id] = fut

        await self._send(
            {
                'jsonrpc': '2.0',
                'id': rpc_id,
                'method': method,
                **({'params': params} if params is not None else {}),
            }
        )

        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=self._response_timeout)
        except (asyncio.TimeoutError, Exception):
            self._pending.pop(rpc_id, None)
            raise

    async def notify(self, method: str, params: Any = None) -> None:
        """
        Send a JSON-RPC notification (no id, no response expected).

        Args:
            method: The remote method name.
            params: Positional (list) or named (dict) parameters, or None.
        """
        await self._send(
            {
                'jsonrpc': '2.0',
                'method': method,
                **({'params': params} if params is not None else {}),
            }
        )

    def on_notification(
        self,
        method: str | None,
        handler: NotificationHandler,
    ) -> None:
        """
        Register a handler for incoming server notifications.

        Args:
            method: The notification method to listen for.  Pass ``None`` to
                    register a catch-all that receives every notification not
                    matched by a specific handler.
            handler: A callable (sync or async) that accepts ``(method, params)``.
        """
        self._notification_handlers.setdefault(method, []).append(handler)

    def remove_notification_handler(
        self,
        method: str | None,
        handler: NotificationHandler,
    ) -> None:
        """Unregister a previously registered notification handler."""
        handlers = self._notification_handlers.get(method, [])
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send(self, payload: dict[str, Any]) -> None:
        if self._writer is None:
            raise ConnectionError('Not connected')
        line = json.dumps(payload, separators=(',', ':')) + '\n'
        self._writer.write(line.encode(self._encoding))
        await self._writer.drain()

    async def _read_loop(self) -> None:
        """Background task: read newline-delimited JSON from the socket."""
        assert self._reader is not None
        try:
            while True:
                raw = await self._reader.readline()
                if not raw:
                    logger.debug('Server closed the connection')
                    break
                await self._handle_raw(raw)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error('Read loop error: %s', exc, exc_info=True)
        finally:
            # Fail all pending requests if the read loop exits unexpectedly
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError('Read loop terminated'))
            self._pending.clear()

    async def _handle_raw(self, raw: bytes) -> None:
        try:
            msg = json.loads(raw.decode(self._encoding))
        except json.JSONDecodeError as exc:
            logger.warning('Received invalid JSON: %s', exc)
            return

        if not isinstance(msg, dict):
            logger.warning('Expected a JSON object, got: %r', msg)
            return

        if 'id' in msg and msg['id'] is not None:
            # Response to one of our requests
            await self._handle_response(msg)
        else:
            # Notification (no id or null id, no result/error)
            await self._handle_notification(msg)

    async def _handle_response(self, msg: dict[str, Any]) -> None:
        rpc_id = msg['id']
        fut = self._pending.pop(rpc_id, None)
        if fut is None:
            logger.warning('Received response for unknown id %r', rpc_id)
            return
        if fut.done():
            return

        if 'error' in msg:
            err = msg['error']
            fut.set_exception(
                JsonRpcError(
                    code=err.get('code', -32603),
                    message=err.get('message', 'Unknown error'),
                    data=err.get('data'),
                )
            )
        else:
            fut.set_result(msg.get('result'))

    async def _handle_notification(self, msg: dict[str, Any]) -> None:
        method: str = msg.get('method', '')
        params: Any = msg.get('params')

        # Collect specific + catch-all handlers
        handlers = [
            *self._notification_handlers.get(method, []),
            *self._notification_handlers.get(None, []),
        ]

        if not handlers:
            logger.debug('No handler for notification %r', method)
            return

        for handler in handlers:
            try:
                result = handler(*params)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.error('Notification handler for %r raised: %s', method, exc, exc_info=True)
