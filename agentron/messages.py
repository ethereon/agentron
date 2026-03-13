from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, NotRequired, TypedDict


class MessageType(StrEnum):
    SYSTEM = 'system'
    USER = 'user'
    ASSISTANT = 'assistant'
    TOOL_RESULT = 'tool_result'


class BaseMessage(TypedDict):
    id: str
    timestamp: int


class ContentType(StrEnum):
    TEXT = 'text'


class TextContent(TypedDict):
    type: Literal[ContentType.TEXT]
    text: str
    text_signature: NotRequired[str]


type Content = TextContent


class AssistantContentType(StrEnum):
    REASONING = 'reasoning'
    TOOL_CALL = 'tool_call'


class Reasoning(TypedDict):
    type: Literal[AssistantContentType.REASONING]
    text: str
    signature: NotRequired[str]
    redacted: NotRequired[bool]


class ToolCall(TypedDict):
    type: Literal[AssistantContentType.TOOL_CALL]
    id: str
    name: str
    arguments: dict[str, Any]
    thought_signature: NotRequired[str]


type AssistantContent = TextContent | Reasoning | ToolCall


class AssistantMessageError(TypedDict):
    message: str


class ModelInfo(TypedDict):
    api: str
    provider: str
    model: str


class FinishReason(StrEnum):
    STOP = 'stop'
    LENGTH = 'length'
    TOOL_USE = 'tool_use'
    ERROR = 'error'
    ABORTED = 'aborted'


class TokenUsageCost(TypedDict):
    input: float
    output: float
    cache_read: float
    cache_write: float
    total: float


class TokenUsage(TypedDict):
    input: int
    output: int
    cache_read: int
    cache_write: int
    total: int
    cost: TokenUsageCost


class UserMessage(BaseMessage):
    mtype: Literal[MessageType.USER]
    content: Content


class SystemMessage(BaseMessage):
    mtype: Literal[MessageType.SYSTEM]
    content: Content


class AssistantMessage(BaseMessage):
    mtype: Literal[MessageType.ASSISTANT]
    content: list[AssistantContent]
    model: ModelInfo
    token_usage: TokenUsage
    finish_reason: NotRequired[FinishReason]
    error: NotRequired[AssistantMessageError]


class ToolResult(TypedDict):
    success: bool
    content: NotRequired[Content]
    error: NotRequired[str]


class ToolResultMessage(BaseMessage):
    mtype: Literal[MessageType.TOOL_RESULT]
    call_id: str
    tool_name: str
    result: ToolResult


type AgentMessage = UserMessage | SystemMessage | AssistantMessage | ToolResultMessage


class StreamingMessageType(StrEnum):
    TEXT_START = 'text_start'
    TEXT_DELTA = 'text_delta'
    TEXT_END = 'text_end'

    REASONING_START = 'reasoning_start'
    REASONING_DELTA = 'reasoning_delta'
    REASONING_END = 'reasoning_end'


class StreamingMessage(TypedDict):
    session_id: str
    type: StreamingMessageType
    partial: AssistantMessage
    delta: NotRequired[str]
    content_index: int
