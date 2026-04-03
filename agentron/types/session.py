from typing import TypedDict
from agentron.types.model import Model


class SessionMetadata(TypedDict, total=False):
    title: str
    description: str
    model: Model
    # Current working directory
    cwd: str
    # Creation timestamp [milliseconds since epoch]
    created: int
