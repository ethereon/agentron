from typing import Iterable
from pathlib import Path

from agentron.web.server import serve, SessionSource
from agentron.web.sources import SerializedSessionSource


def run_web_ui(paths: Iterable[Path]) -> int:
    sources = _resolve_sources(paths)
    if not sources:
        print('No session sources found. Please provide paths to session files or directories containing session files.')
        return 1

    print(f'Discovered {len(sources)} session source(s).')
    with serve(*sources):
        return 0


def _resolve_sources(paths: Iterable[Path]) -> list[SessionSource]:
    session_paths: list[Path] = []
    for path in paths:
        if path.is_dir():
            session_paths.extend(_scan_dir_for_sessions(path))
        elif path.is_file():
            session_paths.append(path)

    return [SerializedSessionSource(path) for path in session_paths]


def _scan_dir_for_sessions(dir_path: Path) -> list[Path]:
    session_files: list[Path] = []
    for file in dir_path.iterdir():
        if file.is_dir():
            # Hierarchical layout: <session_dir>/session.jsonl
            main_session_path = file / 'session.jsonl'
            if main_session_path.is_file():
                session_files.append(main_session_path)
        elif file.suffix == '.jsonl':
            # Flat layout: <session_dir>.jsonl
            session_files.append(file)
    return session_files
