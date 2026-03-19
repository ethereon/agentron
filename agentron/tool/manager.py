from typing import Sequence, Protocol

from agentron.typing import ToolFunction, ToolSchema
from agentron.messages import ToolCall, ToolResult
from agentron.utils.messages import as_content
from agentron.utils.asyn import maybe_await
from agentron.tool.parser import generate_tool_schema
from agentron.tool.validation import validate_tool_arguments


class ToolManager(Protocol):
    schema: list[ToolSchema]
    """
    A list of tool schemas representing the available tools.
    """

    async def __call__(self, tool_call: ToolCall) -> ToolResult:
        """
        Executes the given tool call and returns the result.

        Error handling:
            Any exception raised during the execution of the tool is marks the tool call as failed,
            and the exception message is included in the result sent back to the LLM.
        """
        ...


class CoreToolManager(ToolManager):
    def __init__(self, tools: Sequence[ToolFunction]):
        self.schema = [generate_tool_schema(tool) for tool in tools]
        self.tools_by_name = {tool_schema['name']: tool for tool_schema, tool in zip(self.schema, tools)}
        self.schema_by_name = {tool_schema['name']: tool_schema for tool_schema in self.schema}

    async def __call__(self, tool_call: ToolCall) -> ToolResult:
        try:
            tool = self.tools_by_name.get(tool_call['name'])
            if not tool:
                raise ValueError(f'No tool named {tool_call["name"]} found.')

            tool_schema = self.schema_by_name[tool_call['name']]
            tool_kwargs = validate_tool_arguments(tool_schema, tool_call['arguments'])
            result = await maybe_await(tool(**tool_kwargs))

            return ToolResult(
                success=True,
                content=as_content(result),
            )
        except BaseException as err:
            return ToolResult(
                success=False,
                content=as_content(_format_tool_error(err)),
            )


def _format_tool_error(err: BaseException) -> str:
    return f'{type(err).__name__}: {str(err)}'
