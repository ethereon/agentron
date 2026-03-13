from typing import TYPE_CHECKING, Callable, Any, Awaitable, TypedDict, Protocol
from agentron.messages import Content, AgentMessage, AssistantMessage

if TYPE_CHECKING:
    from PIL import Image

    PILImage = Image.Image
else:
    PILImage = Any

type ContentLike = str | PILImage | Content

type ToolFunction = Callable[..., ContentLike | Awaitable[ContentLike]]


class ToolSchema(TypedDict):
    name: str
    description: str
    parameters: dict[str, Any]


class LLMBackend(Protocol):
    async def __call__(self, messages: list[AgentMessage], tools: list[ToolSchema]) -> AssistantMessage: ...
