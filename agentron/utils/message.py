import uuid
import time

from typing import Any
from agentron.types.core import ContentLike, PILImage
from agentron.path import resolve_external_caller_path
from agentron.types.message import (
    AssistantMessage,
    Content,
    SystemMessage,
    TextContent,
    ToolCall,
    ToolResult,
    ToolResultMessage,
    UserMessage,
)

FILE_SPECIFIER_PREFIX = 'file:'


def as_content(content: ContentLike) -> Content:
    if isinstance(content, dict):
        return content
    elif isinstance(content, str):
        return TextContent(
            type='text',
            text=content,
        )
    elif PILImage is not Any and isinstance(content, PILImage):
        raise NotImplementedError('Image content is not yet supported')
    else:
        raise ValueError(f'Unsupported content type: {type(content)}')


def current_timestamp() -> int:
    return int(time.time() * 1000)


def new_message_id() -> str:
    return uuid.uuid4().hex


def make_user_message(content: ContentLike) -> UserMessage:
    return UserMessage(
        mtype='user',
        id=new_message_id(),
        timestamp=current_timestamp(),
        content=as_content(content),
    )


def make_system_message(text: str) -> SystemMessage:
    return SystemMessage(
        mtype='system',
        id=new_message_id(),
        timestamp=current_timestamp(),
        content=as_content(resolve_text(text)),
    )


def resolve_text(text: str) -> str:
    if text.startswith(FILE_SPECIFIER_PREFIX):
        # Get the path of the file relative to the invoking module
        # (that's outside of the agentron package, e.g. in the user's codebase)
        parent_dir = resolve_external_caller_path()
        file_path = parent_dir / text.removeprefix(FILE_SPECIFIER_PREFIX).strip()
        return file_path.read_text()
    return text


def extract_tool_calls(response: AssistantMessage) -> list[ToolCall]:
    tool_calls: list[ToolCall] = []

    for content in response['content']:
        if content['type'] == 'tool_call':
            tool_calls.append(content)

    return tool_calls


def extract_assistant_text(response: AssistantMessage) -> str | None:
    for content in response['content']:
        if content['type'] == 'text':
            return content['text']
    # No text content found (e.g. if the assistant only returned tool calls)
    return None


def as_tool_result_message(tool_result: ToolResult, tool_call: ToolCall) -> ToolResultMessage:
    return ToolResultMessage(
        id=new_message_id(),
        timestamp=current_timestamp(),
        mtype='tool_result',
        call_id=tool_call['id'],
        tool_name=tool_call['name'],
        result=tool_result,
    )
