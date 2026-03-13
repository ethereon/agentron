import {
    ContentType,
    MessageType,
    type TextContent,
    type AgentMessage,
    type ToolResult,
    type ToolResultMessage,
    type ToolCall
} from './agent-message.js';

export function textContent(text: string): TextContent {
    return {
        type: ContentType.TEXT,
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
        mtype: MessageType.TOOL_RESULT,
        id: crypto.randomUUID(),
        timestamp: Date.now(),
        call_id: call.id,
        tool_name: call.name,
        result
    };
}
