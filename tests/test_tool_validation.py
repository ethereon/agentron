from __future__ import annotations

import unittest

from typing import Literal

from typing_extensions import NotRequired, TypedDict

from agentron.tool.parser import generate_tool_schema
from agentron.tool.validation import ToolError, validate_tool_arguments


class SearchOptions(TypedDict):
    verbose: bool
    """Whether verbose output is enabled."""
    timeout: NotRequired[int]
    """Optional timeout in seconds."""


class SearchPayload(TypedDict):
    name: str
    """Payload name."""


class BatchRequest(TypedDict):
    payloads: list[SearchPayload]
    """Payloads to process."""
    options: SearchOptions
    """Options applied to each payload."""


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


def mapping_tool(weights: dict[str, int]) -> str:
    """
    Accept a mapping of labels to integer weights.
    Args:
        weights: Mapping values to validate.
    Returns:
        A summary of the mapping.
    """
    return ','.join(sorted(weights))


def batch_tool(request: BatchRequest) -> int:
    """
    Process a batch request.
    Args:
        request: The batch request to process.
    Returns:
        The number of payloads received.
    """
    return len(request['payloads'])


class TestGenerateToolSchema(unittest.TestCase):
    def test_search_tool_schema_marks_only_query_as_required(self):
        schema = generate_tool_schema(search_tool)

        self.assertEqual(schema['name'], 'search_tool')
        self.assertEqual(
            schema['description'],
            'Search for matching records.\n\nReturns:\n    A search summary.',
        )

        parameters = schema['parameters']
        self.assertEqual(parameters['type'], 'object')
        self.assertEqual(parameters['required'], ['query'])

        query = parameters['properties']['query']
        limit = parameters['properties']['limit']
        options = parameters['properties']['options']

        self.assertEqual(query['type'], 'string')
        self.assertEqual(limit['type'], 'integer')
        self.assertEqual(options['type'], 'object')
        self.assertEqual(options['required'], ['verbose'])
        self.assertEqual(options['properties']['verbose']['description'], 'Whether verbose output is enabled.')
        self.assertNotIn('timeout', options.get('required', []))

    def test_union_tool_schema_uses_anyof_for_object_or_array(self):
        schema = generate_tool_schema(union_tool)

        payload = schema['parameters']['properties']['payload']
        self.assertIn('anyOf', payload)
        self.assertCountEqual([branch['type'] for branch in payload['anyOf']], ['object', 'array'])

        object_branch = next(branch for branch in payload['anyOf'] if branch['type'] == 'object')
        array_branch = next(branch for branch in payload['anyOf'] if branch['type'] == 'array')

        self.assertEqual(object_branch['required'], ['name'])
        self.assertEqual(object_branch['properties']['name']['type'], 'string')
        self.assertEqual(array_branch['items']['type'], 'string')

    def test_mapping_tool_schema_uses_additional_properties(self):
        schema = generate_tool_schema(mapping_tool)

        weights = schema['parameters']['properties']['weights']
        self.assertEqual(weights['type'], 'object')
        self.assertEqual(weights['additionalProperties'], {'type': 'integer'})

    def test_batch_tool_schema_nests_arrays_of_objects(self):
        schema = generate_tool_schema(batch_tool)

        request = schema['parameters']['properties']['request']
        payloads = request['properties']['payloads']
        options = request['properties']['options']

        self.assertEqual(request['type'], 'object')
        self.assertCountEqual(request['required'], ['payloads', 'options'])
        self.assertEqual(payloads['type'], 'array')
        self.assertEqual(payloads['items']['type'], 'object')
        self.assertEqual(payloads['items']['required'], ['name'])
        self.assertEqual(options['properties']['timeout']['type'], 'integer')


