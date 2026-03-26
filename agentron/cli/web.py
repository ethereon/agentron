from typing import Iterable
from pathlib import Path
from agentron.web import serve


def run_web_ui(sources: Iterable[Path]):
    with serve(*sources) as server:
        num_sessions = len(server._sessions)
        suffix = '' if num_sessions == 1 else 's'
        print(f'Loaded {num_sessions} session{suffix}.')
