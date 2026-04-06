import { AgentMessage, StreamingMessage } from '@ethereon/agentypes/messages.js';
import { MessagesResponse } from '@ethereon/agentypes/web-responses.js';
import { DisposableObject } from '@ethereon/ein/disposable';
import { listenForEvent } from '@ethereon/ein/dom/event-listener';
import { Observable } from '@ethereon/ein/publisher';

export class SessionController extends DisposableObject {
    readonly onNewMessage = new Observable<AgentMessage>(this);
    readonly onStreamingMessage = new Observable<StreamingMessage>(this);

    // Completed messages
    readonly sessionMessages: Promise<AgentMessage[]>;

    constructor(readonly id: string) {
        super();
        this.sessionMessages = this.fetchMessages();
    }

    private async fetchMessages(): Promise<AgentMessage[]> {
        const response = await fetch(`/api/messages?session_id=${this.id}`);
        const messages = (await response.json()) as MessagesResponse;
        this.listenForStreamingMessages();
        return messages;
    }

    private listenForStreamingMessages() {
        const eventSource = new EventSource(`/api/events?session_id=${this.id}`);
        this.disposables.push(
            listenForEvent<MessageEvent>(eventSource, 'new_message', event => {
                this.onNewMessage.publish(JSON.parse(event.data) as AgentMessage);
            }),
            listenForEvent<MessageEvent>(eventSource, 'streaming_message', event => {
                this.onStreamingMessage.publish(JSON.parse(event.data) as StreamingMessage);
            }),
            {
                dispose: () => eventSource.close()
            }
        );
    }
}
