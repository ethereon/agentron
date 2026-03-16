from agentron.model.types import Model
from agentron.rpc.flux import FluxBackend
from agentron.typing import ToolFunction
from agentron.agent import Agent
from agentron.tool.manager import CoreToolManager
from agentron.model.auth import resolve_api_key
from agentron.utils.messages import make_system_message


def make_agent(
    system_prompt: str,
    tools: list[ToolFunction],
    model: Model,
    api_key: str | None = None,
):
    agent = Agent(
        messages=[make_system_message(system_prompt)],
    )
    tool_manager = CoreToolManager(tools=tools)
    agent.set_tool_manager(tool_manager)
    agent.set_backend(
        FluxBackend(
            model=model,
            tools=tool_manager.schema,
            api_key=api_key or resolve_api_key(model),
        )
    )
    return agent
