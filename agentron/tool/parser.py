from __future__ import annotations

import dataclasses
import enum
import functools
import inspect
import re
import textwrap
import types
import typing

from typing import Any, Callable, get_type_hints
from agentron.types.core import ToolSchema

# Mapping from Python built-in / typing types to JSON Schema type strings
_PRIMITIVE_MAP: dict[Any, str] = {
    int: 'integer',
    float: 'number',
    str: 'string',
    bool: 'boolean',
    type(None): 'null',
}


def _is_typeddict(tp: Any) -> bool:
    return isinstance(tp, type) and issubclass(tp, dict) and hasattr(tp, '__annotations__') and hasattr(tp, '__required_keys__')


def _is_dataclass(tp: Any) -> bool:
    return dataclasses.is_dataclass(tp) and isinstance(tp, type)


def _is_string_enum(tp: Any) -> bool:
    return isinstance(tp, type) and issubclass(tp, enum.Enum) and all(isinstance(member.value, str) for member in tp)


def _get_origin(tp: Any) -> Any:
    return getattr(tp, '__origin__', None)


def _get_args(tp: Any) -> tuple:
    return getattr(tp, '__args__', ()) or ()


def _is_union(tp: Any) -> bool:
    """Return True for both typing.Union and PEP 604 X | Y (types.UnionType, 3.10+)."""
    if _get_origin(tp) is typing.Union:
        return True
    if hasattr(types, 'UnionType') and isinstance(tp, types.UnionType):
        return True
    return False


def _is_optional(tp: Any) -> 'tuple[bool, Any]':
    """
    Return (is_optional, inner_type).
    Handles Optional[X], Union[X, None], and X | None (PEP 604).
    """
    if not _is_union(tp):
        return False, tp
    args = _get_args(tp)
    non_none = [a for a in args if a is not type(None)]
    if len(args) - len(non_none) >= 1:  # at least one None in the union
        inner = non_none[0] if len(non_none) == 1 else typing.Union[tuple(non_none)]
        return True, inner
    return False, tp


def _all_primitive_schemas(schemas: list) -> bool:
    """Return True when every schema is a plain {"type": "<scalar>"}."""
    return all(list(s.keys()) == ['type'] and isinstance(s['type'], str) for s in schemas)


def _resolve_union(args: tuple) -> dict:
    """
    Resolve a union of types to the most compact OpenAI-compatible form.

    - All-primitive union  ->  {"type": ["t1", "t2", ...]}
    - Mixed / complex      ->  {"anyOf": [{...}, {...}]}
    """
    member_schemas = [_resolve_type(a) for a in args]
    if _all_primitive_schemas(member_schemas):
        type_names = [s['type'] for s in member_schemas]
        return {'type': type_names} if len(type_names) > 1 else {'type': type_names[0]}
    return {'anyOf': member_schemas}


def _resolve_type(tp: Any) -> dict:
    """Recursively resolve a Python type annotation to a JSON Schema dict."""
    # Unwrap Required / NotRequired wrappers (TypedDict)
    if _get_origin(tp) is typing.Required or (hasattr(typing, 'NotRequired') and _get_origin(tp) is getattr(typing, 'NotRequired')):
        return _resolve_type(_get_args(tp)[0])

    # NoneType
    if tp is type(None):
        return {'type': 'null'}

    # Primitives
    if tp in _PRIMITIVE_MAP:
        return {'type': _PRIMITIVE_MAP[tp]}

    # StringEnum / StrEnum
    if _is_string_enum(tp):
        return {'type': 'string', 'enum': [member.value for member in tp]}

    origin = _get_origin(tp)
    args = _get_args(tp)

    # Union / Optional - checked before List/Dict so Optional[List[X]] works
    if _is_union(tp):
        return _resolve_union(args)

    # List[X]
    if origin is list or tp is list:
        schema: dict = {'type': 'array'}
        if args:
            schema['items'] = _resolve_type(args[0])
        return schema

    # Dict[K, V]
    if origin is dict or tp is dict:
        schema = {'type': 'object'}
        if len(args) == 2:
            schema['additionalProperties'] = _resolve_type(args[1])
        return schema

    # Literal
    if origin is typing.Literal:
        enum_vals = list(args)
        types_seen = {type(v) for v in enum_vals}
        if types_seen <= {str}:
            return {'type': 'string', 'enum': enum_vals}
        if types_seen <= {int}:
            return {'type': 'integer', 'enum': enum_vals}
        return {'enum': enum_vals}

    # TypedDict / dataclass -- nested object schema
    if _is_typeddict(tp) or _is_dataclass(tp):
        return _parse_interface_type(tp)

    raise TypeError(
        f"Type '{tp}' cannot be represented in JSON Schema. Supported types: int, float, str, bool, None, list[X], dict[str, X], Optional[X], X | Y, Literal[...], StringEnum, TypedDict, dataclass."
    )


