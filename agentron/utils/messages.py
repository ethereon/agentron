from typing import Any

import uuid
import time

from agentron.typing import ContentLike, PILImage
from agentron.messages import (
    AssistantContentType,
    AssistantMessage,
    Content,
    ContentType,
    MessageType,
    SystemMessage,
    TextContent,
    ToolCall,
    ToolResult,
    ToolResultMessage,
    UserMessage,
)


def as_content(content: ContentLike) -> Content:
    if isinstance(content, dict):
        return content
    elif isinstance(content, str):
        return TextContent(
            type=ContentType.TEXT,
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
        mtype=MessageType.USER,
        id=new_message_id(),
        timestamp=current_timestamp(),
        content=as_content(content),
    )


def make_system_message(text: str) -> SystemMessage:
    return SystemMessage(
        mtype=MessageType.SYSTEM,
        id=new_message_id(),
        timestamp=current_timestamp(),
        content=as_content(text),
    )


def extract_tool_calls(response: AssistantMessage) -> list[ToolCall]:
    tool_calls: list[ToolCall] = []

    for content in response['content']:
        if content['type'] == AssistantContentType.TOOL_CALL:
            tool_calls.append(content)

    return tool_calls


def as_tool_result_message(tool_result: ToolResult, tool_call: ToolCall) -> ToolResultMessage:
    return ToolResultMessage(
        id=new_message_id(),
        timestamp=current_timestamp(),
        mtype=MessageType.TOOL_RESULT,
        call_id=tool_call['id'],
        tool_name=tool_call['name'],
        result=tool_result,
    )
