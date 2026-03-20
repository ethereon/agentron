import type { AgentMessage } from './agent-message.js';

// --- AUTO-GENERATED CODE BELOW --- //

function isTextContent(obj: any): boolean {
    return (
        obj != null &&
        obj.type === 'text' &&
        typeof obj.text === 'string' &&
        (obj.text_signature == null || typeof obj.text_signature === 'string')
    );
}

function isUserMessage(obj: any): boolean {
    return (
        obj != null &&
        obj.mtype === 'user' &&
        typeof obj.id === 'string' &&
        typeof obj.timestamp === 'number' &&
        isTextContent(obj.content)
    );
}

function isSystemMessage(obj: any): boolean {
    return (
        obj != null &&
        obj.mtype === 'system' &&
        typeof obj.id === 'string' &&
        typeof obj.timestamp === 'number' &&
        isTextContent(obj.content)
    );
}

function isReasoning(obj: any): boolean {
    return (
        obj != null &&
        obj.type === 'reasoning' &&
        typeof obj.text === 'string' &&
        (obj.signature == null || typeof obj.signature === 'string') &&
        (typeof obj.redacted === 'boolean' || obj.redacted == null)
    );
}

function isToolCall(obj: any): boolean {
    return (
        obj != null &&
        obj.type === 'tool_call' &&
        typeof obj.id === 'string' &&
        typeof obj.name === 'string' &&
        obj.arguments != null &&
        typeof obj.arguments === 'object' &&
        !Array.isArray(obj.arguments) &&
        Object.values(obj.arguments).every((value: any) => value != null) &&
        (obj.thought_signature == null || typeof obj.thought_signature === 'string')
    );
}

function is__some__AssistantContent(obj: any): boolean {
    switch (obj.type) {
        case 'text':
            return isTextContent(obj);
        case 'reasoning':
            return isReasoning(obj);
        case 'tool_call':
            return isToolCall(obj);
        default:
            return false;
    }
}

function isModelInfo(obj: any): boolean {
    return (
        obj != null &&
        typeof obj.api === 'string' &&
        typeof obj.provider === 'string' &&
        typeof obj.model === 'string'
    );
}

function isTokenUsageCost(obj: any): boolean {
    return (
        obj != null &&
        typeof obj.input === 'number' &&
        typeof obj.output === 'number' &&
        typeof obj.cache_read === 'number' &&
        typeof obj.cache_write === 'number' &&
        typeof obj.total === 'number'
    );
}

function isTokenUsage(obj: any): boolean {
    return (
        obj != null &&
        typeof obj.input === 'number' &&
        typeof obj.output === 'number' &&
        typeof obj.cache_read === 'number' &&
        typeof obj.cache_write === 'number' &&
        typeof obj.total === 'number' &&
        isTokenUsageCost(obj.cost)
    );
}

function isAssistantMessageError(obj: any): boolean {
    return obj != null && typeof obj.message === 'string';
}

function isAssistantMessage(obj: any): boolean {
    return (
        obj != null &&
        obj.mtype === 'assistant' &&
        typeof obj.id === 'string' &&
        typeof obj.timestamp === 'number' &&
        Array.isArray(obj.content) &&
        obj.content.every(
            (item: any) =>
                item != null && typeof item === 'object' && is__some__AssistantContent(item)
        ) &&
        isModelInfo(obj.model) &&
        isTokenUsage(obj.token_usage) &&
        (obj.finish_reason == null ||
            obj.finish_reason === 'stop' ||
            obj.finish_reason === 'length' ||
            obj.finish_reason === 'tool_use' ||
            obj.finish_reason === 'error' ||
            obj.finish_reason === 'aborted') &&
        (obj.error == null || isAssistantMessageError(obj.error))
    );
}

function isToolResult(obj: any): boolean {
    return (
        obj != null &&
        typeof obj.success === 'boolean' &&
        isTextContent(obj.content) &&
        (obj.internal_error == null || typeof obj.internal_error === 'string')
    );
}

function isToolResultMessage(obj: any): boolean {
    return (
        obj != null &&
        obj.mtype === 'tool_result' &&
        typeof obj.id === 'string' &&
        typeof obj.timestamp === 'number' &&
        typeof obj.call_id === 'string' &&
        typeof obj.tool_name === 'string' &&
        isToolResult(obj.result)
    );
}

function is__some__AgentMessage(obj: any): boolean {
    switch (obj.mtype) {
        case 'user':
            return isUserMessage(obj);
        case 'system':
            return isSystemMessage(obj);
        case 'assistant':
            return isAssistantMessage(obj);
        case 'tool_result':
            return isToolResultMessage(obj);
        default:
            return false;
    }
}

export function isAgentMessage(obj: any): obj is AgentMessage {
    return obj != null && typeof obj === 'object' && is__some__AgentMessage(obj);
}
