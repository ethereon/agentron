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
        self._metadata: SessionMetadata | None = None

    @property
    def metadata(self) -> SessionMetadata:
        if self._metadata is None:
            self._metadata = self._process_metadata(self.header['metadata'])
        return self._metadata

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

    def resolve_subagent(self, session_id: str) -> SessionSource | None:
        subagent_path = self.path.parent / session_id / 'session.jsonl'
        if subagent_path.exists():
            return SerializedSessionSource(subagent_path)
        return None

    def _process_metadata(self, metadata: SessionMetadata) -> SessionMetadata:
        if metadata.get('created') is None:
            # If created timestamp is missing,
            # use the file's creation time as a fallback.
            stat = self.path.stat()
            try:
                metadata['created'] = int(stat.st_birthtime * 1000)
            except AttributeError:
                # st_birthtime may not be available on all platforms.
                metadata['created'] = int(stat.st_ctime * 1000)
        return metadata
