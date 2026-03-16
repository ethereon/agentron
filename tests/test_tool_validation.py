from __future__ import annotations

import asyncio
import unittest

from typing import Literal

from typing_extensions import NotRequired, TypedDict

from agentron.messages import ToolCall
from agentron.tool.manager import CoreToolManager, ToolError, validate_tool_arguments
from agentron.tool.parser import generate_tool_schema


class SearchOptions(TypedDict):
    verbose: bool
    """Whether verbose output is enabled."""
    timeout: NotRequired[int]
    """Optional timeout in seconds."""


class SearchPayload(TypedDict):
    name: str
    """Payload name."""


def search_tool(query: str, limit: int = 10, options: SearchOptions | None = None) -> str:
    """
    Search for matching records.
    Args:
        query: Search text.
        limit: Maximum number of records to return.
        options: Optional search options.
    Returns:
        A search summary.
    """
    return f'{query}:{limit}:{options}'


def mode_tool(mode: Literal['fast', 'safe']) -> str:
    """
    Run the tool in a named mode.
    Args:
        mode: The mode to run.
    Returns:
        The selected mode.
    """
    return mode


def union_tool(payload: SearchPayload | list[str]) -> str:
    """
    Accept either an object payload or a list of strings.
    Args:
        payload: The payload to process.
    Returns:
        A summary of the payload.
    """
    if isinstance(payload, dict):
        return payload['name']
    return ','.join(payload)


_tracked_tool_calls: list[str] = []


def tracked_tool(query: str) -> str:
    """
    Record a tool invocation.
    Args:
        query: The query to record.
    Returns:
        The recorded query.
    """
    _tracked_tool_calls.append(query)
    return query


class TestValidateToolArguments(unittest.TestCase):
    def setUp(self) -> None:
        self.search_schema = generate_tool_schema(search_tool)

    def test_accepts_valid_arguments(self):
        arguments = {
            'query': 'orbit',
            'limit': 5,
            'options': {
                'verbose': True,
                'timeout': 2,
            },
        }

        validated_arguments = validate_tool_arguments(self.search_schema, arguments)

        self.assertIs(validated_arguments, arguments)

    def test_reports_missing_and_unexpected_arguments(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(self.search_schema, {'limit': 3, 'extra': True})

        message = str(ctx.exception)
        self.assertIn('Invalid arguments for tool "search_tool"', message)
        self.assertIn('Missing required argument "query".', message)
        self.assertIn('Unexpected argument "extra".', message)

    def test_reports_nested_type_errors(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(
                self.search_schema,
                {
                    'query': 9,
                    'options': {
                        'verbose': 'yes',
                        'extra': 1,
                    },
                },
            )

        message = str(ctx.exception)
        self.assertIn('"query" must be string; got integer.', message)
        self.assertIn('Unexpected argument "options.extra".', message)
        self.assertIn('"options.verbose" must be boolean; got string.', message)

    def test_reports_invalid_enum_value(self):
        schema = generate_tool_schema(mode_tool)

        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(schema, {'mode': 'turbo'})

        message = str(ctx.exception)
        self.assertIn('"mode" must be one of', message)
        self.assertIn("'fast'", message)
        self.assertIn("'safe'", message)
        self.assertIn("'turbo'", message)

    def test_accepts_anyof_union_branches(self):
        schema = generate_tool_schema(union_tool)

        validate_tool_arguments(schema, {'payload': {'name': 'alpha'}})
        validate_tool_arguments(schema, {'payload': ['alpha', 'beta']})

    def test_reports_anyof_union_mismatch(self):
        schema = generate_tool_schema(union_tool)

        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(schema, {'payload': 'alpha'})

        self.assertIn('"payload" must be object or array; got string.', str(ctx.exception))


class TestCoreToolManager(unittest.TestCase):
    def setUp(self) -> None:
        _tracked_tool_calls.clear()

    def test_invalid_arguments_are_returned_to_the_llm_and_not_invoked(self):
        manager = CoreToolManager([tracked_tool])
        tool_call = ToolCall(
            type='tool_call',
            id='call-1',
            name='tracked_tool',
            arguments={},
        )

        result = asyncio.run(manager(tool_call))

        self.assertFalse(result['success'])
        self.assertEqual(_tracked_tool_calls, [])
        self.assertIn('Missing required argument "query".', result['content']['text'])
