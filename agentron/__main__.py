"""
Agentron CLI
"""

import sys

from pathlib import Path
from typing import get_args
from argparse import ArgumentParser, Namespace

from agentron.types.model import ModelReasoningLevel


def handle_code_command(args: Namespace) -> int:
    from agentron.cli.coding import CodingHarness, resolve_prompt, resolve_system_prompt

    coder = CodingHarness(
        model=args.model,
        system_prompt=resolve_system_prompt(args.system),
        output=args.output,
    )

    if args.prime_repl is not None:
        print(f'Priming Python REPL tool with code from: {args.prime_repl}')
        coder.add_python_repl_tool(code=args.prime_repl.read_text())

    coder.run(
        user_prompt=resolve_prompt(args.user),
        reasoning=args.reasoning,
    )
    return 0


def handle_login_command(args: Namespace) -> int:
    from agentron.cli.login import run_login

    return run_login()


def handle_web_command(args: Namespace) -> int:
    from agentron.cli.web import run_web_ui

    return run_web_ui(args.session_paths)


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
    code_parser.set_defaults(func=handle_code_command)
    code_parser.add_argument(
        '--model',
        required=True,
        help='Model to use for the coding agent (e.g.: openai-codex/gpt-5.4).',
    )
    code_parser.add_argument(
        '--user',
        required=True,
        type=Path,
        nargs='+',
        help='Path to a file containing the user prompt. Multiple paths can be provided, and will be concatenated to form the final prompt.',
    )
    code_parser.add_argument(
        '--system',
        type=Path,
        default=None,
        help='Path to a file containing the system prompt.',
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
    code_parser.add_argument(
        '--prime-repl',
        type=Path,
        default=None,
        help='Adds a Python REPL tool to the coding agent, and primes it by executing the given file.',
    )

    # Login command
    login_parser = subparsers.add_parser(
        'login',
        help='Login to an OAuth provider like OpenAI ChatGPT.',
    )
    login_parser.set_defaults(func=handle_login_command)

    # Web command
    web_parser = subparsers.add_parser(
        'web',
        help='Launch the Agentron web UI.',
    )
    web_parser.set_defaults(func=handle_web_command)
    web_parser.add_argument(
        'session_paths',
        type=Path,
        nargs='+',
        default=None,
        help='One or more path to a session file or directory containing session files to load in the web UI.',
    )

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()
