import { SessionsResponse } from '@ethereon/agentypes/web-responses.js';
import { SessionMetadata } from '@ethereon/agentypes/session.js';

import { DisposableObject } from '@ethereon/ein/disposable';
import { Observable, ObservableDisposable } from '@ethereon/ein/publisher';
import { SessionController, SessionItem } from '../session/session-controller.js';

class AppController extends DisposableObject {
    readonly sessions = new Observable<SessionItem[]>(this);
    readonly activeSession = new ObservableDisposable<SessionController | undefined>(this);

    private readonly idToSessionItem = new Map<string, SessionItem>();
    private pendingSubagentId?: string;

    constructor() {
        super();
        this.setup();
    }

    private async setup(): Promise<void> {
        const response = await fetch('/api/sessions');
        const sessions = (await response.json()) as SessionsResponse;
        const items = Object.entries(sessions).map(([id, metadata]) => ({ id, metadata }));
        for (const item of items) {
            this.idToSessionItem.set(item.id, item);
        }
        this.sessions.publish(items);

        this.setActiveSession(items?.[0]);
    }

    setActiveSession(sessionItem: SessionItem | undefined) {
        if (this.activeSession.value?.id === sessionItem?.id) {
            return;
        }
        this.activeSession.publish(
            sessionItem != null ? new SessionController(sessionItem) : undefined
        );
    }

    async activateSubagentSession(subagentId: string) {
        const activeSession = this.activeSession.value;
        if (
            // Already in progress
            this.pendingSubagentId === subagentId ||
            // No parent session
            activeSession == null
        ) {
            return;
        }
        const qualifiedId = `${activeSession.id}:${subagentId}`;
        const sessionItem = this.idToSessionItem.get(qualifiedId);
        if (sessionItem != null) {
            // Subagent already resolved.
            this.setActiveSession(sessionItem);
            return;
        }
        this.pendingSubagentId = subagentId;
        try {
            const response = await fetch(`/api/session-meta?session_id=${qualifiedId}`);
            const sessionMeta = (await response.json()) as SessionMetadata | null;
            if (sessionMeta == null) {
                return;
            }
            const sessionItem = { id: qualifiedId, metadata: sessionMeta };
            // Only track subagent in the internal ID -> Session Item table.
            // Exclude from the top-level sessions list.
            this.idToSessionItem.set(qualifiedId, sessionItem);
            if (this.pendingSubagentId === subagentId) {
                this.setActiveSession(sessionItem);
            }
        } finally {
            if (this.pendingSubagentId === subagentId) {
                this.pendingSubagentId = undefined;
            }
        }
    }
}

export const app = new AppController();
