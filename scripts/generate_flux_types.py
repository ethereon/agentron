"""
Auto-generates TypeScript type declarations from the Python reference.
"""

from __future__ import annotations

import importlib
import types
import sys
import subprocess
import collections.abc

from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import Any, ForwardRef, Literal, NotRequired, TypeAliasType, Union, get_args, get_origin, get_type_hints


PROJECT_ROOT = Path(__file__).parent.parent
FLUX_ROOT = PROJECT_ROOT / 'packages' / 'flux'

PREAMBLE = '// Auto-generated file. Do not edit directly.\n\n'


def is_typed_dict_class(obj: Any) -> bool:
    return isinstance(obj, type) and issubclass(obj, dict) and hasattr(obj, '__required_keys__') and hasattr(obj, '__optional_keys__')


def to_ts_literal(value: Any) -> str:
    if isinstance(value, StrEnum):
        return f"'{value.value}'"
    if isinstance(value, str):
        escaped = value.replace('\\', '\\\\').replace("'", "\\'")
        return f"'{escaped}'"
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if value is None:
        return 'null'
    return str(value)


def maybe_parenthesize_union(type_name: str) -> str:
    if ' | ' in type_name:
        return f'({type_name})'
    return type_name


def to_ts_type(annotation: Any) -> str:
    if annotation is Any:
        return 'unknown'
    if annotation is str:
        return 'string'
    if annotation in (int, float):
        return 'number'
    if annotation is bool:
        return 'boolean'
    if annotation is type(None):
        return 'null'

    if isinstance(annotation, TypeAliasType):
        return annotation.__name__

    if isinstance(annotation, ForwardRef):
        return annotation.__forward_arg__

    if isinstance(annotation, type):
        if issubclass(annotation, StrEnum):
            return annotation.__name__
        if is_typed_dict_class(annotation):
            return annotation.__name__
        return annotation.__name__

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is NotRequired:
        return to_ts_type(args[0])

    if origin is Literal:
        return ' | '.join(to_ts_literal(value) for value in args)

    if origin in (list, collections.abc.Sequence):
        inner = to_ts_type(args[0]) if args else 'unknown'
        return f'{maybe_parenthesize_union(inner)}[]'

    if origin in (dict,):
        key_type = to_ts_type(args[0]) if args else 'string'
        value_type = to_ts_type(args[1]) if len(args) > 1 else 'unknown'
        if key_type == 'string':
            return f'Record<string, {value_type}>'
        if key_type == 'number':
            return f'Record<number, {value_type}>'
        return f'Record<{key_type}, {value_type}>'

    if origin in (Union, types.UnionType):
        return ' | '.join(to_ts_type(arg) for arg in args)

    if isinstance(annotation, str):
        return annotation

    return str(annotation)


def render_enum(name: str, enum_cls: type[StrEnum]) -> str:
    union = ' | '.join(f"'{member.value}'" for member in enum_cls)
    return f'export type {name} = {union};'


def render_interface(name: str, cls: type, globalns: dict[str, Any]) -> str:
    bases = [base.__name__ for base in cls.__bases__ if is_typed_dict_class(base)]
    extends_clause = f' extends {", ".join(bases)}' if bases else ''
    lines = [f'export interface {name}{extends_clause} {{']

    hints = get_type_hints(cls, globalns=globalns, localns=globalns, include_extras=True)
    optional_keys = getattr(cls, '__optional_keys__', set())

    for field_name, annotation in hints.items():
        origin = get_origin(annotation)
        is_optional = field_name in optional_keys
        if origin is NotRequired:
            annotation = get_args(annotation)[0]
            is_optional = True

        ts_type = to_ts_type(annotation)
        optional_suffix = '?' if is_optional else ''
        lines.append(f'    {field_name}{optional_suffix}: {ts_type};')

    lines.append('}')
    return '\n'.join(lines)


def render_alias(name: str, alias: TypeAliasType) -> str:
    return f'export type {name} = {to_ts_type(alias.__value__)};'


def collect_declarations(module: ModuleType) -> tuple[list[str], dict[str, str]]:
    ordered_names: list[str] = []
    declarations: dict[str, str] = {}
    globalns = vars(module)

    for name, value in globalns.items():
        if name.startswith('_'):
            continue

        if isinstance(value, type) and getattr(value, '__module__', None) == module.__name__:
            if is_typed_dict_class(value):
                declarations[name] = render_interface(name, value, globalns)
                ordered_names.append(name)
                continue

            if issubclass(value, StrEnum):
                declarations[name] = render_enum(name, value)
                ordered_names.append(name)
                continue

        if isinstance(value, TypeAliasType) and getattr(value, '__module__', None) == module.__name__:
            declarations[name] = render_alias(name, value)
            ordered_names.append(name)

    return ordered_names, declarations


def generate_typescript(module_path: str, imports: dict[str, str] | None = None) -> str:
    module = importlib.import_module(module_path)
    ordered_names, declarations = collect_declarations(module)
    code = '\n\n'.join(declarations[name] for name in ordered_names) + '\n'

    if imports:
        import_sources = {}
        for name, source in imports.items():
            import_sources.setdefault(source, []).append(name)

        import_lines = []
        for source, names in import_sources.items():
            names_list = ', '.join(names)
            import_lines.append(f"import type {{ {names_list} }} from './{source}';")

        code = '\n'.join(import_lines) + '\n\n' + code

    return PREAMBLE + code


def format_code(path: Path) -> None:
    subprocess.run(
        [
            'npx',
            'prettier',
            '--write',
            str(path),
        ],
        text=True,
        check=True,
        cwd=FLUX_ROOT,
    )


def maybe_generate_validation():
    valinor = PROJECT_ROOT.parent / 'valinor' / 'dist' / 'valinor.js'
    if not valinor.exists():
        print('Valinor not found. Skipping validation generation.')
        return
    subprocess.run(
        [
            'node',
            valinor,
            '--tsconfig',
            str(FLUX_ROOT / 'tsconfig.json'),
            '--root',
            str(FLUX_ROOT / 'src'),
        ],
        check=True,
    )


def main() -> None:
    sys.path.append(str(PROJECT_ROOT))
    flux_src = FLUX_ROOT / 'src'
    translation_table = {
        'agentron.types.message': flux_src / 'agent-message.ts',
        'agentron.types.model': flux_src / 'model.ts',
        'agentron.rpc.api': flux_src / 'api.ts',
    }
    imports = {
        'agentron.rpc.api': {
            'AgentMessage': 'agent-message.js',
            'ToolSchema': 'tool-schema.js',
            'Model': 'model.js',
            'ModelReasoningLevel': 'model.js',
        }
    }

    for module_path, output_file in translation_table.items():
        ts = generate_typescript(module_path, imports=imports.get(module_path))
        output_file.write_text(ts, encoding='utf-8')
        format_code(output_file)

    maybe_generate_validation()


if __name__ == '__main__':
    main()