def _callable_name(obj: Callable) -> str:
    """Return a human-friendly name for any callable."""
    if isinstance(obj, functools.partial):
        return _callable_name(obj.func)

    # Functions, methods, builtins, classes
    if hasattr(obj, '__name__'):
        return obj.__name__

    # Callable instances
    if hasattr(obj, '__call__'):
        name = obj.__class__.__name__
        # Convert to snake_case if it's CamelCase
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        snake = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        return snake

    raise ValueError(f'Failed to get a name for tool function: {obj}')


def _unwrap_partial(func: Callable) -> tuple[Callable, tuple[Any, ...], dict[str, Any]]:
    """Return the wrapped callable plus all arguments bound by nested partials."""
    partial_args: list[Any] = []
    partial_kwargs: dict[str, Any] = {}

    while isinstance(func, functools.partial):
        partial_args = [*func.args, *partial_args]
        partial_kwargs = {**(func.keywords or {}), **partial_kwargs}
        func = func.func

    return func, tuple(partial_args), partial_kwargs


def _normalize_tool_callable(func: Callable) -> tuple[str, Callable, inspect.Signature, set[str]]:
    """Normalize plain callables, callable instances, and partials for schema generation."""
    wrapped_func, partial_args, partial_kwargs = _unwrap_partial(func)
    func_name = _callable_name(wrapped_func)

    target = wrapped_func
    if (not inspect.isfunction(target)) and hasattr(target, '__call__'):
        target = target.__call__

    full_sig = inspect.signature(target)
    if partial_args or partial_kwargs:
        try:
            bound = full_sig.bind_partial(*partial_args, **partial_kwargs)
        except TypeError as exc:
            raise ValueError(f"Function '{func_name}' has an invalid partial binding: {exc}") from exc
        fixed_params = set(bound.arguments.keys())
    else:
        fixed_params = set()

    remaining_params = [param for name, param in full_sig.parameters.items() if name not in fixed_params]
    return func_name, target, full_sig.replace(parameters=remaining_params), set(full_sig.parameters.keys())


# ---------------------------------------------------------------------------
# TypedDict / dataclass field-doc parsing
# ---------------------------------------------------------------------------


def _get_field_docs(tp: type) -> dict[str, str]:
    """
    Extract per-field docstrings from a TypedDict or dataclass body.

    Convention:
        class Foo(TypedDict):
            x: int
            \"\"\"Description for x\"\"\"
    """
    try:
        src = inspect.getsource(tp)
        src = textwrap.dedent(src)
    except (OSError, TypeError):
        return {}

    field_docs: dict[str, str] = {}
    lines = src.splitlines()

    # A field annotation: optional leading spaces, identifier, colon, then a
    # type expression (NOT a pure docstring line).
    # We distinguish it from e.g. `class Foo(TypedDict):` by requiring the line
    # NOT to start with 'class ' / 'def '.
    ann_re = re.compile(r'^(\s{0,8})(\w+)\s*:')
    triple_re = re.compile(r'^\s*"""')

    i = 0
    while i < len(lines):
        line = lines[i]
        # Skip class/def/decorator lines
        stripped = line.strip()
        if stripped.startswith(('class ', 'def ', '@', '#')):
            i += 1
            continue

        m = ann_re.match(line)
        if m:
            field_name = m.group(2)
            # Skip dunder / class-level names we don't care about
            if field_name in ('__annotations__', '__doc__', '__module__', '__qualname__'):
                i += 1
                continue

            # Look ahead for the docstring (skip blank lines)
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1

            if j < len(lines) and triple_re.match(lines[j]):
                # Collect the triple-quoted block
                doc_lines: list[str] = []
                raw = lines[j].strip()

                # Single-line triple-quoted string: """..."""
                if raw.startswith('"""') and raw.endswith('"""') and len(raw) > 6:
                    doc_lines.append(raw[3:-3])
                    i = j + 1
                else:
                    # Multi-line: starts with """ and ends on a later line
                    first_content = raw[3:].strip()
                    if first_content:
                        doc_lines.append(first_content)
                    k = j + 1
                    while k < len(lines):
                        seg = lines[k].strip()
                        if '"""' in seg:
                            closing = seg.replace('"""', '').strip()
                            if closing:
                                doc_lines.append(closing)
                            i = k + 1
                            break
                        doc_lines.append(seg)
                        k += 1
                    else:
                        i = k

                field_docs[field_name] = ' '.join(doc_lines).strip()
                continue  # i already advanced inside the block

        i += 1

    return field_docs


