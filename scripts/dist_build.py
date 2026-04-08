from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / 'dist'


@dataclass(frozen=True)
class BuildStep:
    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class CopyRule:
    source: Path
    destination: Path


BUILD_STEPS: tuple[BuildStep, ...] = (
    BuildStep(
        name='Build Flux bundle',
        command=('node', 'packages/flux/scripts/bundle.js'),
    ),
    BuildStep(
        name='Build Web UI bundle',
        command=('node', 'packages/webui/scripts/build.mjs'),
    ),
)


COPY_RULES: tuple[CopyRule, ...] = (
    CopyRule(
        source=PROJECT_ROOT / 'agentron',
        destination=Path('agentron'),
    ),
    CopyRule(
        source=PROJECT_ROOT / 'pyproject.toml',
        destination=Path('pyproject.toml'),
    ),
    CopyRule(
        source=PROJECT_ROOT / 'README.md',
        destination=Path('README.md'),
    ),
    CopyRule(
        source=PROJECT_ROOT / 'packages' / 'flux' / 'dist' / 'bundle',
        destination=Path('agentron/dist/flux'),
    ),
    CopyRule(
        source=PROJECT_ROOT / 'packages' / 'webui' / 'dist' / 'bundle',
        destination=Path('agentron/dist/webui'),
    ),
)


VERSION_PATTERN = re.compile(r'(?m)^version = "([^"]+)"$')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build debug and production wheels into dist/.')
    parser.add_argument(
        '--dirty',
        action='store_true',
        help='Allow building from a dirty source tree.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.dirty:
        ensure_clean_worktree()

    clobber_dist_dir()
    run_build_steps()

    with tempfile.TemporaryDirectory(prefix='agentron-dist-build-') as temp_dir:
        staging_root = Path(temp_dir) / 'staging'
        debug_out_dir = Path(temp_dir) / 'wheels' / 'debug'
        production_out_dir = Path(temp_dir) / 'wheels' / 'production'

        stage_source_tree(staging_root)
        remove_transient_files(staging_root)

        pyproject_path = staging_root / 'pyproject.toml'
        original_version = get_project_version(pyproject_path)
        debug_version = make_debug_version(original_version)

        # Build debug wheel (with source maps)
        set_project_version(pyproject_path, debug_version)
        debug_wheels = build_wheel(staging_root, debug_out_dir)

        # Build production wheel
        clean_wheel_build_artifacts(staging_root)
        set_project_version(pyproject_path, original_version)
        remove_source_maps(staging_root)
        remove_transient_files(staging_root)
        production_wheels = build_wheel(staging_root, production_out_dir)

        DIST_DIR.mkdir(parents=True, exist_ok=True)
        copy_wheels_to_dist(debug_wheels + production_wheels)

    print(f'Built {len(list(DIST_DIR.glob("*.whl")))} wheel(s) into {DIST_DIR}')
    return 0


def ensure_clean_worktree() -> None:
    result = subprocess.run(
        ['git', 'status', '--porcelain'],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    if result.stdout.strip():
        raise SystemExit('Source tree is dirty. Re-run with --dirty to override.')


def clobber_dist_dir() -> None:
    if DIST_DIR.exists():
        print(f'Removing existing dist directory: {DIST_DIR}')
        shutil.rmtree(DIST_DIR)


def run_build_steps() -> None:
    for step in BUILD_STEPS:
        print(f'==> {step.name}')
        subprocess.run(step.command, cwd=PROJECT_ROOT, check=True)


def stage_source_tree(staging_root: Path) -> None:
    for rule in COPY_RULES:
        destination = staging_root / rule.destination
        copy_path(rule.source, destination)

    staged_package_dist = staging_root / 'agentron' / 'dist'
    if staged_package_dist.exists():
        shutil.rmtree(staged_package_dist)

    for rule in COPY_RULES:
        if rule.destination.parts[:2] == ('agentron', 'dist'):
            destination = staging_root / rule.destination
            copy_path(rule.source, destination)


def copy_path(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f'Missing required build input: {source}')

    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
        return

    shutil.copy2(source, destination)


def remove_transient_files(root: Path) -> None:
    globs = ('.DS_Store', '*.pyc', '__pycache__')
    for pattern in globs:
        for path in root.rglob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def clean_wheel_build_artifacts(root: Path) -> None:
    paths_to_remove = [root / 'build']
    paths_to_remove.extend(root.glob('*.egg-info'))

    removed = 0
    for path in paths_to_remove:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed += 1

    print(f'Removed {removed} wheel build artifact path(s) before production build')


def remove_source_maps(root: Path) -> None:
    removed = 0
    for path in root.rglob('*.js.map'):
        path.unlink()
        removed += 1
    print(f'Removed {removed} source map file(s) before production build')


def get_project_version(pyproject_path: Path) -> str:
    content = pyproject_path.read_text(encoding='utf-8')
    match = VERSION_PATTERN.search(content)
    if match is None:
        raise ValueError(f'Unable to locate version in {pyproject_path}')
    return match.group(1)


def set_project_version(pyproject_path: Path, version: str) -> None:
    content = pyproject_path.read_text(encoding='utf-8')
    updated_content, replacements = VERSION_PATTERN.subn(f'version = "{version}"', content, count=1)
    if replacements != 1:
        raise ValueError(f'Unable to update version in {pyproject_path}')
    pyproject_path.write_text(updated_content, encoding='utf-8')


def make_debug_version(version: str) -> str:
    if '+' in version:
        return f'{version}.debug'
    return f'{version}+debug'


def build_wheel(source_dir: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = set(output_dir.glob('*.whl'))

    subprocess.run(
        [
            sys.executable,
            '-m',
            'pip',
            'wheel',
            '--no-deps',
            '--wheel-dir',
            str(output_dir),
            str(source_dir),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )

    built_wheels = sorted(set(output_dir.glob('*.whl')) - existing)
    if not built_wheels:
        raise RuntimeError(f'Wheel build produced no artifacts in {output_dir}')
    return built_wheels


def copy_wheels_to_dist(wheels: list[Path]) -> None:
    for wheel in wheels:
        destination = DIST_DIR / wheel.name
        shutil.copy2(wheel, destination)
        print(f'Copied {wheel.name} -> {destination}')


if __name__ == '__main__':
    sys.exit(main())
