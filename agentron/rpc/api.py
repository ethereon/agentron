from typing import TypedDict, NotRequired, Literal, Any
from enum import StrEnum

from agentron.model import Model, ModelReasoningLevel
from agentron.types.message import AgentMessage
from agentron.types.core import ToolSchema


class OAuthLoginData(TypedDict):
    type: Literal['oauth']
    provider: str
    credentials: dict[str, Any]


type ApiKeySource = str | OAuthLoginData


class NotificationKind(StrEnum):
    STREAMING_MESSAGE = 'streaming_message'


class RequestKind(StrEnum):
    SESSION_START = 'session_start'
    TRANSMIT = 'transmit'


class SessionStartRequest(TypedDict):
    session_id: str
    model: Model
    tools: list[ToolSchema]
    api_key: NotRequired[ApiKeySource | None]


class TransmitRequest(TypedDict):
    session_id: str
    messages: list[AgentMessage]
    reasoning: ModelReasoningLevel | None
