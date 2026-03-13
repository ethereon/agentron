from __future__ import annotations
from agentron.tool.parser import (
    _all_primitive_schemas,
    _is_union,
    _parse_google_docstring,
    _parse_interface_type,
    _resolve_type,
    _resolve_union,
    generate_tool_schema,
)
from agentron.typing import ToolSchema

import enum
import dataclasses
import sys
import unittest
from typing import Dict, List, Literal, Optional, Union

from typing_extensions import NotRequired, TypedDict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _props(schema: ToolSchema) -> dict:
    return schema['parameters']['properties']


def _required(schema: ToolSchema) -> list:
    return schema['parameters'].get('required', [])


# ---------------------------------------------------------------------------
# Shared module-level fixtures
# (defined at module scope so get_type_hints can resolve them)
# ---------------------------------------------------------------------------


def basic_func(alpha: int, bar: str) -> None:
    """
    This is a docstring for the foo function.
    Args:
        alpha: This is the alpha parameter, which is an integer.
            Then there is this extended description.
            Also this here.
        bar: This is the bar parameter, which is a string.
    """
    ...


def search_func(
    query: str,
    max_results: Optional[int] = 10,
    tags: List[str] = [],
) -> List[str]:
    """
    Search for documents matching a query.
    Args:
        query: The search query string.
        max_results: Maximum number of results to return.
        tags: Filter results by these tags.
    Returns:
        List of matching document IDs.
    """
    ...


class UserProfile(TypedDict):
    name: str
    """The user's full name."""
    age: int
    """Age in years."""
    email: NotRequired[str]
    """Optional email address."""


def update_user_func(profile: UserProfile) -> bool:
    """
    Update a user profile in the database.
    Args:
        profile: The user profile data to store.
    Returns:
        True on success.
    """
    ...


@dataclasses.dataclass
class Point:
    """A 2-D point."""

    x: float
    """X coordinate."""
    y: float
    """Y coordinate."""
    label: Optional[str] = None
    """Optional label."""


def plot_point_func(point: Point) -> None:
    """
    Plot a single point on the canvas.
    Args:
        point: The point to plot.
    Returns:
        None.
    """
    ...


class SimpleTypedDict(TypedDict):
    name: str
    """The name field."""
    age: int
    """The age field."""
    nickname: NotRequired[str]
    """An optional nickname."""


@dataclasses.dataclass
class SimpleDataclass:
    """A simple point."""

    x: float
    """X coordinate."""
    y: float
    """Y coordinate."""
    label: Optional[str] = None
    """Optional label."""


class StringMode(enum.StrEnum):
    FAST = 'fast'
    SAFE = 'safe'


class LegacyStringMode(str, enum.Enum):
    FAST = 'fast'
    SAFE = 'safe'


# ---------------------------------------------------------------------------
# 1. _resolve_type — primitives and simple types
# ---------------------------------------------------------------------------


