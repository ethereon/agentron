from __future__ import annotations

import json
import mimetypes
import queue
import threading
import webbrowser
import logging

from pathlib import Path
from typing import Any, Protocol, Iterable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
from contextlib import contextmanager

from agentron.agent import Agent
from agentron.types.session import SessionMetadata
from agentron.types.message import AgentMessage
from agentron.web.responses import SessionsResponse, MessagesResponse
from agentron.utils.publisher import SubscriptionStore
from agentron.path import get_webui_root

log = logging.getLogger(__name__)

_SENTINEL = object()  # Placed in a client queue to signal disconnection


class SessionSource(Protocol):
    @property
    def messages(self) -> list[AgentMessage]: ...

    @property
    def session_id(self) -> str: ...

    @property
    def metadata(self) -> SessionMetadata: ...

    def resolve_subagent(self, session_id: str) -> SessionSource | None: ...


class WebServer:
    """
    An HTTP server that publishes agent session activity over SSE.

    Endpoints:
        GET /api/sessions
        Metadata for all top-level registered session sources.

        GET /api/session-meta?session_id=<id>
        Metadata for the given session ID.
        A fully-scoped session ID may be provided to resolve subagent sessions,
        which are not included in the top-level sessions list.

        GET /api/messages?session_id=<id>
        Completed messages for the given session.

        GET /api/events?session_id=<id>
        SSE stream for the given session.

        GET /<path>
        Serve a static file from the static directory.

        GET /
        Serve index.html from the static directory.

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
        # Maps session_id -> SessionSource (for history endpoints)
        self._sessions: dict[str, SessionSource] = {}
        # Maps session_id -> SubscriptionStore (holds Publisher unsubscribers)
        self._subscriptions: dict[str, SubscriptionStore] = {}
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def register_agent(self, agent: Agent) -> None:
        """Subscribe to all events from *agent* and expose it to SSE clients."""
        session_id = agent.session_id
        with self._lock:
            if session_id in self._subscriptions:
                return
            # Subscriptions are established while holding the lock so that no
            # broadcast can race against the client-bucket initialization below.
            store = SubscriptionStore(
                agent.on_new_message.subscribe(lambda msg: self._broadcast(session_id, 'new_message', msg)),
                agent.on_streaming_message.subscribe(lambda msg: self._broadcast(session_id, 'streaming_message', msg)),
            )
            self._subscriptions[session_id] = store
            self._add_session_source(agent)

    def unregister_agent(self, agent: Agent) -> None:
        """Unsubscribe from *agent* and terminate any active SSE connections for it."""
        session_id = agent.session_id
        with self._lock:
            store = self._subscriptions.pop(session_id, None)
            self._sessions.pop(session_id, None)
            clients = self._clients.pop(session_id, [])

        if store:
            store.clear()
        for q in clients:
            q.put(_SENTINEL)

    def add_session_sources(self, sources: Iterable[SessionSource]) -> None:
        non_agent_sources: list[SessionSource] = []
        for source in sources:
            if isinstance(source, Agent):
                self.register_agent(source)
            else:
                non_agent_sources.append(source)

        with self._lock:
            for source in non_agent_sources:
                self._add_session_source(source)

    def start(self, *, open_browser: bool = False) -> None:
        """Start the HTTP server on a daemon background thread."""
        self._server = ThreadingHTTPServer((self.host, self.port), _make_handler(self))
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name='agentron-web-server',
        )
        self._thread.start()

        url = f'http://{self.host}:{self.port}'
        if open_browser:
            webbrowser.open(url)

        print(f'Web UI available at {url}')

    def join(self) -> None:
        """Block until the server thread exits."""
        if self._thread:
            try:
                self._thread.join()
            except KeyboardInterrupt:
                self.stop()

    def stop(self) -> None:
        """Shut down the server and block until the background thread exits."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join()
            self._thread = None

    def _add_session_source(self, source: SessionSource) -> None:
        session_id = source.session_id
        if session_id in self._sessions:
            raise ValueError(f'Session with ID {session_id} is already registered.')
        self._sessions[session_id] = source
        self._clients[session_id] = []

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

    def _get_source(self, session_id: str) -> SessionSource | None:
        """
        Resolve the source for the given session ID.

        The session ID may either directly match a registered source,
        or it may be a scoped ID representing a subagent session
        (e.g. "root:child", or "root:child:grandchild").
        Subagent sources are typically lazily resolved and must be initially
        requested using their full scoped ID.
        """

        with self._lock:
            parts = session_id.split(':')
            primary_id = parts[-1]
            src = self._sessions.get(primary_id)
            if src is not None:
                # Session ID directly matches a known source.
                return src

            if len(parts) == 1:
                # No further resolution possible.
                return None

            root_src = self._sessions.get(parts[0])
            if root_src is None:
                # Failed to resolve the root session
                return None

            # Attempt to resolve the session ID by traversing the parent hierarchy.
            # This allows for lazy subagent session resolution.
            cur_src = root_src
            for cur_id in parts[1:]:
                cur_src = cur_src.resolve_subagent(cur_id)
                if cur_src is None:
                    break

            return cur_src

    def _get_all_source_metadata(self) -> dict[str, SessionMetadata]:
        with self._lock:
            return {session_id: src.metadata for session_id, src in self._sessions.items()}

    def _resolve_session_metadata(self, session_id: str) -> SessionMetadata | None:
        with self._lock:
            # Check if the primary session ID is already resolved.
            primary_id, *parents = session_id.split(':')
            src = self._sessions.get(primary_id)
            if src is not None:
                # Previously resolved
                return src.metadata

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
                case '/api/session-meta':
                    self._handle_session_meta(parsed)
                case _:
                    self._handle_static(parsed.path)

        def _write_json(self, content):
            body = json.dumps(content).encode()
            self._send_response_headers(
                200,
                {
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(body)),
                },
            )
            self.wfile.write(body)

        def _handle_sessions(self) -> None:
            sessions: SessionsResponse = server._get_all_source_metadata()
            self._write_json(sessions)

        def _handle_session_meta(self, parsed) -> None:
            source = self._require_source(parsed)
            if source is not None:
                self._write_json(source.metadata)

        def _require_session_id(self, parsed) -> str | None:
            params = parse_qs(parsed.query)
            ids = params.get('session_id')
            if not ids:
                self.send_error(400, 'Missing session_id parameter')
                return None
            return ids[0]

        def _require_source(self, parsed) -> SessionSource | None:
            session_id = self._require_session_id(parsed)
            if session_id is None:
                return None
            source = server._get_source(session_id)
            if source is None:
                self.send_error(404, f'Unknown session: {session_id}')
                return None
            return source

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
            source = self._require_source(parsed)
            if source is None:
                return
            messages: MessagesResponse = source.messages
            self._write_json(messages)

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


@contextmanager
def serve(*sources: SessionSource):
    """Context manager that starts a WebServer and registers the given sources."""
    server = WebServer()
    server.add_session_sources(sources)
    server.start(open_browser=True)

    yield server

    print('Press Ctrl+C to stop the server and exit.')
    server.join()
