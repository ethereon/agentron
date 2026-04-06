import type { AgentMessage } from '@ethereon/agentypes/messages.js';
import type { SessionMetadata } from '@ethereon/agentypes/session.js';
import type { SessionId, SessionsResponse } from '@ethereon/agentypes/web-responses.js';

import { DisposableObject } from '@ethereon/ein/disposable';
import { Observable, ObservableDisposable } from '@ethereon/ein/publisher';
import { SessionController } from '../session/session-controller.js';

export interface SessionItem {
    id: SessionId;
    meta: SessionMetadata;
}

export class AppController extends DisposableObject {
    readonly sessions = new Observable<SessionItem[]>(this);
    readonly activeSession = new ObservableDisposable<SessionController | undefined>(this);

    constructor() {
        super();
        this.setup();
    }

    private async setup(): Promise<void> {
        const response = await fetch('/api/sessions');
        const sessions = (await response.json()) as SessionsResponse;
        const items = Object.entries(sessions).map(([id, meta]) => ({ id, meta }));
        this.sessions.publish(items);

        this.setActiveSession(items?.[0].id ?? undefined);
    }

    setActiveSession(sessionId: string | undefined) {
        this.activeSession.publish(
            sessionId != null ? new SessionController(sessionId) : undefined
        );
    }
}