class TestResolveTypePrimitives(unittest.TestCase):
    def test_int(self):
        self.assertEqual(_resolve_type(int), {'type': 'integer'})

    def test_float(self):
        self.assertEqual(_resolve_type(float), {'type': 'number'})

    def test_str(self):
        self.assertEqual(_resolve_type(str), {'type': 'string'})

    def test_bool(self):
        self.assertEqual(_resolve_type(bool), {'type': 'boolean'})

    def test_none_type(self):
        self.assertEqual(_resolve_type(type(None)), {'type': 'null'})

    def test_list_typed(self):
        self.assertEqual(_resolve_type(List[str]), {'type': 'array', 'items': {'type': 'string'}})

    def test_list_nested(self):
        self.assertEqual(
            _resolve_type(List[List[int]]),
            {'type': 'array', 'items': {'type': 'array', 'items': {'type': 'integer'}}},
        )

    def test_list_bare(self):
        result = _resolve_type(list)
        self.assertEqual(result['type'], 'array')
        self.assertNotIn('items', result)

    def test_dict_typed(self):
        self.assertEqual(
            _resolve_type(Dict[str, int]),
            {'type': 'object', 'additionalProperties': {'type': 'integer'}},
        )

    def test_dict_bare(self):
        result = _resolve_type(dict)
        self.assertEqual(result['type'], 'object')
        self.assertNotIn('additionalProperties', result)

    def test_literal_str(self):
        self.assertEqual(
            _resolve_type(Literal['a', 'b']),
            {'type': 'string', 'enum': ['a', 'b']},
        )

    def test_literal_int(self):
        self.assertEqual(
            _resolve_type(Literal[1, 2, 3]),
            {'type': 'integer', 'enum': [1, 2, 3]},
        )

    def test_literal_mixed_no_type_key(self):
        result = _resolve_type(Literal['x', 1])
        self.assertIn('enum', result)
        self.assertNotIn('type', result)

    def test_string_enum(self):
        for enum_type in (StringMode, LegacyStringMode):
            with self.subTest(enum_type=enum_type.__name__):
                self.assertEqual(
                    _resolve_type(enum_type),
                    {'type': 'string', 'enum': ['fast', 'safe']},
                )

    def test_non_string_enum_unsupported(self):
        class NumberMode(enum.Enum):
            FAST = 1
            SAFE = 2

        with self.assertRaises(TypeError) as ctx:
            _resolve_type(NumberMode)
        self.assertIn('JSON Schema', str(ctx.exception))

    def test_unsupported_raises(self):
        with self.assertRaises(TypeError) as ctx:
            _resolve_type(set)
        self.assertIn('JSON Schema', str(ctx.exception))


# ---------------------------------------------------------------------------
# 2. Union / Optional representation — the core new behaviour
# ---------------------------------------------------------------------------


class TestUnionRepresentation(unittest.TestCase):
    """Verify OpenAI-style type-array output for unions."""

    # --- _all_primitive_schemas helper ---

    def test_all_primitive_true(self):
        self.assertTrue(_all_primitive_schemas([{'type': 'integer'}, {'type': 'null'}]))

    def test_all_primitive_false_when_array(self):
        self.assertFalse(_all_primitive_schemas([{'type': 'array', 'items': {'type': 'str'}}, {'type': 'null'}]))

    def test_all_primitive_true_for_plain_object_string(self):
        # {"type": "object"} with no other keys satisfies the primitive-schema predicate
        # (it has exactly one key whose value is a plain string).
        self.assertTrue(_all_primitive_schemas([{'type': 'object'}, {'type': 'string'}]))

    def test_all_primitive_false_when_object_has_properties(self):
        # Once an object has extra keys it is no longer a primitive scalar schema.
        self.assertFalse(
            _all_primitive_schemas(
                [
                    {'type': 'object', 'properties': {}},
                    {'type': 'string'},
                ]
            )
        )

    def test_all_primitive_false_when_anyof(self):
        self.assertFalse(_all_primitive_schemas([{'anyOf': [{'type': 'integer'}]}]))

    # --- _resolve_union ---

    def test_resolve_union_all_primitives_gives_type_array(self):
        result = _resolve_union((int, str))
        self.assertEqual(result, {'type': ['integer', 'string']})

    def test_resolve_union_with_null_gives_type_array(self):
        result = _resolve_union((int, type(None)))
        self.assertEqual(result, {'type': ['integer', 'null']})

    def test_resolve_union_complex_gives_anyof(self):
        # list[str] | int cannot collapse to a type array
        result = _resolve_union((List[str], int))
        self.assertIn('anyOf', result)
        self.assertNotIn('type', result)

    def test_resolve_union_single_primitive_unwrapped(self):
        # Union of a single non-None primitive should just return that type string
        result = _resolve_union((int,))
        self.assertEqual(result, {'type': 'integer'})

    # --- Optional[X] via _resolve_type ---

    def test_optional_int_is_type_array(self):
        result = _resolve_type(Optional[int])
        self.assertEqual(result, {'type': ['integer', 'null']})

    def test_optional_str_is_type_array(self):
        result = _resolve_type(Optional[str])
        self.assertEqual(result, {'type': ['string', 'null']})

    def test_optional_float_is_type_array(self):
        result = _resolve_type(Optional[float])
        self.assertEqual(result, {'type': ['number', 'null']})

    def test_optional_bool_is_type_array(self):
        result = _resolve_type(Optional[bool])
        self.assertEqual(result, {'type': ['boolean', 'null']})

    def test_union_two_primitives_is_type_array(self):
        result = _resolve_type(Union[int, str])
        self.assertIn('type', result)
        self.assertIsInstance(result['type'], list)
        self.assertCountEqual(result['type'], ['integer', 'string'])

    def test_union_three_primitives_is_type_array(self):
        result = _resolve_type(Union[int, str, float])
        self.assertIsInstance(result['type'], list)
        self.assertEqual(len(result['type']), 3)

    def test_union_with_list_falls_back_to_anyof(self):
        result = _resolve_type(Union[List[str], int])
        self.assertIn('anyOf', result)
        self.assertNotIn('type', result)

    def test_optional_list_falls_back_to_anyof(self):
        result = _resolve_type(Optional[List[str]])
        self.assertIn('anyOf', result)

    def test_no_anyof_for_all_primitive_optional(self):
        result = _resolve_type(Optional[int])
        self.assertNotIn('anyOf', result)

    def test_no_anyof_for_primitive_union(self):
        result = _resolve_type(Union[int, str])
        self.assertNotIn('anyOf', result)

    def test_optional_string_enum_falls_back_to_anyof(self):
        for enum_type in (StringMode, LegacyStringMode):
            with self.subTest(enum_type=enum_type.__name__):
                result = _resolve_type(Optional[enum_type])
                self.assertIn('anyOf', result)


