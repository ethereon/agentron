// Auto-generated file. Do not edit directly.

import type { AgentMessage } from './messages.js';
import type { Model, ModelReasoningLevel } from './model.js';
import type { ToolSchema } from './tool-schema.js';

export interface OAuthLoginData {
    type: 'oauth';
    provider: string;
    credentials: Record<string, unknown>;
}

export type ApiKeySource = string | OAuthLoginData;

export type NotificationKind = 'streaming_message';

export type RequestKind = 'session_start' | 'transmit';

export interface SessionStartRequest {
    session_id: string;
    model: Model;
    tools: ToolSchema[];
    api_key?: ApiKeySource | null;
}

export interface TransmitRequest {
    session_id: string;
    messages: AgentMessage[];
    reasoning: ModelReasoningLevel | null;
}