def _parse_interface_type(tp: type) -> dict:
    """Build a JSON Schema object schema for a TypedDict or dataclass."""
    if _is_typeddict(tp):
        hints = get_type_hints(tp, include_extras=True)
        required_keys: frozenset = tp.__required_keys__  # type: ignore[attr-defined]
    elif _is_dataclass(tp):
        hints = get_type_hints(tp, include_extras=True)
        required_keys = frozenset(
            f.name
            for f in dataclasses.fields(tp)
            if (
                f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING  # type: ignore[misc]
            )
        )
    else:
        raise TypeError(f'{tp} is not a TypedDict or dataclass.')

    field_docs = _get_field_docs(tp)
    properties: dict = {}
    required: list = []

    for field_name, field_type in hints.items():
        # Detect NotRequired wrapper
        not_required = False
        if hasattr(typing, 'NotRequired') and _get_origin(field_type) is getattr(typing, 'NotRequired'):
            not_required = True
            field_type = _get_args(field_type)[0]
        elif hasattr(typing, 'Required') and _get_origin(field_type) is getattr(typing, 'Required'):
            field_type = _get_args(field_type)[0]

        prop_schema = _resolve_type(field_type)
        if field_name in field_docs:
            prop_schema['description'] = field_docs[field_name]

        properties[field_name] = prop_schema
        if (field_name in required_keys) and not not_required:
            required.append(field_name)

    schema: dict = {'type': 'object', 'properties': properties}
    if required:
        schema['required'] = required
    if tp.__doc__ and tp.__doc__.strip() != tp.__name__:
        schema['description'] = tp.__doc__.strip()
    return schema


# ---------------------------------------------------------------------------
# Docstring parsing
# ---------------------------------------------------------------------------


def _format_description_lines(lines: list[str], section_re: re.Pattern[str]) -> str:
    """Normalize non-Args docstring content into a readable description."""
    cleaned: list[str] = []
    previous_blank = False

    for line in lines:
        stripped = line.rstrip()
        if not stripped.strip():
            if cleaned and not previous_blank:
                cleaned.append('')
                previous_blank = True
            continue

        cleaned.append(stripped)
        previous_blank = False

    while cleaned and cleaned[-1] == '':
        cleaned.pop()

    blocks: list[str] = []
    i = 0
    while i < len(cleaned):
        if cleaned[i] == '':
            i += 1
            continue

        if section_re.match(cleaned[i]):
            section_lines = [cleaned[i]]
            i += 1
            while i < len(cleaned) and cleaned[i] != '' and not section_re.match(cleaned[i]):
                section_lines.append(cleaned[i])
                i += 1
            blocks.append('\n'.join(section_lines))
            continue

        paragraph_lines = [cleaned[i].strip()]
        i += 1
        while i < len(cleaned) and cleaned[i] != '' and not section_re.match(cleaned[i]):
            paragraph_lines.append(cleaned[i].strip())
            i += 1
        blocks.append(' '.join(line for line in paragraph_lines if line))

    return '\n\n'.join(blocks)


def _parse_google_docstring(doc: str) -> tuple[str, dict[str, str]]:
    """
    Parse a Google-style docstring.

    Returns:
        (description, {param_name: description})
    """
    doc = textwrap.dedent(doc).strip()
    lines = doc.splitlines()

    # Google-style section headers: word(s) followed by a colon at indent 0
    section_re = re.compile(r'^(\w[\w\s]*)\s*:\s*$')
    args_section_names = {'args', 'arguments', 'parameters'}

    def ensure_description_break() -> None:
        if description_lines and description_lines[-1] != '':
            description_lines.append('')

    # ---- Split into description content and args block ----
    description_lines: list[str] = []
    args_lines: list[str] = []
    in_args = False

    for line in lines:
        m = section_re.match(line)
        if m:
            was_in_args = in_args
            section_name = m.group(1).strip().lower()
            in_args = section_name in args_section_names
            if not in_args:
                if was_in_args:
                    ensure_description_break()
                description_lines.append(line.rstrip())
            continue

        if in_args:
            if line.strip() and line == line.lstrip():
                in_args = False
                ensure_description_break()
                description_lines.append(line.rstrip())
                continue
            args_lines.append(line)
            continue

        description_lines.append(line.rstrip())

    description = _format_description_lines(description_lines, section_re)

    # ---- Parse the args block ----
    param_descriptions: dict[str, str] = {}
    param_re = re.compile(r'^(\s{2,8})(\w+)\s*:\s*(.*)')
    current_param: str | None = None
    current_desc_lines: list[str] = []
    base_indent: int = 0

    def flush() -> None:
        if current_param is not None:
            param_descriptions[current_param] = ' '.join(current_desc_lines).strip()

    for line in args_lines:
        if not line.strip():
            continue
        m = param_re.match(line)
        if m:
            flush()
            base_indent = len(m.group(1))
            current_param = m.group(2)
            current_desc_lines = [m.group(3)] if m.group(3).strip() else []
        else:
            indent = len(line) - len(line.lstrip())
            if current_param is not None and indent > base_indent:
                current_desc_lines.append(line.strip())

    flush()
    return description, param_descriptions


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------


