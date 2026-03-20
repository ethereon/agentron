from __future__ import annotations

import json

from typing import TYPE_CHECKING, Iterable
from pathlib import Path

if TYPE_CHECKING:
    from agentron.agent import Agent
    from agentron.messages import AgentMessage
    from agentron.utils.publisher import Subscription


class MessageWriter:
    def __init__(self, path: Path):
        self.path = path
        self._file = path.open('a', encoding='utf-8')
        self._closed = False
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

    def write_message(self, message: AgentMessage) -> None:
        if self._closed:
            return

        self._file.write(json.dumps(message, separators=(',', ':')))
        self._file.write('\n')
        self._file.flush()

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


def write_messages(messages: Iterable[AgentMessage], path: Path) -> None:
    with MessageWriter(path) as writer:
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

    try:
        new_message_subscription = agent.on_new_message.subscribe(write_message)
        finalize_subscription = agent.on_finalize.subscribe(on_finalize)

        for message in list(agent.messages):
            write_message(message)
    except Exception:
        close()
        raise

    return close
