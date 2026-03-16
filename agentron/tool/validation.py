from typing import Any

from agentron.typing import ToolSchema


class ToolError(RuntimeError): ...


def _value_type_name(value: Any) -> str:
    match value:
        case None:
            return 'null'
        case bool():
            return 'boolean'
        case int():
            return 'integer'
        case float():
            return 'number'
        case str():
            return 'string'
        case list():
            return 'array'
        case dict():
            return 'object'
        case _:
            return type(value).__name__


def _format_path(path: str) -> str:
    return f'"{path}"' if path else 'the arguments object'


def _child_path(path: str, key: Any) -> str:
    return f'{path}.{key}' if path else str(key)


def _format_enum_values(values: list[Any]) -> str:
    return ', '.join(repr(value) for value in values)


def _schema_description(schema: dict[str, Any]) -> str:
    match schema:
        case {'enum': enum_values}:
            return f'one of {_format_enum_values(enum_values)}'
        case {'anyOf': options}:
            return ' or '.join(_schema_description(option) for option in options)
        case {'type': list() as schema_types}:
            return ' or '.join(schema_types)
        case {'type': str() as schema_type}:
            return schema_type
        case _:
            return 'a valid value'


def _matches_json_type(value: Any, schema_type: str) -> bool:
    match schema_type:
        case 'null':
            return value is None
        case 'boolean':
            return isinstance(value, bool)
        case 'integer':
            return isinstance(value, int) and not isinstance(value, bool)
        case 'number':
            return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
        case 'string':
            return isinstance(value, str)
        case 'array':
            return isinstance(value, list)
        case 'object':
            return isinstance(value, dict)
        case _:
            return False


def _collect_schema_issues(value: Any, schema: dict[str, Any], path: str, issues: list[str]) -> None:
    match schema:
        case {'anyOf': options}:
            for option in options:
                option_issues: list[str] = []
                _collect_schema_issues(value, option, path, option_issues)
                if not option_issues:
                    return
            issues.append(f'{_format_path(path)} must be {_schema_description(schema)}; got {_value_type_name(value)}.')
            return

    schema_type = schema.get('type')
    match schema_type:
        case list() as schema_types:
            if not any(_matches_json_type(value, option) for option in schema_types):
                issues.append(f'{_format_path(path)} must be {_schema_description(schema)}; got {_value_type_name(value)}.')
                return
        case str() as expected_type:
            if not _matches_json_type(value, expected_type):
                issues.append(f'{_format_path(path)} must be {_schema_description(schema)}; got {_value_type_name(value)}.')
                return

    if 'enum' in schema and value not in schema['enum']:
        issues.append(f'{_format_path(path)} must be one of {_format_enum_values(schema["enum"])}; got {value!r}.')
        return

    match schema_type:
        case 'array':
            item_schema = schema.get('items')
            if item_schema:
                for index, item in enumerate(value):
                    _collect_schema_issues(item, item_schema, f'{path}[{index}]', issues)
            return
        case 'object':
            properties = schema.get('properties')
            required = schema.get('required', [])
            additional_properties = schema.get('additionalProperties')

            for required_key in required:
                if required_key not in value:
                    required_path = f'{path}.{required_key}' if path else required_key
                    issues.append(f'Missing required argument {_format_path(required_path)}.')

            if properties is not None:
                for key in value:
                    if key not in properties:
                        if additional_properties is None:
                            unexpected_path = _child_path(path, key)
                            issues.append(f'Unexpected argument {_format_path(unexpected_path)}.')
                            continue
                        if not isinstance(key, str):
                            issues.append(f'{_format_path(path)} must use string keys; got key {key!r}.')
                            continue
                        _collect_schema_issues(value[key], additional_properties, _child_path(path, key), issues)

                for key, property_schema in properties.items():
                    if key in value:
                        child_path = _child_path(path, key)
                        _collect_schema_issues(value[key], property_schema, child_path, issues)
                return

            if additional_properties is not None:
                for key, child_value in value.items():
                    if not isinstance(key, str):
                        issues.append(f'{_format_path(path)} must use string keys; got key {key!r}.')
                        continue
                    child_path = _child_path(path, key)
                    _collect_schema_issues(child_value, additional_properties, child_path, issues)
            return


def validate_tool_arguments(
    schema: ToolSchema,
    arguments: Any,
) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ToolError(f'Invalid arguments for tool "{schema["name"]}": the arguments object must be an object; got {_value_type_name(arguments)}.')

    issues: list[str] = []
    _collect_schema_issues(arguments, schema['parameters'], '', issues)
    if issues:
        raise ToolError(f'Invalid arguments for tool "{schema["name"]}": ' + ' '.join(issues))

    return arguments
