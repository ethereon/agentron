from pathlib import Path
from functools import cache

from agentron.serialization import read_session_data, SessionHeader
from agentron.types.session import SessionMetadata
from agentron.types.message import AgentMessage
from agentron.web.server import SessionSource


class SerializedSessionSource(SessionSource):
    """
    Source for an existing serialized session.
    """

    def __init__(self, path: Path):
        self.path = path

    @property
    def metadata(self) -> SessionMetadata:
        return self._header['metadata']

    @property
    def session_id(self) -> str:
        return self._header['session_id']

    @property
    @cache
    def messages(self) -> list[AgentMessage]:
        return read_session_data(self.path).messages

    @property
    @cache
    def _header(self) -> SessionHeader:
        return read_session_data(self.path, header_only=True).header
