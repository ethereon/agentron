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
    # Subagents set this to their parent session ID
    parent_session_id: str
    # Subagents set this to the tool call name that triggered their creation
    invoking_tool_call: str
