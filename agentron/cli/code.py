import asyncio

from pathlib import Path

from agentron import make_agent, get_model
from agentron.types.model import ModelReasoningLevel
from agentron.kit.io import read_file, write_file, patch_file
from agentron.kit.shell import bash
from agentron.web import serve

SYSTEM_PROMPT = """You are an expert coding agent.

- The user will provide instructions on what to do. Ask for clarification only if the task is ambiguous and you cannot make a reasonable assumption.
- Think through your approach before acting, especially for multi-step tasks.
- Before making tool calls, briefly explain what you're about to do — skip this for trivial actions.
- If a tool call fails, re-read its description carefully and correct your invocation before retrying. Avoid repeating the same failing call.
- Keep responses concise. Prefer code and output over lengthy prose.
"""


def resolve_prompt(source: str) -> str:
    maybe_path = Path(source).resolve()
    if maybe_path.is_file():
        print(f'Loading prompt from file: {maybe_path}')
        return maybe_path.read_text()
    return source


def resolve_system_prompt(source: str | None) -> str:
    if source is None:
        print('Using default system prompt.')
        return SYSTEM_PROMPT
    return resolve_prompt(source)


def run_coding_agent(
    model: str,
    user_prompt: str,
    system_prompt: str | None = None,
    output: Path | None = None,
    reasoning: ModelReasoningLevel = 'medium',
):
    agent = make_agent(
        model=get_model(model),
        system_prompt=resolve_system_prompt(system_prompt),
        tools=[
            read_file,
            write_file,
            patch_file,
            bash,
        ],
        output=output,
    )
    with serve(agent):
        asyncio.run(
            agent.ask(
                resolve_prompt(user_prompt),
                reasoning=reasoning,
            )
        )
