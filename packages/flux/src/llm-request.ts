import type { AgentMessage, StreamingMessage } from './types/messages.js';
import type { ToolSchema } from './tool-schema.js';
import type { ModelReasoningLevel } from './types/model.js';

export interface ToolSet {
    tools: ToolSchema[];
    backendState?: Record<string, unknown>;
}

export interface LLMRequest {
    // The messages to send to the LLM.
    messages: Iterable<AgentMessage>;

    // Callback invoked with streaming updates from the LLM.
    onStreamingMessage(message: StreamingMessage): void;

    // Available tools for this request.
    tools: ToolSet;

    abortSignal: AbortSignal;

    sessionId: string;

    // If omitted, a default value of MEDIUM is assumed (if the model supports reasoning levels).
    reasoning?: ModelReasoningLevel;
}
