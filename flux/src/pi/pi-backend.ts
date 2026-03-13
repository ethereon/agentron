import * as pi from '@mariozechner/pi-ai';

import { log } from '../logging.js';
import { kDefaultReasoningLevel, type LLMRequest, type ToolSet } from '../llm-request.js';
import { fromPiAssistantMessage, translateToPi } from './pi-message-translator.js';
import { jsonSchemaToolToPiTool } from './pi-tool-translator.js';
import { asPiModel } from './pi-model-translator.js';
import { type Model, ModelReasoningLevel } from '../model.js';
import {
    StreamingMessageType,
    type AssistantMessage,
    type StreamingMessage
} from '../agent-message.js';

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
            reasoning: asThinkingLevel(request.reasoning),
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

function asThinkingLevel(level: ModelReasoningLevel | undefined): pi.ThinkingLevel | undefined {
    if (level == null) {
        // No reasoning level explicitly specified.
        // Use the default (usually medium).
        // Note that we don't want to return undefined here as that would effectively
        // disable reasoning for pi (at least for providers like Z.ai).
        return kDefaultReasoningLevel;
    }

    switch (level) {
        case ModelReasoningLevel.DISABLED:
            // For pi, a falsey/omitted reasoning level is equivalent to disabled.
            return undefined;

        case ModelReasoningLevel.LOW:
            return 'low';

        case ModelReasoningLevel.MEDIUM:
            return 'medium';

        case ModelReasoningLevel.HIGH:
            return 'high';

        case ModelReasoningLevel.EXTRA_HIGH:
            return 'xhigh';

        default:
            level satisfies never;
            log.warn(`Received unrecognized reasoning level: ${level}.`);
            return kDefaultReasoningLevel;
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
        case 'text_start':
            type = StreamingMessageType.TEXT_START;
            break;
        case 'text_delta':
            type = StreamingMessageType.TEXT_DELTA;
            delta = ev.delta;
            break;
        case 'text_end':
            type = StreamingMessageType.TEXT_END;
            break;
        case 'thinking_start':
            type = StreamingMessageType.REASONING_START;
            break;
        case 'thinking_delta':
            type = StreamingMessageType.REASONING_DELTA;
            delta = ev.delta;
            break;
        case 'thinking_end':
            type = StreamingMessageType.REASONING_END;
            break;
        default:
            return;
    }
    callback({
        type,
        session_id: sessionId,
        content_index: ev.contentIndex,
        delta,
        partial: fromPiAssistantMessage({
            id: messageId,
            message: ev.partial
        })
    });
}

function getStreamingMessageType(ev: pi.AssistantMessageEvent): StreamingMessageType | undefined {
    return undefined;
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
