import * as style from '../gen/styles/session.js';

import { div } from '@ethereon/ein/dom/utils';
import { AppController } from '../app/app-controller.js';
import { DisposableObject } from '@ethereon/ein/disposable';
import { listenForEvent } from '@ethereon/ein/dom/event-listener';
import { Observable } from '@ethereon/ein/publisher';
import { debounce } from '@ethereon/ein/rate';
import { SessionItem } from './session-controller.js';

class SessionSelector extends DisposableObject {
    private readonly sessions: SessionItem[];
    private readonly popover: HTMLElement;
    private readonly selectedSession: Observable<SessionItem | undefined>;
    private readonly push: () => void;

    constructor(
        readonly app: AppController,
        sessions: SessionItem[]
    ) {
        super();

        const popover = (this.popover = div({
            class: style.x_session_selector_popover
        }));

        this.selectedSession = new Observable<SessionItem | undefined>(this);
        this.selectedSession.publish(app.activeSession.value);
        this.push = debounce(200, () => {
            app.setActiveSession(this.selectedSession.value);
        });

        // Order by creation timestamp (newest first)
        // Treat missing timestamps as 0.
        this.sessions = sessions.toSorted((a, b) => {
            const aTime = a.metadata.created ?? 0;
            const bTime = b.metadata.created ?? 0;
            return bTime - aTime;
        });

        const count = this.sessions.length;
        const items = this.sessions.map((session, idx) =>
            this.renderSessionItem(session, count - idx)
        );
        popover.append(...items);

        popover.onkeydown = this.onKeyDown.bind(this);

        this.disposables.push(
            {
                dispose: () => popover.remove()
            },

            listenForEvent(popover, 'toggle', ev => {
                const isVisible = ev.newState === 'open';
                if (!isVisible && !this.isDisposed) {
                    this.dispose();
                }
            }),

            this.selectedSession.subscribe(() => this.syncToSelectedSession())
        );

        popover.popover = 'auto';
        document.body.appendChild(popover);
        popover.showPopover();

        requestAnimationFrame(() => this.syncToSelectedSession('center'));
    }

    private renderSessionItem(session: SessionItem, index: number): HTMLElement {
        const shortHash =
            session.id.length <= 8
                ? session.id
                : session.id.slice(0, 3) + '…' + session.id.slice(-3);

        const item = div({
            class: style.x_session_selector_item,
            children: [
                div({
                    class: style.title_row,
                    children: [
                        div({
                            class: style.title,
                            text: session.metadata.title ?? `Session ${index}`
                        }),
                        div({
                            class: style.id,
                            text: shortHash
                        })
                    ]
                }),
                div({
                    class: style.created_at,
                    text: session.metadata.created
                        ? new Date(session.metadata.created).toLocaleString()
                        : 'Unknown creation time'
                })
            ]
        });
        item.onmousedown = (ev: MouseEvent) => {
            ev.stopImmediatePropagation();
            this.selectSession(session, true);
        };
        item.dataset.sessionId = session.id;
        item.tabIndex = 0;
        return item;
    }

    private hide(): void {
        if (this.popover.isConnected) {
            this.popover.hidePopover();
        }
    }

    private syncToSelectedSession(position: ScrollLogicalPosition = 'nearest'): void {
        const selectedSession = this.selectedSession.value;
        const currentSelection = this.popover.querySelector(`.${style.selected}`);
        if (currentSelection) {
            currentSelection.classList.remove(style.selected);
        }
        if (selectedSession) {
            const newSelection = this.popover.querySelector(
                `[data-session-id="${CSS.escape(selectedSession.id)}"]`
            );
            if (newSelection) {
                newSelection.classList.add(style.selected);
                newSelection.scrollIntoView({ block: position });
                (newSelection as HTMLElement).focus();
            }
        }
    }

    private onKeyDown(ev: KeyboardEvent): void {
        if (this.maybeHandleKeyboardEvent(ev)) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
        }
    }

    private maybeHandleKeyboardEvent(ev: KeyboardEvent): boolean {
        switch (ev.key) {
            case 'ArrowUp':
                this.selectRelative(-1);
                return true;
            case 'ArrowDown':
                this.selectRelative(1);
                return true;
            case 'Enter':
                this.hide();
                return true;
        }
        return false;
    }

    private selectRelative(delta: number): void {
        const selectedSession = this.selectedSession.value;
        const currentIndex = this.sessions.findIndex(s => s.id === selectedSession?.id);
        if (currentIndex === -1) {
            return;
        }
        const newIndex = (currentIndex + delta + this.sessions.length) % this.sessions.length;
        const newSession = this.sessions[newIndex];
        this.selectSession(newSession);
    }

    private selectSession(session: SessionItem | undefined, immediate: boolean = false): void {
        if (session !== this.selectedSession.value) {
            this.selectedSession.publish(session);
            if (immediate) {
                this.app.setActiveSession(this.selectedSession.value);
            } else {
                this.push();
            }
        }
    }
}

export function showSessionSelector(app: AppController): void {
    const sessions = app.sessions.value;
    if (sessions == null || sessions.length === 0) {
        console.warn('[SessionSelector] No sessions available to select.');
        return;
    }
    new SessionSelector(app, sessions);
}
