import * as style from '../gen/styles/session.js';

import type { AgentMessage, StreamingMessage } from '@ethereon/agentypes/messages.js';

import { DisposableObject } from '@ethereon/ein/disposable';
import {
    AgentMessageView,
    AssistantMessageView,
    renderAgentMessage
} from '../message/message-view.js';
import { div } from '@ethereon/ein/dom/utils';
import { SessionController } from './session-controller.js';

export class SessionView extends DisposableObject {
    readonly container: HTMLElement;
    readonly initialRenderComplete: Promise<void>;

    private messageViewsById = new Map<string, AgentMessageView>();
    private lastMessageView?: AgentMessageView;

    constructor(session: SessionController) {
        super();
        this.container = div({
            class: style.session_view
        });
        this.initialRenderComplete = this.setup(session);
    }

    private async setup(session: SessionController): Promise<void> {
        const messages = await session.sessionMessages;
        if (this.isDisposed) {
            return;
        }
        for (const message of messages) {
            this.insertMessageView(message);
        }
        this.disposables.push(
            session.onNewMessage.subscribe(this.onNewMessage.bind(this)),
            session.onStreamingMessage.subscribe(this.onStreamingMessage.bind(this))
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
}
