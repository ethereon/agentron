import * as pi from '@earendil-works/pi-ai';

import { textContent } from '../agent-message-utils.js';
import type {
    FinishReason,
    AgentMessage,
    ModelInfo,
    TokenUsage,
    AssistantMessage,
    AssistantContent,
    TextContent
} from '@ethereon/agentypes/messages.js';

interface PiTranslation {
    systemPrompt: string;
    messages: pi.Message[];
}

export interface PiMessageIdTable {
    assistant: string;
    reasoning: string;
}

interface ToPiTranslationRequest {
    messages: Iterable<AgentMessage>;
}

interface FromPiTranslationRequest {
    id: string;
    message: pi.AssistantMessage;
}

export function translateToPi(request: ToPiTranslationRequest): PiTranslation {
    const messages: pi.Message[] = [];
    let systemPrompt: string = '';

    function processMessage(msg: AgentMessage): void {
        switch (msg.mtype) {
            case 'system':
                systemPrompt = msg.content.text;
                return;

            case 'user':
                messages.push({
                    role: 'user',
                    content: [msg.content],
                    timestamp: msg.timestamp
                });
                return;

            case 'assistant':
                messages.push({
                    role: 'assistant',
                    content: msg.content.map(asPiAssistantContent),
                    api: msg.model.api as pi.Api,
                    provider: msg.model.provider as pi.Provider,
                    model: msg.model?.model,
                    usage: asPiUsage(msg.token_usage),
                    stopReason: asPiStopReason(msg.finish_reason),
                    errorMessage: msg.error?.message,
                    timestamp: msg.timestamp
                });
                return;

            case 'tool_result':
                messages.push({
                    role: 'toolResult',
                    toolCallId: msg.call_id,
                    toolName: msg.tool_name,
                    timestamp: msg.timestamp,
                    isError: !msg.result.success,
                    // In practice, we shouldn't hit missing content here.
                    // The source event producer should auto-inject missing content.
                    content: [
                        msg.result.content ??
                            textContent(
                                msg.result.success ? 'Tool call succeeded' : 'Tool call failed'
                            )
                    ]
                });
                return;

            default:
                msg satisfies never;
        }
    }

    for (const msg of request.messages) {
        processMessage(msg);
    }

    return {
        systemPrompt,
        messages
    };
}

export function fromPiAssistantMessage(request: FromPiTranslationRequest): AssistantMessage {
    const msg = request.message;
    return {
        mtype: 'assistant',
        id: request.id,
        content: msg.content.map(fromPiAssistantContent),
        timestamp: msg.timestamp,
        model: extractModelInfo(msg),
        token_usage: fromPiUsage(msg.usage),
        finish_reason: fromPiStopReason(msg.stopReason),
        error: msg.errorMessage ? { message: msg.errorMessage } : undefined
    };
}

type PiAssistantContent = pi.TextContent | pi.ThinkingContent | pi.ToolCall;

function asPiAssistantContent(content: AssistantContent): PiAssistantContent {
    switch (content.type) {
        case 'text':
            return content;

        case 'tool_call':
            return {
                type: 'toolCall',
                id: content.id,
                name: content.name,
                arguments: content.arguments,
                thoughtSignature: content.thought_signature
            };

        case 'reasoning':
            return {
                type: 'thinking',
                thinking: content.text,
                thinkingSignature: content.signature,
                redacted: content.redacted
            };

        default:
            content satisfies never;
            throw Error(`Unsupported content type: ${(content as any).type}`);
    }
}

function fromPiAssistantContent(content: PiAssistantContent): AssistantContent {
    switch (content.type) {
        case 'text':
            return content as TextContent;

        case 'toolCall':
            return {
                type: 'tool_call',
                id: content.id,
                name: content.name,
                arguments: content.arguments,
                thought_signature: content.thoughtSignature
            };

        case 'thinking':
            return {
                type: 'reasoning',
                text: content.thinking,
                signature: content.thinkingSignature,
                redacted: content.redacted
            };

        default:
            content satisfies never;
            throw Error(`Unsupported Pi content type: ${(content as any).type}`);
    }
}

function asPiStopReason(reason: string | undefined): pi.StopReason {
    if (reason == null) {
        return 'stop';
    }
    switch (reason) {
        case 'stop':
        case 'length':
        case 'error':
        case 'aborted':
            return reason;

        case 'tool_use':
            return 'toolUse';

        default:
            return 'stop';
    }
}

function fromPiStopReason(reason: pi.StopReason | undefined): FinishReason | undefined {
    if (reason == null) {
        return undefined;
    }
    switch (reason) {
        case 'stop':
        case 'length':
        case 'error':
        case 'aborted':
            return reason;

        case 'toolUse':
            return 'tool_use';

        default:
            return reason satisfies never;
    }
}

function asPiUsage(usage: TokenUsage): pi.Usage {
    const cost = usage.cost;
    return {
        input: usage.input,
        output: usage.output,
        cacheRead: usage.cache_read,
        cacheWrite: usage.cache_write,
        totalTokens: usage.total,
        cost: {
            input: cost.input,
            output: cost.output,
            cacheRead: cost.cache_read,
            cacheWrite: cost.cache_write,
            total: cost.total
        }
    };
}

function fromPiUsage(usage: pi.Usage): TokenUsage {
    return {
        input: usage.input,
        output: usage.output,
        cache_read: usage.cacheRead,
        cache_write: usage.cacheWrite,
        total: usage.totalTokens,
        cost: {
            input: usage.cost.input,
            output: usage.cost.output,
            cache_read: usage.cost.cacheRead,
            cache_write: usage.cost.cacheWrite,
            total: usage.cost.total
        }
    };
}

function extractModelInfo(msg: pi.AssistantMessage): ModelInfo {
    return {
        api: msg.api,
        provider: msg.provider,
        model: msg.model
    };
}
