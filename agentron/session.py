import asyncio

from typing import Awaitable, Callable, Iterable


from agentron.tool.manager import ToolManager
from agentron.utils.publisher import Publisher
from agentron.utils.messages import as_tool_result_message, extract_tool_calls, make_user_message
from agentron.messages import (
    Content,
    AgentMessage,
    AssistantMessage,
    StreamingMessage,
    ToolCall,
    ToolResult,
)


type Transmitter = Callable[[list[AgentMessage]], Awaitable[AssistantMessage]]


class AgentSession:
    def __init__(
        self,
        id: str,
        tool_manager: ToolManager,
        transmitter: Transmitter,
        messages: Iterable[AgentMessage] | None = None,
    ):
        self.id = id
        self.messages: list[AgentMessage] = list(messages) if messages else []
        self.tool_manager = tool_manager
        self.transmitter = transmitter

        self.on_transmit = Publisher[None]()
        self.on_new_message = Publisher[AgentMessage]()
        self.on_streaming_message = Publisher[StreamingMessage]()
        self.on_tool_call = Publisher[ToolCall]()

    async def ask(self, prompt: str | Content) -> AssistantMessage:
        self._push_message(make_user_message(prompt))
        return await self.resume()

    async def resume(self) -> AssistantMessage:
        while True:
            # Get the LLM's response
            response = await self.transmit()
            self._push_message(response)

            # Check if the LLM called any tools
            tool_calls = extract_tool_calls(response)
            if not tool_calls:
                # No tool calls, we're done
                return response

            # Execute tool calls
            tool_results = await self.run_tool_call_batch(tool_calls)

            # Add tool results and continue the loop
            self._push_messages(map(as_tool_result_message, tool_results, tool_calls))

    async def run_tool_call_batch(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """
        Runs a batch of tool calls concurrently and returns their results.
        """
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(self.run_tool_call(tc)) for tc in tool_calls]
        return [task.result() for task in tasks]

    async def run_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """
        Executes a single tool call and returns the result.
        """
        self.on_tool_call.publish(tool_call)
        return await self.tool_manager(tool_call)

    async def transmit(self) -> AssistantMessage:
        self.on_transmit.publish(None)
        return await self.transmitter(self.messages)

    def _push_messages(self, messages: Iterable[AgentMessage]):
        for msg in messages:
            self._push_message(msg)

    def _push_message(self, message: AgentMessage):
        self.messages.append(message)
        self.on_new_message.publish(message)
