from typing import TYPE_CHECKING, Callable, Any, Awaitable, TypedDict, Protocol
from agentron.types.message import Content, AgentMessage, AssistantMessage, StreamingMessage
from agentron.types.model import ModelReasoningLevel

if TYPE_CHECKING:
    from PIL import Image

    PILImage = Image.Image
else:
    PILImage = Any

type ContentLike = str | PILImage | Content

type ToolFunction = Callable[..., ContentLike | Awaitable[ContentLike]]

type StreamingMessageHandler = Callable[[StreamingMessage], None]


class ToolSchema(TypedDict):
    name: str
    description: str
    parameters: dict[str, Any]


class LLMBackend(Protocol):
    async def __call__(
        self,
        *,
        session_id: str,
        messages: list[AgentMessage],
        reasoning: ModelReasoningLevel | None,
        on_streaming_message: StreamingMessageHandler,
    ) -> AssistantMessage: ...
