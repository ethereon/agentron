from __future__ import annotations

import json
import mimetypes
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from agentron.session import AgentSession
from agentron.utils.publisher import SubscriptionStore
from agentron.path import get_webui_root

_SENTINEL = object()  # Placed in a client queue to signal disconnection


class WebServer:
    """
    An HTTP server that publishes agent session activity over SSE.

    Endpoints:
        GET /api/sessions                   JSON list of registered session IDs.
        GET /api/messages?session_id=<id>   JSON list of existing messages for the session.
        GET /api/events?session_id=<id>     SSE stream for the given session.
        GET /                               Serve index.html from the static directory.
        GET /<path>                         Serve a static file from the static directory.

    SSE event types:
        new_message         AgentMessage (user/system/assistant/tool_result)
        streaming_message   StreamingMessage (incremental assistant text/reasoning)
    """

    def __init__(self, host: str = 'localhost', port: int = 8765):
        self.host = host
        self.port = port
        self.static_dir = get_webui_root()
        self._lock = threading.Lock()
        # Maps session_id -> list of per-client queues
        self._clients: dict[str, list[queue.Queue]] = {}
        # Maps session_id -> AgentSession (for history endpoints)
        self._sessions: dict[str, AgentSession] = {}
        # Maps session_id -> SubscriptionStore (holds Publisher unsubscribers)
        self._subscriptions: dict[str, SubscriptionStore] = {}
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def register_session(self, session: AgentSession) -> None:
        """Subscribe to all events from *session* and expose it to SSE clients."""
        session_id = session.id
        with self._lock:
            if session_id in self._subscriptions:
                return
            # Subscriptions are established while holding the lock so that no
            # broadcast can race against the client-bucket initialization below.
            store = SubscriptionStore(
                session.on_new_message.subscribe(lambda msg: self._broadcast(session_id, 'new_message', msg)),
                session.on_streaming_message.subscribe(lambda msg: self._broadcast(session_id, 'streaming_message', msg)),
            )
            self._sessions[session_id] = session
            self._subscriptions[session_id] = store
            self._clients[session_id] = []

    def unregister_session(self, session: AgentSession) -> None:
        """Unsubscribe from *session* and terminate any active SSE connections for it."""
        session_id = session.id
        with self._lock:
            store = self._subscriptions.pop(session_id, None)
            self._sessions.pop(session_id, None)
            clients = self._clients.pop(session_id, [])

        if store:
            store.clear()
        for q in clients:
            q.put(_SENTINEL)

    def start(self) -> None:
        """Start the HTTP server on a daemon background thread."""
        self._server = ThreadingHTTPServer((self.host, self.port), _make_handler(self))
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name='agentron-web-server',
        )
        self._thread.start()
        print(f'Web UI available at http://{self.host}:{self.port}')

    def join(self) -> None:
        """Block until the server thread exits."""
        if self._thread:
            self._thread.join()

    def stop(self) -> None:
        """Shut down the server and block until the background thread exits."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join()
            self._thread = None

    def _broadcast(self, session_id: str, event: str, data: Any) -> None:
        """Serialize *data* and enqueue the event for all SSE clients of *session_id*."""
        payload = json.dumps(data)
        with self._lock:
            clients = list(self._clients.get(session_id, []))
        for q in clients:
            q.put((event, payload))

    def _add_client(self, session_id: str, q: queue.Queue) -> bool:
        """Register *q* as a client for *session_id*. Returns False if the session is unknown."""
        with self._lock:
            bucket = self._clients.get(session_id)
            if bucket is None:
                return False
            bucket.append(q)
            return True

    def _remove_client(self, session_id: str, q: queue.Queue) -> None:
        with self._lock:
            bucket = self._clients.get(session_id)
            if bucket is not None:
                try:
                    bucket.remove(q)
                except ValueError:
                    pass

    def _session_ids(self) -> list[str]:
        with self._lock:
            return list(self._clients)

    def _get_session(self, session_id: str) -> AgentSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def _resolve_static_path(self, request_path: str) -> Path | None:
        relative_path = Path(unquote(request_path.lstrip('/')))
        if request_path == '/':
            relative_path /= 'index.html'

        try:
            candidate = (self.static_dir / relative_path).resolve(strict=True)
            candidate.relative_to(self.static_dir)
        except (FileNotFoundError, ValueError):
            return None

        if not candidate.is_file():
            return None

        return candidate


def _make_handler(server: WebServer):
    """Return a BaseHTTPRequestHandler subclass bound to *server*."""

    class _Handler(BaseHTTPRequestHandler):
        def handle(self):
            try:
                super().handle()
            except (ConnectionResetError, BrokenPipeError):
                pass

        def log_message(self, format: str, *args: Any) -> None:
            pass  # Suppress default per-request logging

        def _send_response_headers(self, status_code: int, headers: dict[str, str]) -> None:
            self.send_response(status_code)
            for header, value in headers.items():
                self.send_header(header, value)
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            match parsed.path:
                case '/api/events':
                    self._handle_sse(parsed)
                case '/api/messages':
                    self._handle_messages(parsed)
                case '/api/sessions':
                    self._handle_sessions()
                case _:
                    self._handle_static(parsed.path)

        def _handle_sessions(self) -> None:
            body = json.dumps(server._session_ids()).encode()
            self._send_response_headers(
                200,
                {
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(body)),
                },
            )
            self.wfile.write(body)

        def _require_session_id(self, parsed) -> str | None:
            params = parse_qs(parsed.query)
            ids = params.get('session_id')
            if not ids:
                self.send_error(400, 'Missing session_id parameter')
                return None
            return ids[0]

        def _require_session(self, parsed) -> AgentSession | None:
            session_id = self._require_session_id(parsed)
            if session_id is None:
                return None
            session = server._get_session(session_id)
            if session is None:
                self.send_error(404, f'Unknown session: {session_id}')
                return None
            return session

        def _handle_sse(self, parsed) -> None:
            session_id = self._require_session_id(parsed)
            if session_id is None:
                return
            q: queue.Queue = queue.Queue()

            if not server._add_client(session_id, q):
                self.send_error(404, f'Unknown session: {session_id}')
                return

            self._send_response_headers(
                200,
                {
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                },
            )

            try:
                while True:
                    try:
                        item = q.get(timeout=15)
                    except queue.Empty:
                        # Keepalive comment to prevent proxy/browser timeouts
                        self.wfile.write(b': keepalive\n\n')
                        self.wfile.flush()
                        continue

                    if item is _SENTINEL:
                        break

                    event, data = item
                    self.wfile.write(f'event: {event}\ndata: {data}\n\n'.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                server._remove_client(session_id, q)

        def _handle_messages(self, parsed) -> None:
            session_id = self._require_session_id(parsed)
            if session_id is None:
                return
            session = server._get_session(session_id)
            if session is None:
                return

            body = json.dumps(session.messages).encode()
            self._send_response_headers(
                200,
                {
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(body)),
                },
            )
            self.wfile.write(body)

        def _handle_static(self, request_path: str) -> None:
            file_path = server._resolve_static_path(request_path)
            if file_path is None:
                self.send_error(404)
                return

            body = file_path.read_bytes()
            content_type, content_encoding = mimetypes.guess_type(str(file_path))

            headers = {
                'Content-Type': content_type or 'application/octet-stream',
                'Content-Length': str(len(body)),
            }
            if content_encoding:
                headers['Content-Encoding'] = content_encoding
            self._send_response_headers(200, headers)
            self.wfile.write(body)

    return _Handler
