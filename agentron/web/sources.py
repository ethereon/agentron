from pathlib import Path

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
        self._messages: list[AgentMessage] | None = None
        self._header: SessionHeader | None = None

    @property
    def metadata(self) -> SessionMetadata:
        return self.header['metadata']

    @property
    def session_id(self) -> str:
        return self.header['session_id']

    @property
    def messages(self) -> list[AgentMessage]:
        if self._messages is None:
            data = read_session_data(self.path)
            self._messages = data.messages
            self._header = data.header
        return self._messages

    @property
    def header(self) -> SessionHeader:
        if self._header is None:
            self._header = read_session_data(self.path, header_only=True).header
        return self._header
