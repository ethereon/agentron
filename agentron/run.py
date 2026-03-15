import uuid
import logging

from agentron.rpc.backend import FluxTransmitter
from agentron.typing import ToolFunction
from agentron.model import Model, ModelReasoningLevel
from agentron.session import AgentSession
from agentron.tool.manager import CoreToolManager
from agentron.model.auth import resolve_api_key
from agentron.utils.messages import make_system_message


logger = logging.getLogger(__name__)


def make_agent(
    system_prompt: str,
    tools: list[ToolFunction],
    model: Model,
    reasoning_level: ModelReasoningLevel = ModelReasoningLevel.MEDIUM,
    api_key: str | None = None,
):
    session_id = uuid.uuid4().hex
    tool_manager = CoreToolManager(tools=tools)
    transmitter = FluxTransmitter(
        session_id=session_id,
        tools=tool_manager.schema,
        model=model,
        api_key=api_key or resolve_api_key(model),
        reasoning_level=reasoning_level,
    )
    session = AgentSession(
        id=session_id,
        tool_manager=tool_manager,
        messages=[make_system_message(system_prompt)],
        transmitter=transmitter,
    )
    transmitter.on_streaming_message = session.on_streaming_message.publish
    return session
