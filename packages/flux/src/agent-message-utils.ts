import type {
    ContentType,
    MessageType,
    TextContent,
    AgentMessage,
    ToolResult,
    ToolResultMessage,
    ToolCall
} from './types/messages.js';

export function textContent(text: string): TextContent {
    return {
        type: 'text',
        text
    };
}

export function firstMessageofType<T extends MessageType>(
    mtype: T,
    messages: AgentMessage[]
): Extract<AgentMessage, { mtype: T }> | undefined {
    for (const ev of messages) {
        if (ev.mtype === mtype) {
            return ev as Extract<AgentMessage, { mtype: T }>;
        }
    }
    return undefined;
}

export function makeToolResultMessage(call: ToolCall, result: ToolResult): ToolResultMessage {
    return {
        mtype: 'tool_result',
        id: crypto.randomUUID(),
        timestamp: Date.now(),
        call_id: call.id,
        tool_name: call.name,
        result
    };
}
