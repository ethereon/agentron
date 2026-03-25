"""
Agentron CLI
"""

from pathlib import Path
from typing import get_args
from argparse import ArgumentParser, Namespace

from agentron.types.model import ModelReasoningLevel


def handle_code_command(args: Namespace) -> None:
    from agentron.cli.code import run_coding_agent

    run_coding_agent(
        system_prompt=args.system,
        user_prompt=args.user,
        model=args.model,
        output=args.output,
        reasoning=args.reasoning,
    )


def handle_login_command(args: Namespace) -> None:
    from agentron.cli.login import run_login

    run_login()


def main():
    parser = ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        required=True,
    )

    # Code command
    code_parser = subparsers.add_parser(
        'code',
        help='Run a coding agent.',
    )
    code_parser.add_argument(
        '--system',
        required=True,
        help='System prompt for the coding agent. May be a path to a file or a string.',
    )
    code_parser.add_argument(
        '--user',
        required=True,
        help='User prompt for the coding agent. May be a path to a file or a string.',
    )
    code_parser.add_argument(
        '--model',
        required=True,
        help='Model to use for the coding agent (e.g.: openai-codex/gpt-5.4).',
    )
    code_parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help='Directory/file to save the coding agent session outputs.',
    )
    code_parser.add_argument(
        '--reasoning',
        default='medium',
        help='Reasoning level for the coding agent.',
        choices=get_args(ModelReasoningLevel.__value__),
    )
    code_parser.set_defaults(func=handle_code_command)

    # Login command
    login_parser = subparsers.add_parser(
        'login',
        help='Login to an OAuth provider like OpenAI ChatGPT.',
    )
    login_parser.set_defaults(func=handle_login_command)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