# ---------------------------------------------------------------------------
# 3. PEP 604  X | Y  syntax (Python 3.10+)
# ---------------------------------------------------------------------------


@unittest.skipUnless(sys.version_info >= (3, 10), 'PEP 604 requires Python 3.10+')
class TestPEP604UnionSyntax(unittest.TestCase):
    def test_is_union_detects_pipe(self):
        tp = eval('int | str')
        self.assertTrue(_is_union(tp))

    def test_is_union_still_detects_typing_union(self):
        self.assertTrue(_is_union(Union[int, str]))

    def test_is_union_false_for_plain_type(self):
        self.assertFalse(_is_union(int))

    def test_pipe_optional_is_type_array(self):
        tp = eval('int | None')
        result = _resolve_type(tp)
        self.assertIsInstance(result['type'], list)
        self.assertCountEqual(result['type'], ['integer', 'null'])

    def test_pipe_union_two_primitives_is_type_array(self):
        tp = eval('int | str')
        result = _resolve_type(tp)
        self.assertIsInstance(result['type'], list)
        self.assertCountEqual(result['type'], ['integer', 'string'])

    def test_pipe_union_three_primitives(self):
        tp = eval('int | str | float')
        result = _resolve_type(tp)
        self.assertEqual(len(result['type']), 3)

    def test_pipe_optional_none_first(self):
        tp = eval('None | str')
        result = _resolve_type(tp)
        self.assertCountEqual(result['type'], ['null', 'string'])

    def test_pipe_optional_with_list_falls_back_to_anyof(self):
        tp = eval('list[str] | None')
        result = _resolve_type(tp)
        self.assertIn('anyOf', result)

    def test_pipe_optional_in_generate_schema_not_required(self):
        def f(x, y) -> None:
            """Summary.
            Args:
                x: An int or None.
                y: A required string.
            """

        f.__annotations__['x'] = eval('int | None')
        f.__annotations__['y'] = str
        f.__annotations__['return'] = type(None)
        schema = generate_tool_schema(f)
        self.assertNotIn('x', _required(schema))
        self.assertIn('y', _required(schema))

    def test_pipe_optional_inner_type_in_schema(self):
        # generate_tool_schema strips None from Optional unions before resolving,
        # so int | None yields {"type": "integer"} in the emitted schema.
        def f(x, y) -> None:
            """Summary.
            Args:
                x: An int or None.
                y: A string.
            """

        f.__annotations__['x'] = eval('int | None')
        f.__annotations__['y'] = str
        f.__annotations__['return'] = type(None)
        schema = generate_tool_schema(f)
        x_schema = _props(schema)['x']
        self.assertEqual(x_schema['type'], 'integer')

    def test_pipe_union_non_optional_in_schema(self):
        def f(val) -> None:
            """Summary.
            Args:
                val: An int or string.
            """

        f.__annotations__['val'] = eval('int | str')
        f.__annotations__['return'] = type(None)
        schema = generate_tool_schema(f)
        val_schema = _props(schema)['val']
        self.assertIsInstance(val_schema['type'], list)
        self.assertCountEqual(val_schema['type'], ['integer', 'string'])


