import * as style from '../gen/styles/session.js';

import { AsyncQueue } from '@ethereon/ein/async';
import { DisposableObject } from '@ethereon/ein/disposable';

import type { AgentMessage, StreamingMessage } from '@ethereon/flux/agent-message';
import {
    AgentMessageView,
    AssistantMessageView,
    renderAgentMessage
} from '../message/message-view.js';
import { div } from '@ethereon/ein/dom/utils';

export class SessionView extends DisposableObject {
    readonly container: HTMLElement;
    readonly queue = new AsyncQueue();

    private sessionId?: string;
    private messageViewsById = new Map<string, AgentMessageView>();
    private lastMessageView?: AgentMessageView;
    private eventSource?: EventSource;

    constructor() {
        super();
        this.container = div({
            class: style.session_view
        });
        this.disposables.add({
            dispose: () => this.discardEventSource()
        });
    }

    async setSession(sessionId: string) {
        this.sessionId = sessionId;
        this.queue.enqueue(async () => {
            if (this.sessionId !== sessionId) {
                return;
            }
            await this.prepareForSession(sessionId);
        });
    }

    private async prepareForSession(sessionId: string) {
        this.discardEventSource();
        const response = await fetch(`/api/messages?session_id=${sessionId}`);
        const messages = await response.json();

        // Clear prior views and state.
        this.messageViewsById.clear();
        this.lastMessageView = undefined;
        this.container.replaceChildren();

        // Insert existing messages.
        if (this.sessionId !== sessionId) {
            return;
        }
        for (const message of messages) {
            this.insertMessageView(message);
        }

        // Setup streaming updates.
        this.eventSource = new EventSource(`/api/events?session_id=${sessionId}`);
        this.eventSource.addEventListener('new_message', event =>
            this.onNewMessage(JSON.parse(event.data))
        );
        this.eventSource.addEventListener('streaming_message', event =>
            this.onStreamingMessage(JSON.parse(event.data))
        );
    }

    private insertMessageView(message: AgentMessage) {
        if (message.mtype !== 'tool_result') {
            const view = renderAgentMessage(message);
            this.messageViewsById.set(message.id, view);
            this.container.appendChild(view.container);
            this.lastMessageView = view;
        } else {
            // Find the corresponding tool call view to attach this result to.
            const msgView = this.lastMessageView;
            if (!(msgView instanceof AssistantMessageView)) {
                throw new Error(
                    `Expected tool result to correspond to a view for an assistant message. Instead got ${msgView?.constructor.name ?? 'no view'}`
                );
            }
            msgView.attachToolResult(message);
        }
    }

    private onNewMessage(message: AgentMessage) {
        const existingView = this.messageViewsById.get(message.id);
        if (!existingView) {
            this.insertMessageView(message);
        } else if (existingView instanceof AssistantMessageView) {
            if (message.mtype !== 'assistant') {
                throw new Error(
                    `Expected message update to correspond to assistant message view. Instead got ${message.mtype}`
                );
            }
            existingView.syncToMessage(message);
        }
    }

    private onStreamingMessage(message: StreamingMessage) {
        const messageId = message.partial.id;
        const view = this.messageViewsById.get(messageId);
        if (!view) {
            this.insertMessageView(message.partial);
            return;
        }
        if (!(view instanceof AssistantMessageView)) {
            throw new Error(
                `Expected streaming message to correspond to assistant message view. Instead got ${view.constructor.name}`
            );
        }
        view.applyStreamingUpdate(message);
    }

    private discardEventSource() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = undefined;
        }
    }
}
