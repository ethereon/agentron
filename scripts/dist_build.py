from __future__ import annotations

import argparse
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build a wheel into dist/.')
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
        wheel_out_dir = Path(temp_dir) / 'wheels'

        stage_source_tree(staging_root)
        remove_transient_files(staging_root)

        wheels = build_wheel(staging_root, wheel_out_dir)

        DIST_DIR.mkdir(parents=True, exist_ok=True)
        copy_wheels_to_dist(wheels)

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
