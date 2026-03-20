from __future__ import annotations

import json
import time

from typing import TYPE_CHECKING, Iterable, TypedDict, Literal
from pathlib import Path
from dataclasses import dataclass

if TYPE_CHECKING:
    from agentron.agent import Agent
    from agentron.messages import AgentMessage
    from agentron.utils.publisher import Subscription

_CURRENT_SERIALIZATION_VERSION = 1


class SessionHeader(TypedDict):
    type: Literal['header']
    version: int
    session_id: str
    created: int
    metadata: dict


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

    def maybe_write_header(self, *, session_id: str, metadata: dict) -> None:
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
    metadata: dict | None = None,
) -> None:
    with MessageWriter(path) as writer:
        if session_id is not None:
            writer.maybe_write_header(
                session_id=session_id,
                metadata=metadata if metadata is not None else {},
            )
        writer.write_messages(messages)


def _resolve_auto_write_path(agent: Agent, path: Path) -> Path:
    if path.is_dir():
        return path / f'{agent.session_id}.jsonl'
    return path


def auto_write_messages(agent: Agent, path: Path) -> Subscription:
    """
    Automatically write existing and future messages for the given agent to
    the specified path. If the path is a directory, a file named after the
    agent's session ID will be created inside it.
    """
    writer = MessageWriter(_resolve_auto_write_path(agent, path))
    write_message = writer.write_message
    new_message_subscription: Subscription | None = None
    finalize_subscription: Subscription | None = None

    def close(*, unsubscribe_finalize: bool = True) -> None:
        nonlocal new_message_subscription, finalize_subscription

        if new_message_subscription is not None:
            new_message_subscription()
            new_message_subscription = None

        if unsubscribe_finalize and finalize_subscription is not None:
            finalize_subscription()
            finalize_subscription = None

        writer.close()

    def on_finalize(_: None) -> None:
        close(unsubscribe_finalize=False)

    if agent.is_finalized:
        close()
        return lambda: None

    try:
        new_message_subscription = agent.on_new_message.subscribe(write_message)
        finalize_subscription = agent.on_finalize.subscribe(on_finalize)
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


def read_session_data(path: Path) -> SessionData:
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

        messages = []
        for line in file:
            if line.strip():
                try:
                    message_data = json.loads(line)
                    messages.append(message_data)
                except json.JSONDecodeError as e:
                    raise ValueError('Failed to parse message line as JSON.') from e

    return SessionData(header=header, messages=messages)