# ---------------------------------------------------------------------------
# 4. _parse_google_docstring
# ---------------------------------------------------------------------------


class TestParseGoogleDocstring(unittest.TestCase):
    def test_basic(self):
        doc = """
        One-line summary.
        Args:
            x: Description of x.
            y: Description of y.
        """
        summary, params = _parse_google_docstring(doc)
        self.assertEqual(summary, 'One-line summary.')
        self.assertEqual(params['x'], 'Description of x.')
        self.assertEqual(params['y'], 'Description of y.')

    def test_multiline_description(self):
        doc = """
        Summary here.
        Args:
            alpha: First line.
                Second line.
                Third line.
            beta: Short.
        """
        _, params = _parse_google_docstring(doc)
        self.assertIn('First line', params['alpha'])
        self.assertIn('Second line', params['alpha'])
        self.assertIn('Third line', params['alpha'])
        self.assertEqual(params['beta'], 'Short.')

    def test_multiline_whitespace_normalised(self):
        doc = """
        Summary.
        Args:
            x: Line one.
                Line two.
                Line three.
        """
        _, params = _parse_google_docstring(doc)
        self.assertEqual(params['x'], 'Line one. Line two. Line three.')

    def test_returns_excluded_from_summary(self):
        doc = """
        Do the thing.
        Args:
            x: Some value.
        Returns:
            The result.
        """
        summary, _ = _parse_google_docstring(doc)
        self.assertNotIn('result', summary.lower())

    def test_empty_args_section(self):
        doc = 'No-arg function summary.'
        summary, params = _parse_google_docstring(doc)
        self.assertEqual(summary, 'No-arg function summary.')
        self.assertEqual(params, {})

    def test_alias_arguments(self):
        doc = 'Summary.\nArguments:\n    x: Desc.\n'
        _, params = _parse_google_docstring(doc)
        self.assertIn('x', params)

    def test_alias_parameters(self):
        doc = 'Summary.\nParameters:\n    x: Desc.\n'
        _, params = _parse_google_docstring(doc)
        self.assertIn('x', params)

    def test_multiple_sections_only_args_parsed(self):
        doc = """
        Summary.
        Args:
            x: Desc.
        Returns:
            Something.
        Raises:
            ValueError: If bad.
        """
        _, params = _parse_google_docstring(doc)
        self.assertEqual(list(params.keys()), ['x'])


# ---------------------------------------------------------------------------
# 5. _parse_interface_type — TypedDict and dataclass
# ---------------------------------------------------------------------------


class TestParseInterfaceType(unittest.TestCase):
    # TypedDict

    def test_typeddict_is_object(self):
        self.assertEqual(_parse_interface_type(SimpleTypedDict)['type'], 'object')

    def test_typeddict_required_fields(self):
        schema = _parse_interface_type(SimpleTypedDict)
        self.assertIn('name', schema['required'])
        self.assertIn('age', schema['required'])

    def test_typeddict_not_required_absent(self):
        schema = _parse_interface_type(SimpleTypedDict)
        self.assertNotIn('nickname', schema['required'])

    def test_typeddict_field_types(self):
        props = _parse_interface_type(SimpleTypedDict)['properties']
        self.assertEqual(props['name']['type'], 'string')
        self.assertEqual(props['age']['type'], 'integer')
        self.assertEqual(props['nickname']['type'], 'string')

    def test_typeddict_field_descriptions(self):
        props = _parse_interface_type(SimpleTypedDict)['properties']
        self.assertEqual(props['name']['description'], 'The name field.')
        self.assertEqual(props['age']['description'], 'The age field.')
        self.assertEqual(props['nickname']['description'], 'An optional nickname.')

    # dataclass

    def test_dataclass_is_object(self):
        self.assertEqual(_parse_interface_type(SimpleDataclass)['type'], 'object')

    def test_dataclass_required_fields(self):
        schema = _parse_interface_type(SimpleDataclass)
        self.assertIn('x', schema['required'])
        self.assertIn('y', schema['required'])

    def test_dataclass_optional_not_required(self):
        schema = _parse_interface_type(SimpleDataclass)
        self.assertNotIn('label', schema.get('required', []))

    def test_dataclass_optional_is_type_array(self):
        label = _parse_interface_type(SimpleDataclass)['properties']['label']
        self.assertIsInstance(label['type'], list)
        self.assertCountEqual(label['type'], ['string', 'null'])

    def test_dataclass_field_descriptions(self):
        props = _parse_interface_type(SimpleDataclass)['properties']
        self.assertEqual(props['x']['description'], 'X coordinate.')
        self.assertEqual(props['y']['description'], 'Y coordinate.')

    def test_dataclass_class_docstring(self):
        schema = _parse_interface_type(SimpleDataclass)
        self.assertIn('description', schema)
        self.assertIn('point', schema['description'].lower())

    def test_non_interface_raises(self):
        with self.assertRaises(TypeError):
            _parse_interface_type(int)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 6. generate_tool_schema — happy-path / schema structure
