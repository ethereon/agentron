from __future__ import annotations

import json
import time

from typing import TYPE_CHECKING, Iterable, TypedDict, Literal, Callable
from pathlib import Path
from dataclasses import dataclass

from agentron.types.session import SessionMetadata
from agentron.utils.publisher import SubscriptionStore

if TYPE_CHECKING:
    from agentron.agent import Agent
    from agentron.types.message import AgentMessage

_CURRENT_SERIALIZATION_VERSION = 1


class SessionHeader(TypedDict):
    type: Literal['header']
    version: int
    session_id: str
    created: int
    metadata: SessionMetadata


@dataclass
class SessionData:
    header: SessionHeader
    messages: list[AgentMessage]


class MessageWriter:
    def __init__(self, path: Path):
        self.path = path
        self._file = path.open('a', encoding='utf-8')
        self._closed = False
        self._target_was_empty = self.path.stat().st_size == 0
        self._ensure_trailing_newline()

    def _ensure_trailing_newline(self) -> None:
        with open(self.path, 'rb') as existing_file:
            existing_file.seek(0, 2)
            if existing_file.tell() == 0:
                return

            existing_file.seek(-1, 2)
            if existing_file.read(1) == b'\n':
                return

        self._file.write('\n')
        self._file.flush()

    def maybe_write_header(self, *, session_id: str, metadata: SessionMetadata) -> None:
        if not self._target_was_empty:
            return
        header = SessionHeader(
            type='header',
            version=_CURRENT_SERIALIZATION_VERSION,
            session_id=session_id,
            created=int(time.time() * 1000),
            metadata=metadata,
        )
        self._write_line(header)

    def write_message(self, message: AgentMessage) -> None:
        if self._closed:
            return
        self._write_line(message)

    def write_messages(self, messages: Iterable[AgentMessage]) -> None:
        for message in messages:
            self.write_message(message)

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True
        self._file.close()

    def __enter__(self) -> MessageWriter:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _write_line(self, data) -> None:
        self._file.write(json.dumps(data, separators=(',', ':')))
        self._file.write('\n')
        self._file.flush()


def write_messages(
    messages: Iterable[AgentMessage],
    path: Path,
    *,
    session_id: str | None = None,
    metadata: SessionMetadata | None = None,
) -> None:
    with MessageWriter(path) as writer:
        if session_id is not None:
            writer.maybe_write_header(
                session_id=session_id,
                metadata=metadata if metadata is not None else {},
            )
        writer.write_messages(messages)


def auto_write_messages(agent: Agent, path: Path) -> Callable[[], None]:
    """
    Automatically write existing and future messages for the given agent
    under the specified path.

    Returns a function that can be called to stop the automatic writing.

    - The path is expected to be an existing directory.
    - A sub-directory with the agent's session ID will be created if it doesn't already exist.
    - Persistence for sub-agents will be automatically handled and scoped to the parent agent's session.
    """
    if not path.exists():
        raise ValueError(f'Path {path} does not exist.')
    if not path.is_dir():
        raise ValueError(f'Path {path} is not a directory.')

    if agent.is_finalized:
        # Early exit for already finalized agents.
        return lambda: None

    session_dir = path / agent.session_id
    session_dir.mkdir(exist_ok=True)

    writer = MessageWriter(session_dir / 'session.jsonl')
    write_message = writer.write_message
    subs = SubscriptionStore()

    def close() -> None:
        subs.clear()
        writer.close()

    def on_finalize(_: None) -> None:
        close()

    def on_sub_agent_created(sub_agent: Agent) -> None:
        auto_write_messages(sub_agent, session_dir)

    try:
        subs.add(
            agent.on_new_message.subscribe(write_message),
            agent.on_finalize.subscribe(on_finalize),
            agent.on_sub_agent_created.subscribe(on_sub_agent_created),
        )
        writer.maybe_write_header(
            session_id=agent.session_id,
            metadata=agent.metadata,
        )
        for message in list(agent.messages):
            write_message(message)
    except Exception:
        close()
        raise

    return close


def read_session_data(path: Path, *, header_only=False) -> SessionData:
    with path.open('r', encoding='utf-8') as file:
        header_line = file.readline()
        if not header_line:
            raise ValueError('Session file is empty.')

        try:
            header_data = json.loads(header_line)
        except json.JSONDecodeError as e:
            raise ValueError('Failed to parse session header as JSON.') from e

        if not isinstance(header_data, dict) or header_data.get('type') != 'header':
            raise ValueError('First line of session file must be a header object.')

        try:
            header = SessionHeader(**header_data)
        except TypeError as e:
            raise ValueError('Session header is missing required fields.') from e

        if header_only:
            return SessionData(header=header, messages=[])

        messages = []
        for line in file:
            if line.strip():
                try:
                    message_data = json.loads(line)
                    messages.append(message_data)
                except json.JSONDecodeError as e:
                    raise ValueError('Failed to parse message line as JSON.') from e

    return SessionData(header=header, messages=messages)
