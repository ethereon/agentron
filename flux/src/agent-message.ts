// Auto-generated file. Do not edit directly.

export const enum MessageType {
    SYSTEM = 'system',
    USER = 'user',
    ASSISTANT = 'assistant',
    TOOL_RESULT = 'tool_result'
}

export interface BaseMessage {
    id: string;
    timestamp: number;
}

export const enum ContentType {
    TEXT = 'text'
}

export interface TextContent {
    type: ContentType.TEXT;
    text: string;
    text_signature?: string;
}

export type Content = TextContent;

export const enum AssistantContentType {
    REASONING = 'reasoning',
    TOOL_CALL = 'tool_call'
}

export interface Reasoning {
    type: AssistantContentType.REASONING;
    text: string;
    signature?: string;
    redacted?: boolean;
}

export interface ToolCall {
    type: AssistantContentType.TOOL_CALL;
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

export const enum FinishReason {
    STOP = 'stop',
    LENGTH = 'length',
    TOOL_USE = 'tool_use',
    ERROR = 'error',
    ABORTED = 'aborted'
}

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
    mtype: MessageType.USER;
    content: Content;
}

export interface SystemMessage {
    id: string;
    timestamp: number;
    mtype: MessageType.SYSTEM;
    content: Content;
}

export interface AssistantMessage {
    id: string;
    timestamp: number;
    mtype: MessageType.ASSISTANT;
    content: AssistantContent[];
    model: ModelInfo;
    token_usage: TokenUsage;
    finish_reason?: FinishReason;
    error?: AssistantMessageError;
}

export interface ToolResult {
    success: boolean;
    content?: Content;
    error?: string;
}

export interface ToolResultMessage {
    id: string;
    timestamp: number;
    mtype: MessageType.TOOL_RESULT;
    call_id: string;
    tool_name: string;
    result: ToolResult;
}

export type AgentMessage = UserMessage | SystemMessage | AssistantMessage | ToolResultMessage;

export const enum StreamingMessageType {
    TEXT_START = 'text_start',
    TEXT_DELTA = 'text_delta',
    TEXT_END = 'text_end',
    REASONING_START = 'reasoning_start',
    REASONING_DELTA = 'reasoning_delta',
    REASONING_END = 'reasoning_end'
}

export interface StreamingMessage {
    session_id: string;
    type: StreamingMessageType;
    partial: AssistantMessage;
    delta?: string;
    content_index: number;
}
