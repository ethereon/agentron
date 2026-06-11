import { SessionsResponse } from '@ethereon/agentypes/web-responses.js';
import { SessionMetadata } from '@ethereon/agentypes/session.js';

import { DisposableObject } from '@ethereon/ein/disposable';
import { listenForEvent } from '@ethereon/ein/dom/event-listener';
import { Observable, ObservableDisposable } from '@ethereon/ein/publisher';

import { SessionController, SessionItem } from '../session/session-controller.js';

type UrlHistoryMode = 'push' | 'replace';
type UrlUpdateMode = UrlHistoryMode | 'skip';

interface SetActiveSessionOptions {
    urlUpdate?: UrlUpdateMode;
}

class AppController extends DisposableObject {
    readonly sessions = new Observable<SessionItem[]>(this);
    readonly activeSession = new ObservableDisposable<SessionController | undefined>(this);

    private readonly idToSessionItem = new Map<string, SessionItem>();
    private readonly sessionUrl: SessionUrlObserver;
    private pendingSubagentId?: string;

    constructor() {
        super();
        this.sessionUrl = this.disposables.add(
            new SessionUrlObserver(sessionId =>
                this.setActiveSessionById(sessionId, { urlUpdate: 'skip' })
            )
        );
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

        // Check if there's a session ID available in the URL.
        const urlSession = await this.getSessionItem(this.sessionUrl.sessionId);
        this.setActiveSession(
            // Activate session from URL if available.
            // Fallback: first session.
            urlSession ?? items?.[0],
            { urlUpdate: 'replace' }
        );
    }

    setActiveSession(sessionItem: SessionItem | undefined, options?: SetActiveSessionOptions) {
        const urlUpdate = options?.urlUpdate ?? 'push';

        if (this.activeSession.value?.id === sessionItem?.id) {
            if (urlUpdate !== 'skip') {
                this.sessionUrl.updateSessionId(sessionItem?.id, urlUpdate);
            }
            return;
        }
        this.activeSession.publish(
            sessionItem != null ? new SessionController(sessionItem) : undefined
        );
        if (urlUpdate !== 'skip') {
            this.sessionUrl.updateSessionId(sessionItem?.id, urlUpdate);
        }
    }

    getSubagentSessionId(subagentId: string): string | undefined {
        const activeSession = this.activeSession.value;
        if (activeSession == null) {
            return undefined;
        }
        return `${activeSession.id}~${subagentId}`;
    }

    generateSubagentSessionUrl(subagentId: string): URL | undefined {
        const sessionId = this.getSubagentSessionId(subagentId);
        return this.generateSessionUrl(sessionId);
    }

    generateSessionUrl(sessionId: string | undefined): URL | undefined {
        return this.sessionUrl.generateSessionUrl(sessionId);
    }

    private async setActiveSessionById(
        sessionId: string | undefined,
        options?: SetActiveSessionOptions
    ) {
        const sessionItem = await this.getSessionItem(sessionId);
        const skipUrlUpdate = options?.urlUpdate === 'skip';
        if (skipUrlUpdate && this.sessionUrl.sessionId !== sessionId) {
            return;
        }
        if (sessionItem != null) {
            this.setActiveSession(sessionItem, options);
        }
    }

    async getSessionItem(sessionId: string | undefined): Promise<SessionItem | undefined> {
        if (sessionId == null) {
            return undefined;
        }

        const cachedItem = this.idToSessionItem.get(sessionId);
        if (cachedItem != null) {
            return cachedItem;
        }

        // Reaching this point typically implies that the session ID corresponds
        // to a subagent session. The metadata for these are lazily loaded and cached.
        try {
            const response = await fetch(
                `/api/session-meta?session_id=${encodeURIComponent(sessionId)}`
            );
            const sessionMeta = (await response.json()) as SessionMetadata | null;
            if (sessionMeta == null) {
                return undefined;
            }
            const sessionItem: SessionItem = {
                id: sessionId,
                metadata: sessionMeta
            };
            // Cache for future lookups.
            // Note that this subagent session item is intentionally not added to
            // the `this.sessions` list which only contains top-level sessions.
            this.idToSessionItem.set(sessionId, sessionItem);
            return sessionItem;
        } catch {
            return undefined;
        }
    }

    async activateSubagentSession(subagentId: string) {
        if (this.pendingSubagentId === subagentId) {
            // Already in the process of activating this subagent session.
            return;
        }
        const qualifiedId = this.getSubagentSessionId(subagentId);
        if (qualifiedId == null) {
            // No active session to derive subagent session ID from.
            return;
        }
        const sessionItem = this.idToSessionItem.get(qualifiedId);
        if (sessionItem != null) {
            // Subagent already resolved.
            this.setActiveSession(sessionItem);
            return;
        }
        this.pendingSubagentId = subagentId;
        try {
            const sessionItem = await this.getSessionItem(qualifiedId);
            if (sessionItem != null && this.pendingSubagentId === subagentId) {
                this.setActiveSession(sessionItem);
            }
        } finally {
            if (this.pendingSubagentId === subagentId) {
                this.pendingSubagentId = undefined;
            }
        }
    }
}

class SessionUrlObserver extends DisposableObject {
    private static readonly sessionParam = 'session_id';

    constructor(private readonly onSessionIdChange: (sessionId: string | undefined) => void) {
        super();
        const sync = () => this.onSessionIdChange(this.readSessionId());
        this.disposables.push(
            listenForEvent(window, 'hashchange', sync),
            listenForEvent(window, 'popstate', sync)
        );
    }

    get sessionId(): string | undefined {
        return this.readSessionId();
    }

    generateSessionUrl(sessionId: string | undefined): URL | undefined {
        const url = this.getCurrentUrl();
        if (url == null) {
            return undefined;
        }
        const hashParams = this.readHashParams(url);
        if (sessionId != null) {
            hashParams.set(SessionUrlObserver.sessionParam, sessionId);
        } else {
            hashParams.delete(SessionUrlObserver.sessionParam);
        }
        url.hash = hashParams.toString();
        return url;
    }

    updateSessionId(sessionId: string | undefined, mode: UrlHistoryMode) {
        const currentSessionId = this.readSessionId();
        if (currentSessionId === sessionId) {
            return;
        }
        const url = this.generateSessionUrl(sessionId);
        if (url == null) {
            return;
        }
        history[mode === 'push' ? 'pushState' : 'replaceState'](
            history.state,
            '', // historical unused parameter
            url
        );
    }

    private readSessionId(url = this.getCurrentUrl()): string | undefined {
        const sessionId = this.readHashParams(url).get(SessionUrlObserver.sessionParam)?.trim();
        return sessionId || undefined;
    }

    private readHashParams(url = this.getCurrentUrl()): URLSearchParams {
        return new URLSearchParams(url?.hash.replace(/^#/, ''));
    }

    private getCurrentUrl(): URL | undefined {
        try {
            return new URL(window.location.href);
        } catch {
            return undefined;
        }
    }
}

export const app = new AppController();
