from __future__ import annotations

import os
import sys

from agentron.session import AgentSession
from agentron.utils.publisher import SubscriptionStore
from agentron.messages import (
    AgentMessage,
    AssistantContent,
    AssistantContentType,
    AssistantMessage,
    ContentType,
    MessageType,
    StreamingMessage,
    StreamingMessageType,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)


class Ansi:
    RESET = '\033[0m'
    DIM = '\033[2m'
    CYAN = '\033[36m'
    BRIGHT_WHITE_BOLD = '\033[1;97m'
    GREEN = '\033[32m'
    RED = '\033[31m'


class ConsoleRenderer:
    """
    Renders session activity to a terminal stream.
    """

    def __init__(
        self,
        session: AgentSession,
        stream=sys.stdout,
        *,
        use_color: bool | None = None,
    ):
        self.session = session
        self.stream = stream
        self.use_color = self._detect_color_support() if use_color is None else use_color
        self.subscriptions = SubscriptionStore()

        # Assistant messages that were already printed from streaming updates.
        self._streamed_assistant_ids: set[str] = set()
        # Tool calls already printed (from assistant content or callback).
        self._printed_tool_call_ids: set[str] = set()

        # Track the active streamed content segment to keep output readable.
        self._active_stream_segment: tuple[str, int] | None = None
        self._active_stream_line_open = False

        self._render_existing_messages()
        self._subscribe()

    def close(self) -> None:
        """Unsubscribe from session events."""
        self.subscriptions.clear()

    def _subscribe(self) -> None:
        self.subscriptions.add(
            self.session.on_new_message.subscribe(self._on_new_message),
            self.session.on_streaming_message.subscribe(self._on_streaming_message),
            self.session.on_tool_call.subscribe(self._on_tool_call),
        )

    def _render_existing_messages(self) -> None:
        for message in self.session.messages:
            match message['mtype']:
                case MessageType.USER:
                    self._print_user_message(message)
                case MessageType.SYSTEM:
                    self._print_system_message(message)

    def _on_new_message(self, message: AgentMessage) -> None:
        match message['mtype']:
            case MessageType.USER:
                self._print_user_message(message)

            case MessageType.SYSTEM:
                self._print_system_message(message)

            case MessageType.ASSISTANT:
                if message['id'] not in self._streamed_assistant_ids:
                    self._render_assistant_message(message)
            case MessageType.TOOL_RESULT:
                self._render_tool_result_message(message)

    def _print_user_message(self, message: UserMessage) -> None:
        self._print_prefixed('User: ', message['content']['text'])

    def _print_system_message(self, message: SystemMessage) -> None:
        self._print_prefixed('System: ', message['content']['text'])

    def _on_streaming_message(self, message: StreamingMessage) -> None:
        partial = message['partial']
        message_id = partial['id']
        self._streamed_assistant_ids.add(message_id)

        stream_type = message['type']
        segment = (message_id, message['content_index'])
        delta = message.get('delta', '')

        match stream_type:
            case StreamingMessageType.TEXT_START | StreamingMessageType.TEXT_DELTA:
                self._activate_stream_segment(segment)
                self._print_inline(delta)
            case StreamingMessageType.REASONING_START | StreamingMessageType.REASONING_DELTA:
                self._activate_stream_segment(segment)
                self._print_inline(self._dim(delta))
            case StreamingMessageType.TEXT_END:
                self._activate_stream_segment(segment)
                self._print_inline(delta)
                self._finish_stream_segment()
            case StreamingMessageType.REASONING_END:
                self._activate_stream_segment(segment)
                self._print_inline(self._dim(delta))
                self._finish_stream_segment()

    def _on_tool_call(self, tool_call: ToolCall) -> None:
        self._render_tool_call(tool_call)

    def _render_assistant_message(self, message: AssistantMessage) -> None:
        for content in message['content']:
            self._render_assistant_content(content)

    def _render_assistant_content(self, content: AssistantContent) -> None:
        match content['type']:
            case ContentType.TEXT:
                self._print(content['text'])
            case AssistantContentType.REASONING:
                self._print(self._dim(content['text']))
            case AssistantContentType.TOOL_CALL:
                self._render_tool_call(content)

    def _render_tool_call(self, tool_call: ToolCall) -> None:
        call_id = tool_call['id']
        if call_id in self._printed_tool_call_ids:
            return

        self._printed_tool_call_ids.add(call_id)

        prefix = self._colorize('Tool Call:', Ansi.CYAN)
        name = self._colorize(tool_call['name'], Ansi.BRIGHT_WHITE_BOLD)
        self._print(f'{prefix} {name}')

    def _render_tool_result_message(self, message: ToolResultMessage) -> None:
        tool_name = message['tool_name']
        success = message['result']['success']

        if success:
            status = self._colorize('Success', Ansi.GREEN)
            self._print(f'  {tool_name}: {status}')
            return

        status = self._colorize('Error', Ansi.RED)
        error_text = message['result'].get('error')
        if error_text:
            self._print(f'  {tool_name}: {status} ({error_text})')
            return

        self._print(f'  {tool_name}: {status}')

    def _activate_stream_segment(self, segment: tuple[str, int]) -> None:
        if self._active_stream_segment == segment:
            return

        if self._active_stream_line_open:
            self._print('')

        self._active_stream_segment = segment

    def _finish_stream_segment(self) -> None:
        if self._active_stream_line_open:
            self._print('')
        self._active_stream_line_open = False
        self._active_stream_segment = None

    def _print_inline(self, text: str) -> None:
        if not text:
            return

        self.stream.write(text)
        self.stream.flush()
        self._active_stream_line_open = not text.endswith('\n')

    def _print_prefixed(self, prefix: str, text: str) -> None:
        print(self._colorize(prefix, Ansi.CYAN), end='')
        self._print(text)

    def _print(self, text: str) -> None:
        self.stream.write(text)
        self.stream.write('\n\n')
        self.stream.flush()
        self._active_stream_line_open = False

    def _dim(self, text: str) -> str:
        return self._colorize(text, Ansi.DIM)

    def _colorize(self, text: str, ansi_code: str) -> str:
        if not self.use_color or not text:
            return text
        return f'{ansi_code}{text}{Ansi.RESET}'

    def _detect_color_support(self) -> bool:
        if os.getenv('NO_COLOR') is not None:
            return False

        force_color = os.getenv('CLICOLOR_FORCE')
        if force_color and force_color != '0':
            return True

        if not hasattr(self.stream, 'isatty') or not self.stream.isatty():
            return False

        term = os.getenv('TERM', '')
        if term.lower() == 'dumb':
            return False

        return True
