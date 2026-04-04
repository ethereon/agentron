import type { SessionMetadata } from '@ethereon/agentypes/session.js';
import type { SessionId, SessionsResponse } from '@ethereon/agentypes/web-responses.js';

import { DisposableObject } from '@ethereon/ein/disposable';
import { Observable } from '@ethereon/ein/publisher';

export interface SessionItem {
    id: SessionId;
    meta: SessionMetadata;
}

class AppController extends DisposableObject {
    readonly sessions = new Observable<SessionItem[]>(this);
    readonly activeSession = new Observable<SessionId | undefined>(this);

    constructor() {
        super();
        this.setup();
    }

    private async setup(): Promise<void> {
        const response = await fetch('/api/sessions');
        const sessions = (await response.json()) as SessionsResponse;
        const items = Object.entries(sessions).map(([id, meta]) => ({ id, meta }));
        this.sessions.publish(items);
        this.activeSession.publish(items?.[0].id ?? undefined);
    }
}

export const app = new AppController();
