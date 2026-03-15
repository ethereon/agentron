import type { AgentMessage, StreamingMessage } from '@ethereon/flux/agent-message';

export interface NewMessageEvent {
    type: 'new_message';
    data: AgentMessage;
}

export interface StreamingMessageEvent {
    type: 'streaming_message';
    data: StreamingMessage;
}

export type StreamingEvent = NewMessageEvent | StreamingMessageEvent;
