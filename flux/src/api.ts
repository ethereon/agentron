// Auto-generated file. Do not edit directly.

import type { AgentMessage } from './agent-message.js';
import type { ToolSchema } from './tool-schema.js';
import type { Model, ModelReasoningLevel } from './model.js';

export const enum NotificationKind {
    STREAMING_MESSAGE = 'streaming_message'
}

export const enum RequestKind {
    SESSION_START = 'session_start',
    TRANSMIT = 'transmit'
}

export interface SessionStartRequest {
    session_id: string;
    model: Model;
    tools: ToolSchema[];
    api_key?: string | null;
}

export interface TransmitRequest {
    session_id: string;
    messages: AgentMessage[];
    reasoning?: ModelReasoningLevel;
}
