from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


type MessageType = Literal[
    'system',
    'user',
    'assistant',
    'tool_result',
]


class BaseMessage(TypedDict):
    id: str
    timestamp: int


type ContentType = Literal['text']


class TextContent(TypedDict):
    type: Literal['text']
    text: str
    text_signature: NotRequired[str]


type Content = TextContent

type AssistantContentType = Literal[
    'reasoning',
    'tool_call',
]


class Reasoning(TypedDict):
    type: Literal['reasoning']
    text: str
    signature: NotRequired[str]
    redacted: NotRequired[bool]


class ToolCall(TypedDict):
    type: Literal['tool_call']
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


type FinishReason = Literal[
    'stop',
    'length',
    'tool_use',
    'error',
    'aborted',
]


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
    mtype: Literal['user']
    content: Content


class SystemMessage(BaseMessage):
    mtype: Literal['system']
    content: Content


class AssistantMessage(BaseMessage):
    mtype: Literal['assistant']
    content: list[AssistantContent]
    model: ModelInfo
    token_usage: TokenUsage
    finish_reason: NotRequired[FinishReason]
    error: NotRequired[AssistantMessageError]


class ToolResult(TypedDict):
    success: bool
    content: Content


class ToolResultMessage(BaseMessage):
    mtype: Literal['tool_result']
    call_id: str
    tool_name: str
    result: ToolResult


type AgentMessage = UserMessage | SystemMessage | AssistantMessage | ToolResultMessage

type StreamingMessageType = Literal[
    'text_start',
    'text_delta',
    'text_end',
    'reasoning_start',
    'reasoning_delta',
    'reasoning_end',
]


class StreamingMessage(TypedDict):
    session_id: str
    type: StreamingMessageType
    partial: AssistantMessage
    delta: NotRequired[str]
    content_index: int
