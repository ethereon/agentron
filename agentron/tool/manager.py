from typing import Sequence, Protocol

from agentron.typing import ToolFunction, ToolSchema
from agentron.messages import ToolCall, ToolResult
from agentron.utils.messages import as_content
from agentron.utils.asyn import maybe_await
from agentron.tool.parser import generate_tool_schema


class ToolError(RuntimeError): ...


class ToolManager(Protocol):
    schema: list[ToolSchema]
    """
    A list of tool schemas representing the available tools.
    """

    async def __call__(self, tool_call: ToolCall) -> ToolResult:
        """
        Executes the given tool call and returns the result.

        Error handling:
            May raise a ToolError if the invocation is deemed invalid.
            The ToolError message is intended to be propagated back to the LLM.
            All other exception types are considered internal errors, and their
            details are not transmitted back to the LLM (but available in the
            ToolResult.internal_error field for introspection).
        """
        ...


class CoreToolManager(ToolManager):
    def __init__(self, tools: Sequence[ToolFunction]):
        self.schema = [generate_tool_schema(tool) for tool in tools]
        self.tools_by_name = {tool_schema['name']: tool for tool_schema, tool in zip(self.schema, tools)}

    async def __call__(self, tool_call: ToolCall) -> ToolResult:
        try:
            tool = self.tools_by_name.get(tool_call['name'])
            if not tool:
                raise ToolError(f'No tool named {tool_call["name"]} found.')

            # TODO: Validate tool arguments against a schema
            tool_kwargs = tool_call['arguments']
            result = await maybe_await(tool(**tool_kwargs))

            return ToolResult(
                success=True,
                content=as_content(result),
            )
        except ToolError as err:
            return ToolResult(
                success=False,
                content=as_content(f'Error: {str(err)}'),
            )