# ---------------------------------------------------------------------------


class TestGenerateToolSchemaHappyPath(unittest.TestCase):
    # Top-level keys

    def test_has_name(self):
        self.assertEqual(generate_tool_schema(basic_func)['name'], 'basic_func')

    def test_has_description(self):
        self.assertEqual(
            generate_tool_schema(basic_func)['description'],
            'This is a docstring for the foo function.',
        )

    def test_has_parameters_not_input_schema(self):
        schema = generate_tool_schema(basic_func)
        self.assertIn('parameters', schema)
        self.assertNotIn('input_schema', schema)

    def test_parameters_type_is_object(self):
        self.assertEqual(generate_tool_schema(basic_func)['parameters']['type'], 'object')

    # Required / optional

    def test_all_required_when_no_defaults(self):
        self.assertCountEqual(_required(generate_tool_schema(basic_func)), ['alpha', 'bar'])

    def test_default_value_removes_from_required(self):
        schema = generate_tool_schema(search_func)
        self.assertIn('query', _required(schema))
        self.assertNotIn('max_results', _required(schema))
        self.assertNotIn('tags', _required(schema))

    def test_optional_annotation_removes_from_required(self):
        def f(x: Optional[int]) -> None:
            """Summary.\nArgs:\n    x: An optional int.\n"""

        schema = generate_tool_schema(f)
        self.assertNotIn('x', _required(schema))

    def test_all_optional_produces_no_required_key(self):
        def f(x: Optional[int] = None) -> None:
            """Summary.\nArgs:\n    x: Optional.\n"""

        schema = generate_tool_schema(f)
        self.assertNotIn('required', schema['parameters'])

    # Primitive types

    def test_int_param(self):
        self.assertEqual(_props(generate_tool_schema(basic_func))['alpha']['type'], 'integer')

    def test_str_param(self):
        self.assertEqual(_props(generate_tool_schema(basic_func))['bar']['type'], 'string')

    def test_list_param(self):
        tags = _props(generate_tool_schema(search_func))['tags']
        self.assertEqual(tags['type'], 'array')
        self.assertEqual(tags['items']['type'], 'string')

    # Optional represented as type array

    def test_optional_param_schema_is_inner_type(self):
        # generate_tool_schema strips None from Optional, routing through inner_tp,
        # so Optional[str] emits {"type": "string"} — nullability is encoded by
        # absence from the required list, not in the type schema.
        def f(x: Optional[str]) -> None:
            """Summary.\nArgs:\n    x: An optional string.\n"""

        x_schema = _props(generate_tool_schema(f))['x']
        self.assertEqual(x_schema['type'], 'string')
        self.assertNotIn('anyOf', x_schema)

    # Descriptions

    def test_param_description(self):
        self.assertEqual(
            _props(generate_tool_schema(basic_func))['bar']['description'],
            'This is the bar parameter, which is a string.',
        )

    def test_multiline_description_joined(self):
        desc = _props(generate_tool_schema(basic_func))['alpha']['description']
        self.assertIn('This is the alpha parameter', desc)
        self.assertIn('Then there is this extended description', desc)
        self.assertIn('Also this here', desc)
        self.assertNotIn('\n', desc)

    def test_summary_excludes_returns(self):
        self.assertNotIn('List of matching', generate_tool_schema(search_func)['description'])

    def test_summary_excludes_args_content(self):
        self.assertNotIn('search query string', generate_tool_schema(search_func)['description'])

    # Various type forms

    def test_literal_param(self):
        def f(mode: Literal['fast', 'slow']) -> None:
            """Run.\nArgs:\n    mode: The mode.\n"""

        mode = _props(generate_tool_schema(f))['mode']
        self.assertEqual(mode['type'], 'string')
        self.assertCountEqual(mode['enum'], ['fast', 'slow'])

    def test_dict_param(self):
        def f(meta: Dict[str, str]) -> None:
            """Store.\nArgs:\n    meta: Key-value pairs.\n"""

        meta = _props(generate_tool_schema(f))['meta']
        self.assertEqual(meta['type'], 'object')
        self.assertEqual(meta['additionalProperties']['type'], 'string')

    def test_union_param_type_array(self):
        def f(value: Union[int, str]) -> None:
            """Process.\nArgs:\n    value: Int or string.\n"""

        val = _props(generate_tool_schema(f))['value']
        self.assertIsInstance(val['type'], list)
        self.assertCountEqual(val['type'], ['integer', 'string'])

    def test_string_enum_param(self):
        for enum_type in (StringMode, LegacyStringMode):
            with self.subTest(enum_type=enum_type.__name__):

                def f(mode) -> None:
                    """Run.\nArgs:\n    mode: Processing mode.\n"""

                f.__annotations__['mode'] = enum_type
                f.__annotations__['return'] = type(None)
                mode = _props(generate_tool_schema(f))['mode']
                self.assertEqual(mode['type'], 'string')
                self.assertCountEqual(mode['enum'], ['fast', 'safe'])

    def test_optional_string_enum_param_schema_is_inner_enum(self):
        for enum_type in (StringMode, LegacyStringMode):
            with self.subTest(enum_type=enum_type.__name__):

                def f(mode=None) -> None:
                    """Run.\nArgs:\n    mode: Optional mode.\n"""

                f.__annotations__['mode'] = Optional[enum_type]
                f.__annotations__['return'] = type(None)
                schema = generate_tool_schema(f)
                mode = _props(schema)['mode']
                self.assertEqual(mode['type'], 'string')
                self.assertCountEqual(mode['enum'], ['fast', 'safe'])
                self.assertNotIn('mode', _required(schema))

    def test_complex_union_anyof(self):
        def f(value: Union[List[str], int]) -> None:
            """Process.\nArgs:\n    value: List or int.\n"""

        val = _props(generate_tool_schema(f))['value']
        self.assertIn('anyOf', val)

    # No-arg function

    def test_no_args(self):
        def ping() -> str:
            """Return pong."""
            return 'pong'

        schema = generate_tool_schema(ping)
        self.assertEqual(_props(schema), {})
        self.assertEqual(_required(schema), [])

    # TypedDict param

    def test_typeddict_param_is_object(self):
        self.assertEqual(_props(generate_tool_schema(update_user_func))['profile']['type'], 'object')

    def test_typeddict_param_required_fields(self):
        inner = _props(generate_tool_schema(update_user_func))['profile']
        self.assertIn('name', inner['required'])
        self.assertNotIn('email', inner['required'])

    def test_typeddict_field_types(self):
        props = _props(generate_tool_schema(update_user_func))['profile']['properties']
        self.assertEqual(props['name']['type'], 'string')
        self.assertEqual(props['age']['type'], 'integer')

    def test_typeddict_field_descriptions(self):
        props = _props(generate_tool_schema(update_user_func))['profile']['properties']
        self.assertEqual(props['name']['description'], "The user's full name.")
        self.assertEqual(props['email']['description'], 'Optional email address.')

    # dataclass param

    def test_dataclass_param_is_object(self):
        self.assertEqual(_props(generate_tool_schema(plot_point_func))['point']['type'], 'object')

    def test_dataclass_required_fields(self):
        inner = _props(generate_tool_schema(plot_point_func))['point']
        self.assertIn('x', inner['required'])
        self.assertNotIn('label', inner.get('required', []))

    def test_dataclass_optional_field_is_type_array(self):
        label = _props(generate_tool_schema(plot_point_func))['point']['properties']['label']
        self.assertIsInstance(label['type'], list)
        self.assertCountEqual(label['type'], ['string', 'null'])


