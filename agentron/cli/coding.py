import asyncio

from pathlib import Path

from agentron import make_agent, get_model
from agentron.agent import Agent
from agentron.types.core import ToolFunction
from agentron.types.model import ModelReasoningLevel
from agentron.kit.io import read_file, write_file, apply_patch
from agentron.kit.repl import RunInPythonREPL
from agentron.kit.shell import bash
from agentron.web.server import serve

SYSTEM_PROMPT = """You are an expert coding agent.

- The user will provide instructions on what to do. Ask for clarification only if the task is ambiguous and you cannot make a reasonable assumption.
- Think through your approach before acting, especially for multi-step tasks.
- Before making tool calls, briefly explain what you're about to do — skip this for trivial actions.
- If a tool call fails, re-read its description carefully and correct your invocation before retrying. Avoid repeating the same failing call.
- Keep responses concise. Prefer code and output over lengthy prose.
"""


def resolve_prompt(source: Path | list[Path]) -> str:
    sources = [source] if isinstance(source, Path) else source
    assert sources, 'At least one prompt source must be provided.'
    texts = []
    for source in sources:
        maybe_path = source.resolve()
        if maybe_path.is_file():
            print(f'Loading prompt from file: {maybe_path}')
            texts.append(maybe_path.read_text())
        else:
            raise FileNotFoundError(f'Prompt file not found: {source}')

    return '\n\n'.join(texts)


def resolve_system_prompt(source: Path | None) -> str:
    if source is None:
        print('Using default system prompt.')
        return SYSTEM_PROMPT
    return resolve_prompt(source)


class CodingHarness:
    def __init__(
        self,
        *,
        model: str,
        system_prompt: str,
        output: Path | None = None,
    ):
        self.model = get_model(model)
        self.system_prompt = system_prompt
        self.output = output
        self._agent: Agent | None = None
        self.tools: list[ToolFunction] = [
            read_file,
            write_file,
            apply_patch,
            bash,
        ]

    def add_python_repl_tool(self, code: str | None = None) -> None:
        assert self._agent is None, 'Tools must be added before the agent is initialized.'
        repl = RunInPythonREPL()
        if code is not None:
            repl(code)
        self.tools.append(repl)

    @property
    def agent(self) -> Agent:
        if self._agent is None:
            self._agent = make_agent(
                model=self.model,
                system_prompt=self.system_prompt,
                tools=self.tools,
                output=self.output,
            )
        return self._agent

    def run(
        self,
        user_prompt: str,
        reasoning: ModelReasoningLevel = 'medium',
    ):
        with serve(self.agent):
            asyncio.run(
                self.agent.ask(
                    user_prompt,
                    reasoning=reasoning,
                )
            )
