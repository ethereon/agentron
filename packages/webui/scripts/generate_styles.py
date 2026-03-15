from argparse import ArgumentParser

from pathlib import Path

from mayo.evaluator import evaluate
from mayo.codegen import TypeScriptCodeGenerator, generate_css, sort_source_units
from mayo.module import FileModuleResolver

import os
import shutil

PROJECT_ROOT = Path(__file__).parent.parent
TYPESCRIPT_SRC_DIR = PROJECT_ROOT / 'src'
TYPESCRIPT_STYLES_OUTPUT_DIR = TYPESCRIPT_SRC_DIR / 'gen' / 'styles'

CSS_INTERNAL_PREFIX = 'at_'
CSS_OUTPUT_PATH = PROJECT_ROOT / 'dist' / 'app.css'


class HyperTypeScriptCodeGenerator(TypeScriptCodeGenerator):
    def transform_name(self, name: str) -> str:
        name = super().transform_name(name)
        if name.startswith(CSS_INTERNAL_PREFIX):
            name = name.removeprefix(CSS_INTERNAL_PREFIX)
        return name


class HyperModuleResolver(FileModuleResolver):
    SEARCH_ROOTS = [TYPESCRIPT_SRC_DIR]

    def resolve_path(self, module: str) -> Path | None:
        for search_root in self.SEARCH_ROOTS:
            base = search_root / module.replace('.', os.path.sep).replace('_', '-')
            candidates = (base.with_suffix('.sass'), base / 'style.sass')
            for candidate in candidates:
                if candidate.exists():
                    return candidate
        return None


def get_output_path(source_path: Path, scoped_output_dir: Path) -> Path:
    source_stem = source_path.stem
    assert source_stem != 'index'
    if source_stem == 'style':
        # <parent_name>/style.sass --> <output_root>/<parent_name>.ts
        return scoped_output_dir.parent / f'{source_path.parent.stem}.ts'
    # <parent_name>/<name>.sass --> <output_dir>/<parent_name>/<name>.ts
    return scoped_output_dir / f'{source_stem}.ts'


def generate():
    style_sources = sorted(TYPESCRIPT_SRC_DIR.glob('**/*.sass'))
    ts_generator = HyperTypeScriptCodeGenerator()
    resolver = HyperModuleResolver()
    resolver.activate()

    ts_output_dir = TYPESCRIPT_STYLES_OUTPUT_DIR
    # Re-create output directory
    if ts_output_dir.exists():
        shutil.rmtree(ts_output_dir)
    ts_output_dir.mkdir(parents=True)

    source_units = []

    for src_path in style_sources:
        print(f'* \033[92m{src_path}\033[0m')
        # Parse
        src_unit = evaluate(path=src_path)
        resolver.cache_module_by_path(path=src_path, module=src_unit)
        source_units.append(src_unit)

        # Emit typescript
        ts_source = ts_generator(src_unit)
        ts_output = ts_source.encode('utf-8')
        if ts_output:
            scoped_output_dir = ts_output_dir / src_path.relative_to(TYPESCRIPT_SRC_DIR).parent
            ts_output_path = get_output_path(src_path, scoped_output_dir)
            ts_output_path.parent.mkdir(exist_ok=True, parents=True)
            print(f'\t{ts_output_path}')
            with ts_output_path.open('wb') as ts_file:
                ts_file.write(ts_output)

    # Emit CSS
    sort_source_units(sources=source_units)
    css_lines = []
    for src_unit in source_units:
        css_output = generate_css(src_unit.rules)
        if css_output:
            css_lines.append(css_output)

    CSS_OUTPUT_PATH.parent.mkdir(exist_ok=True, parents=True)
    CSS_OUTPUT_PATH.write_text('\n'.join(css_lines))


def watch():
    from watchdog.observers import Observer
    from watchdog.events import PatternMatchingEventHandler
    from threading import Timer

    class SourceChangeEventHandler(PatternMatchingEventHandler):
        def __init__(self, debounce_interval=0.2):
            super().__init__(patterns=['*.sass'])
            self.execution_count = 0
            self.is_execution_scheduled = False
            self.debounce_interval = debounce_interval

        def on_any_event(self, event):
            if not self.is_execution_scheduled:
                self.is_execution_scheduled = True
                (Timer(self.debounce_interval, self.regenerate).start())

        def regenerate(self):
            self.is_execution_scheduled = False
            print(chr(27) + '[2J')  # Clear the screen
            generate()
            self.execution_count += 1
            print(f'Style regeneration count: {self.execution_count}')

    observer = Observer()
    observer.schedule(
        event_handler=SourceChangeEventHandler(),
        path=str(TYPESCRIPT_SRC_DIR),
        recursive=True,
    )
    observer.start()
    try:
        observer.join()
    except KeyboardInterrupt:
        print('\nEnding watch.')


def main():
    parser = ArgumentParser(__doc__)
    parser.add_argument(
        '--watch',
        default=False,
        action='store_true',
        help='Monitor for style changes and auto-regenerate.',
    )
    args = parser.parse_args()

    # Unconditionally generate once (even for watch)
    generate()

    if args.watch:
        print('Style generator is now monitoring changes.')
        watch()


if __name__ == '__main__':
    main()
