import time

from pathlib import Path

from agentron.model.repo import get_model
from agentron.types.model import Model
from agentron.rpc.flux import FluxBackend
from agentron.types.core import ToolFunction
from agentron.agent import Agent
from agentron.tool.manager import CoreToolManager
from agentron.model.auth import resolve_api_key
from agentron.utils.message import make_system_message
from agentron.serialization import auto_write_messages
from agentron.terminal import TerminalOutput


def make_agent(
    *,
    system_prompt: str,
    tools: list[ToolFunction],
    model: Model | str,
    api_key: str | None = None,
    output: Path | str | None = None,
    title: str | None = None,
    terminal: bool = False,
) -> Agent:
    """
    Convenience function to create an Agent with common configurations.

    Args:
        system_prompt: The system prompt to use for the agent.
                       May use the special "file:<path to a file>" syntax to load the prompt from a file.

        tools:
            A list of tool functions that the agent can use.

        model:
            The model to use for the agent.
            Can be specified as a string in the format "provider:model_name"

        api_key:
            An optional API key to use for the model.
            If not provided, the function will attempt to resolve the API key from the environment or configuration.

        output:
            An optional file path [jsonl] to write the agent's messages to in real-time.

        title:
            An optional title for the agent session (persisted as metadata when serialized).

        terminal:
            Whether to also print the agent's activity (messages, tool calls...) to the terminal in real-time.

    Returns:
        An instance of Agent configured with the specified parameters.
    """
    # Resolve the model
    if isinstance(model, str):
        model = get_model(model)

    # Create the agent
    agent = Agent(
        messages=[
            # Resolve the system prompt
            make_system_message(system_prompt)
        ],
    )

    # The tool manager is responsible for providing available tool schemas
    # and executing tool calls.
    # The default instance auto-generates the schemas from the provided tool functions.
    # For execution, it handles tasks like validating the arguments and appropriately
    # wrapping the results.
    # For more advanced uses (e.g. injecting a permissions system), this can be overriden.
    tool_manager = CoreToolManager(tools=tools)
    agent.set_tool_manager(tool_manager)
    agent.set_backend(
        FluxBackend(
            model=model,
            tools=tool_manager.schema,
            api_key=api_key or resolve_api_key(model),
        )
    )

    # Setup metadata
    agent.metadata['model'] = model
    agent.metadata['cwd'] = str(Path.cwd())
    agent.metadata['created'] = int(time.time() * 1000)
    if title is not None:
        agent.metadata['title'] = title

    # Auto-persist messages if an output path is provided.
    if output is not None:
        auto_write_messages(agent, Path(output))

    # Stream agent activity to the terminal if requested.
    if terminal:
        TerminalOutput(agent)

    return agent