# ---------------------------------------------------------------------------
# 7. generate_tool_schema — validation / error paths
# ---------------------------------------------------------------------------


class TestGenerateToolSchemaValidation(unittest.TestCase):
    def test_missing_annotation_raises_type_error(self):
        def f(x, y: str) -> None:
            """Doc.\nArgs:\n    x: desc\n    y: desc\n"""

        with self.assertRaises(TypeError) as ctx:
            generate_tool_schema(f)
        self.assertIn('x', str(ctx.exception))
        self.assertIn('missing a type annotation', str(ctx.exception))

    def test_missing_annotation_names_function(self):
        def my_func(bad_param) -> None:
            """Doc.\nArgs:\n    bad_param: desc\n"""

        with self.assertRaises(TypeError) as ctx:
            generate_tool_schema(my_func)
        self.assertIn('my_func', str(ctx.exception))

    def test_positional_only_raises_value_error(self):
        g: dict = {}
        exec(
            'def f(x: int, /, y: str) -> None:\n    """Doc.\n    Args:\n        y: desc\n    """\n',
            g,
        )
        with self.assertRaises(ValueError) as ctx:
            generate_tool_schema(g['f'])
        self.assertIn('positional-only', str(ctx.exception))

    def test_missing_doc_param_raises_value_error(self):
        def f(a: int, b: str) -> None:
            """Doc.\nArgs:\n    a: desc\n"""

        with self.assertRaises(ValueError) as ctx:
            generate_tool_schema(f)
        self.assertIn('b', str(ctx.exception))

    def test_missing_doc_param_lists_all(self):
        def f(a: int, b: str, c: float) -> None:
            """Doc.\nArgs:\n    a: desc\n"""

        with self.assertRaises(ValueError) as ctx:
            generate_tool_schema(f)
        msg = str(ctx.exception)
        self.assertIn('b', msg)
        self.assertIn('c', msg)

    def test_unknown_doc_param_raises_value_error(self):
        def f(a: int) -> None:
            """Doc.\nArgs:\n    a: desc\n    ghost: nope\n"""

        with self.assertRaises(ValueError) as ctx:
            generate_tool_schema(f)
        self.assertIn('ghost', str(ctx.exception))

    def test_missing_return_type_raises_type_error(self):
        def f(a: int):
            """Doc.\nArgs:\n    a: desc\n"""

        with self.assertRaises(TypeError) as ctx:
            generate_tool_schema(f)
        self.assertIn('return type', str(ctx.exception).lower())

    def test_missing_return_type_names_function(self):
        def uniquely_named(a: int):
            """Doc.\nArgs:\n    a: desc\n"""

        with self.assertRaises(TypeError) as ctx:
            generate_tool_schema(uniquely_named)
        self.assertIn('uniquely_named', str(ctx.exception))

    def test_unsupported_param_type_raises(self):
        def f(a: set) -> None:
            """Doc.\nArgs:\n    a: desc\n"""

        with self.assertRaises(TypeError) as ctx:
            generate_tool_schema(f)
        self.assertIn('JSON Schema', str(ctx.exception))

    def test_unsupported_return_type_raises(self):
        def f(a: int) -> set:
            """Doc.\nArgs:\n    a: desc\n"""
            return set()

        with self.assertRaises(TypeError) as ctx:
            generate_tool_schema(f)
        self.assertIn('Return type', str(ctx.exception))

    def test_no_docstring_raises(self):
        def f(a: int) -> None:
            pass

        with self.assertRaises(ValueError) as ctx:
            generate_tool_schema(f)
        self.assertIn('no docstring', str(ctx.exception).lower())

    def test_no_args_section_when_params_present(self):
        def f(a: int) -> None:
            """Just a summary."""

        with self.assertRaises(ValueError):
            generate_tool_schema(f)

    def test_error_includes_param_name(self):
        def f(secret_param) -> None:
            """Doc.\nArgs:\n    secret_param: desc\n"""

        with self.assertRaises(TypeError) as ctx:
            generate_tool_schema(f)
        self.assertIn('secret_param', str(ctx.exception))

    def test_error_includes_function_name(self):
        def uniquely_named_function(x) -> None:
            """Doc.\nArgs:\n    x: desc\n"""

        with self.assertRaises(TypeError) as ctx:
            generate_tool_schema(uniquely_named_function)
        self.assertIn('uniquely_named_function', str(ctx.exception))


