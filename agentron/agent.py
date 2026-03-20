import asyncio
import uuid

from typing import Iterable

from agentron.model.types import ModelReasoningLevel
from agentron.typing import LLMBackend
from agentron.tool.manager import ToolManager
from agentron.utils.publisher import Publisher
from agentron.utils.messages import as_tool_result_message, extract_assistant_text, extract_tool_calls, make_user_message
from agentron.messages import (
    Content,
    AgentMessage,
    AssistantMessage,
    StreamingMessage,
    ToolCall,
    ToolResult,
)


class Agent:
    def __init__(
        self,
        session_id: str | None = None,
        messages: Iterable[AgentMessage] | None = None,
        metadata: dict | None = None,
    ):
        self.session_id = session_id or uuid.uuid4().hex
        self.messages: list[AgentMessage] = list(messages) if messages else []
        self.tool_manager: ToolManager | None = None
        self.backend: LLMBackend | None = None
        self.is_finalized = False
        self.metadata = metadata or {}

        self.on_transmit = Publisher[None]()
        self.on_new_message = Publisher[AgentMessage]()
        self.on_streaming_message = Publisher[StreamingMessage]()
        self.on_tool_call = Publisher[ToolCall]()
        self.on_finalize = Publisher[None]()

    async def ask(
        self,
        prompt: str | Content,
        reasoning: ModelReasoningLevel | None = None,
    ) -> str | None:
        if self.is_finalized:
            raise RuntimeError('Cannot ask a finalized agent.')

        self._push_message(make_user_message(prompt))
        response = await self._resume(reasoning=reasoning)
        return extract_assistant_text(response)

    def set_backend(self, backend: LLMBackend) -> None:
        self.backend = backend

    def set_tool_manager(self, tool_manager: ToolManager) -> None:
        self.tool_manager = tool_manager

    def finalize(self):
        if self.is_finalized:
            return

        self.is_finalized = True
        self.on_finalize.publish(None)

        Publisher.clear_all(
            self.on_transmit,
            self.on_new_message,
            self.on_streaming_message,
            self.on_tool_call,
            self.on_finalize,
        )

    async def _resume(
        self,
        *,
        reasoning: ModelReasoningLevel | None,
    ) -> AssistantMessage:
        while True:
            # Get the LLM's response
            response = await self._transmit(reasoning=reasoning)
            self._push_message(response)

            # Check if the LLM called any tools
            tool_calls = extract_tool_calls(response)
            if not tool_calls:
                # No tool calls, we're done
                return response

            # Execute tool calls
            tool_results = await self._run_tool_call_batch(tool_calls)

            # Add tool results and continue the loop
            self._push_messages(map(as_tool_result_message, tool_results, tool_calls))

    async def _run_tool_call_batch(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """
        Runs a batch of tool calls concurrently and returns their results.
        """
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(self._run_tool_call(tc)) for tc in tool_calls]
        return [task.result() for task in tasks]

    async def _run_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """
        Executes a single tool call and returns the result.
        """
        if self.tool_manager is None:
            raise RuntimeError('No tool manager configured for this agent.')
        self.on_tool_call.publish(tool_call)
        return await self.tool_manager(tool_call)

    async def _transmit(self, *, reasoning: ModelReasoningLevel | None) -> AssistantMessage:
        if self.backend is None:
            raise RuntimeError('No LLM backend configured for this agent.')

        self.on_transmit.publish(None)
        return await self.backend(
            session_id=self.session_id,
            messages=self.messages,
            reasoning=reasoning,
            on_streaming_message=self.on_streaming_message.publish,
        )

    def _push_messages(self, messages: Iterable[AgentMessage]):
        for msg in messages:
            self._push_message(msg)

    def _push_message(self, message: AgentMessage):
        self.messages.append(message)
        self.on_new_message.publish(message)

    def __enter__(self):
        if self.is_finalized:
            raise RuntimeError('This agent has already been finalized.')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finalize()
        return False
