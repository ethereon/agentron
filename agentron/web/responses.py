from agentron.types.session import SessionMetadata
from agentron.types.message import AgentMessage

type SessionId = str


type SessionsResponse = dict[SessionId, SessionMetadata]

type MessagesResponse = list[AgentMessage]
