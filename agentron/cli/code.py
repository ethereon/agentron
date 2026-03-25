import asyncio

from pathlib import Path

from agentron import make_agent, get_model
from agentron.types.model import ModelReasoningLevel
from agentron.kit.io import read_file, write_file, patch_file
from agentron.kit.shell import bash
from agentron.web import serve


def resolve_prompt(source: str) -> str:
    maybe_path = Path(source).resolve()
    if maybe_path.is_file():
        print(f'Loading prompt from file: {maybe_path}')
        return maybe_path.read_text()
    return source


def run_coding_agent(
    system_prompt: str,
    user_prompt: str,
    model: str,
    output: Path | None = None,
    reasoning: ModelReasoningLevel = 'medium',
):
    agent = make_agent(
        model=get_model(model),
        system_prompt=resolve_prompt(system_prompt),
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