def generate_tool_schema(func: Callable) -> ToolSchema:
    """
    Generate an OpenAI-style tool-call JSON schema for *func*.

    If *func* is a functools.partial instance, the wrapped callable provides the
    schema name, docstring, and type hints, and any bound arguments are removed
    from the emitted parameter schema.

    Output format:
        {
            "name": "func_name",
            "description": "...",
            "parameters": {
                "type": "object",
                "properties": { ... },
                "required": [ ... ]
            }
        }

    Optional / union types use the JSON Schema type-array form for
    all-primitive unions, e.g. Optional[int] -> {"type": ["integer", "null"]},
    and anyOf for complex unions containing non-primitive members.

    Raises:
        TypeError  -- type annotation issues or unsupported types
        ValueError -- docstring / argument consistency issues
    """
    func_name, func, sig, all_param_names = _normalize_tool_callable(func)
    params = sig.parameters

    # --- Collect type hints (resolves forward references) ---
    try:
        hints = get_type_hints(func)
    except Exception as exc:
        raise TypeError(f"Could not resolve type hints for '{func_name}': {exc}") from exc

    # --- Return type required ---
    if 'return' not in hints:
        raise TypeError(f"Function '{func_name}' is missing a return type annotation.")

    # --- No positional-only parameters ---
    for name, param in params.items():
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            raise ValueError(f"Function '{func_name}' has a positional-only parameter '{name}'. Positional-only parameters (before '/' in the signature) are not supported.")

    # --- Every parameter must have a type annotation ---
    for name in params:
        if name not in hints:
            raise TypeError(f"Parameter '{name}' of '{func_name}' is missing a type annotation.")

    # --- Parse docstring ---
    raw_doc = inspect.getdoc(func) or ''
    if not raw_doc:
        raise ValueError(f"Function '{func_name}' has no docstring.")

    summary, param_docs = _parse_google_docstring(raw_doc)

    # --- Validate docstring <-> signature consistency ---
    sig_params = set(params.keys())
    doc_params = set(param_docs.keys())

    missing_in_doc = sig_params - doc_params
    if missing_in_doc:
        raise ValueError(f"Function '{func_name}': the following parameters are not described in the docstring 'Args:' section: {sorted(missing_in_doc)}")

    unknown_in_doc = doc_params - all_param_names
    if unknown_in_doc:
        raise ValueError(f"Function '{func_name}': the docstring 'Args:' section references unknown parameters: {sorted(unknown_in_doc)}")

    # --- Build properties ---
    properties: dict = {}
    required: list = []

    for name, param in params.items():
        tp = hints[name]

        # Detect optional from annotation
        is_opt, inner_tp = _is_optional(tp)

        # Detect optional from default value
        if param.default is not inspect.Parameter.empty:
            is_opt = True

        try:
            if is_opt:
                prop_schema = _resolve_type(inner_tp)
            else:
                prop_schema = _resolve_type(tp)
                required.append(name)
        except TypeError as exc:
            raise TypeError(f"Parameter '{name}' of '{func_name}': {exc}") from exc

        prop_schema['description'] = param_docs[name]
        properties[name] = prop_schema

    # --- Validate return type (just ensure it resolves) ---
    try:
        _resolve_type(hints['return'])
    except TypeError as exc:
        raise TypeError(f"Return type of '{func_name}': {exc}") from exc

    parameters: dict = {'type': 'object', 'properties': properties}
    if required:
        parameters['required'] = required

    return {
        'name': func_name,
        'description': summary,
        'parameters': parameters,
    }
