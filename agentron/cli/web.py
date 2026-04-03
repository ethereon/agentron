from typing import Iterable
from pathlib import Path

from agentron.web.server import serve, SessionSource
from agentron.web.sources import SerializedSessionSource


def run_web_ui(paths: Iterable[Path]):
    sources = _resolve_sources(paths)
    print(f'Discovered {len(sources)} session source(s).')
    with serve(*sources):
        pass


def _resolve_sources(paths: Iterable[Path]) -> list[SessionSource]:
    session_paths: list[Path] = []
    for path in paths:
        if path.is_dir():
            for file in path.iterdir():
                if file.is_file() and file.suffix == '.jsonl':
                    session_paths.append(file)
        elif path.is_file():
            session_paths.append(path)

    return [SerializedSessionSource(path) for path in session_paths]