# ---------------------------------------------------------------------------
# 8. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases(unittest.TestCase):
    def test_bool_param(self):
        def f(flag: bool) -> None:
            """Summary.\nArgs:\n    flag: A flag.\n"""

        self.assertEqual(_props(generate_tool_schema(f))['flag']['type'], 'boolean')

    def test_float_param(self):
        def f(value: float) -> None:
            """Summary.\nArgs:\n    value: A float.\n"""

        self.assertEqual(_props(generate_tool_schema(f))['value']['type'], 'number')

    def test_nested_optional_list_inner_type_is_array(self):
        # generate_tool_schema strips None and resolves List[str] directly,
        # so Optional[List[str]] emits {"type": "array"} not anyOf.
        def f(items: Optional[List[str]] = None) -> None:
            """Summary.\nArgs:\n    items: Optional list.\n"""

        schema = generate_tool_schema(f)
        items_schema = _props(schema)['items']
        self.assertEqual(items_schema['type'], 'array')
        self.assertEqual(items_schema['items']['type'], 'string')

    def test_default_value_removes_from_required(self):
        def f(x: int = 42) -> None:
            """Summary.\nArgs:\n    x: An int with default.\n"""

        self.assertNotIn('x', _required(generate_tool_schema(f)))

    def test_name_matches_function_name(self):
        def very_specific_name(x: int) -> None:
            """Summary.\nArgs:\n    x: desc.\n"""

        self.assertEqual(generate_tool_schema(very_specific_name)['name'], 'very_specific_name')

    def test_typeddict_all_required(self):
        class AllRequired(TypedDict):
            a: int
            """Field a."""
            b: str
            """Field b."""

        def f(data: AllRequired) -> None:
            """Summary.\nArgs:\n    data: The data.\n"""

        f.__annotations__['data'] = AllRequired
        f.__annotations__['return'] = type(None)
        inner = _props(generate_tool_schema(f))['data']
        self.assertCountEqual(inner['required'], ['a', 'b'])

    def test_typeddict_total_false_no_required(self):
        class AllOptional(TypedDict, total=False):
            a: int
            """Field a."""
            b: str
            """Field b."""

        def f(data: AllOptional) -> None:
            """Summary.\nArgs:\n    data: The data.\n"""

        f.__annotations__['data'] = AllOptional
        f.__annotations__['return'] = type(None)
        inner = _props(generate_tool_schema(f))['data']
        self.assertNotIn('required', inner)

    def test_dataclass_all_required(self):
        @dataclasses.dataclass
        class Rect:
            """Rectangle."""

            width: float
            """Width."""
            height: float
            """Height."""

        def f(r: Rect) -> None:
            """Draw.\nArgs:\n    r: The rect.\n"""

        f.__annotations__['r'] = Rect
        f.__annotations__['return'] = type(None)
        inner = _props(generate_tool_schema(f))['r']
        self.assertCountEqual(inner['required'], ['width', 'height'])

    def test_literal_single_value(self):
        def f(x: Literal['only']) -> None:
            """Summary.\nArgs:\n    x: Only option.\n"""

        self.assertEqual(_props(generate_tool_schema(f))['x']['enum'], ['only'])

    def test_multi_word_summary(self):
        def f(x: int) -> None:
            """This is a multi-word summary that spans many words.\nArgs:\n    x: desc.\n"""

        self.assertIn('multi-word summary', generate_tool_schema(f)['description'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
