// Auto-generated file. Do not edit directly.

export type MessageType = 'system' | 'user' | 'assistant' | 'tool_result';

export interface BaseMessage {
    id: string;
    timestamp: number;
}

export type ContentType = 'text';

export interface TextContent {
    type: 'text';
    text: string;
    text_signature?: string;
}

export type Content = TextContent;

export type AssistantContentType = 'reasoning' | 'tool_call';

export interface Reasoning {
    type: 'reasoning';
    text: string;
    signature?: string;
    redacted?: boolean;
}

export interface ToolCall {
    type: 'tool_call';
    id: string;
    name: string;
    arguments: Record<string, unknown>;
    thought_signature?: string;
}

export type AssistantContent = TextContent | Reasoning | ToolCall;

export interface AssistantMessageError {
    message: string;
}

export interface ModelInfo {
    api: string;
    provider: string;
    model: string;
}

export type FinishReason = 'stop' | 'length' | 'tool_use' | 'error' | 'aborted';

export interface TokenUsageCost {
    input: number;
    output: number;
    cache_read: number;
    cache_write: number;
    total: number;
}

export interface TokenUsage {
    input: number;
    output: number;
    cache_read: number;
    cache_write: number;
    total: number;
    cost: TokenUsageCost;
}

export interface UserMessage {
    id: string;
    timestamp: number;
    mtype: 'user';
    content: Content;
}

export interface SystemMessage {
    id: string;
    timestamp: number;
    mtype: 'system';
    content: Content;
}

export interface AssistantMessage {
    id: string;
    timestamp: number;
    mtype: 'assistant';
    content: AssistantContent[];
    model: ModelInfo;
    token_usage: TokenUsage;
    finish_reason?: FinishReason;
    error?: AssistantMessageError;
}

export interface ToolResult {
    success: boolean;
    content: Content;
    subagent_ids?: string[];
}

export interface ToolResultMessage {
    id: string;
    timestamp: number;
    mtype: 'tool_result';
    call_id: string;
    tool_name: string;
    result: ToolResult;
}

export type AgentMessage = UserMessage | SystemMessage | AssistantMessage | ToolResultMessage;

export type StreamingMessageType =
    | 'text_start'
    | 'text_delta'
    | 'text_end'
    | 'reasoning_start'
    | 'reasoning_delta'
    | 'reasoning_end';

export interface StreamingMessage {
    session_id: string;
    type: StreamingMessageType;
    partial: AssistantMessage;
    delta?: string;
    content_index: number;
}
