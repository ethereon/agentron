import * as pi from '@mariozechner/pi-ai';

import type { LLMRequest, ToolSet } from '../llm-request.js';
import type { Model } from '../model.js';
import type { StreamingMessageType, AssistantMessage, StreamingMessage } from '../agent-message.js';
import { fromPiAssistantMessage, translateToPi } from './pi-message-translator.js';
import { jsonSchemaToolToPiTool } from './pi-tool-translator.js';
import { asPiModel } from './pi-model-translator.js';

export type PiModel = pi.Model<pi.KnownApi>;

interface PiBackendParams {
    model: Model;
    apiKey?: string;
}

export class PiBackend {
    private readonly model: PiModel;
    private readonly apiKey?: string;

    constructor(params: PiBackendParams) {
        this.model = asPiModel(params.model);
        this.apiKey = params.apiKey;
    }

    async transmit(request: LLMRequest): Promise<AssistantMessage> {
        const translation = translateToPi({
            messages: request.messages
        });
        const context: pi.Context = {
            systemPrompt: translation.systemPrompt,
            messages: translation.messages,
            tools: getPiTools(request.tools)
        };

        // Stream
        const stream = pi.streamSimple(this.model, context, {
            apiKey: this.apiKey,
            signal: request.abortSignal,
            reasoning: request.reasoning,
            headers: {
                'HTTP-Referer': 'https://github.com/ethereon/agentron',
                'X-Title': 'Agentron'
            }
        });
        const sessionId = request.sessionId;
        const responseId = crypto.randomUUID();
        const onStreamingMessage = request.onStreamingMessage;
        for await (const streamEvent of stream) {
            maybeStreamMessage(streamEvent, sessionId, responseId, onStreamingMessage);
        }

        // Get the final accumulated message
        const finalMessage = await stream.result();

        if (finalMessage.content.length === 0 && !request.abortSignal?.aborted) {
            if (finalMessage.errorMessage != null) {
                throw Error(finalMessage.errorMessage);
            }
            throw Error('No response received from backend.');
        }

        return fromPiAssistantMessage({
            id: responseId,
            message: finalMessage
        });
    }
}

function maybeStreamMessage(
    ev: pi.AssistantMessageEvent,
    sessionId: string,
    messageId: string,
    callback: (message: StreamingMessage) => void
): void {
    let type: StreamingMessageType | undefined = undefined;
    let delta: string | undefined = undefined;
    switch (ev.type) {
        case 'text_delta':
            delta = ev.delta;
        case 'text_start':
        case 'text_end':
            type = ev.type;
            break;

        case 'thinking_delta':
            delta = ev.delta;
            type = 'reasoning_delta';
            break;

        case 'thinking_start':
            type = 'reasoning_start';
            break;

        case 'thinking_end':
            type = 'reasoning_end';
            break;

        default:
            return;
    }

    const partial = fromPiAssistantMessage({
        id: messageId,
        message: ev.partial
    });
    // Clear the finish reason from partial messages.
    // (pi sets it to 'stop' by default).
    if (partial.finish_reason != null) {
        partial.finish_reason = undefined;
    }

    callback({
        type,
        session_id: sessionId,
        content_index: ev.contentIndex,
        delta,
        partial
    });
}

function getPiTools(tools: ToolSet): pi.Tool[] {
    const key = 'pi.tools';
    const cachedTools = tools.backendState?.[key];
    if (cachedTools != null) {
        return cachedTools as pi.Tool[];
    }
    const convertedTools = tools.tools.map(jsonSchemaToolToPiTool);
    tools.backendState = {
        ...tools.backendState,
        [key]: convertedTools
    };
    return convertedTools;
}