class TestValidateToolArguments(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.search_schema = generate_tool_schema(search_tool)
        cls.mode_schema = generate_tool_schema(mode_tool)
        cls.union_schema = generate_tool_schema(union_tool)
        cls.mapping_schema = generate_tool_schema(mapping_tool)
        cls.batch_schema = generate_tool_schema(batch_tool)

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

    def test_accepts_omitting_defaulted_arguments(self):
        arguments = {'query': 'orbit'}

        validated_arguments = validate_tool_arguments(self.search_schema, arguments)

        self.assertIs(validated_arguments, arguments)

    def test_requires_the_top_level_arguments_object(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(self.search_schema, ['orbit'])

        self.assertEqual(
            str(ctx.exception),
            'Invalid arguments for tool "search_tool": the arguments object must be an object; got array.',
        )

    def test_reports_missing_and_unexpected_arguments(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(self.search_schema, {'limit': 3, 'extra': True})

        message = str(ctx.exception)
        self.assertIn('Invalid arguments for tool "search_tool"', message)
        self.assertIn('Missing required argument "query".', message)
        self.assertIn('Unexpected argument "extra".', message)

    def test_reports_nested_missing_and_unexpected_arguments(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(
                self.search_schema,
                {
                    'query': 'orbit',
                    'options': {
                        'timeout': 2,
                        'extra': 1,
                    },
                },
            )

        message = str(ctx.exception)
        self.assertIn('Missing required argument "options.verbose".', message)
        self.assertIn('Unexpected argument "options.extra".', message)

    def test_reports_nested_type_errors(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(
                self.search_schema,
                {
                    'query': 9,
                    'limit': True,
                    'options': {
                        'verbose': 'yes',
                    },
                },
            )

        message = str(ctx.exception)
        self.assertIn('"query" must be string; got integer.', message)
        self.assertIn('"limit" must be integer; got boolean.', message)
        self.assertIn('"options.verbose" must be boolean; got string.', message)

    def test_reports_array_item_paths(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(
                self.batch_schema,
                {
                    'request': {
                        'payloads': [
                            {'name': 'alpha'},
                            {'name': 2},
                        ],
                        'options': {
                            'verbose': True,
                        },
                    },
                },
            )

        self.assertIn('"request.payloads[1].name" must be string; got integer.', str(ctx.exception))

    def test_accepts_typed_dict_arrays(self):
        arguments = {
            'request': {
                'payloads': [
                    {'name': 'alpha'},
                    {'name': 'beta'},
                ],
                'options': {
                    'verbose': False,
                },
            },
        }

        validated_arguments = validate_tool_arguments(self.batch_schema, arguments)

        self.assertIs(validated_arguments, arguments)

    def test_accepts_dict_additional_properties(self):
        arguments = {'weights': {'alpha': 1, 'beta': 2}}

        validated_arguments = validate_tool_arguments(self.mapping_schema, arguments)

        self.assertIs(validated_arguments, arguments)

    def test_reports_invalid_additional_properties_values(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(self.mapping_schema, {'weights': {'alpha': 'heavy'}})

        self.assertIn('"weights.alpha" must be integer; got string.', str(ctx.exception))

    def test_reports_non_string_additional_properties_keys(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(self.mapping_schema, {'weights': {1: 2}})

        self.assertIn('"weights" must use string keys; got key 1.', str(ctx.exception))

    def test_reports_invalid_enum_value(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(self.mode_schema, {'mode': 'turbo'})

        message = str(ctx.exception)
        self.assertIn('"mode" must be one of', message)
        self.assertIn("'fast'", message)
        self.assertIn("'safe'", message)
        self.assertIn("'turbo'", message)

    def test_accepts_anyof_union_branches(self):
        validate_tool_arguments(self.union_schema, {'payload': {'name': 'alpha'}})
        validate_tool_arguments(self.union_schema, {'payload': ['alpha', 'beta']})

    def test_reports_anyof_union_mismatch(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(self.union_schema, {'payload': 'alpha'})

        self.assertIn('"payload" must be object or array; got string.', str(ctx.exception))

    def test_optional_parameters_must_be_omitted_instead_of_null(self):
        with self.assertRaises(ToolError) as ctx:
            validate_tool_arguments(self.search_schema, {'query': 'orbit', 'options': None})

        self.assertIn('"options" must be object; got null.', str(ctx.exception))
