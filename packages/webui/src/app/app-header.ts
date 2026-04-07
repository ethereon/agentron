import { DisposableObject, DisposableStore } from '@ethereon/ein/disposable';
import * as style from '../gen/styles/app.js';

import { div } from '@ethereon/ein/dom/utils';
import { AppController } from './app-controller.js';
import { SessionController } from '../session/session-controller.js';
import { TokenUsage } from '@ethereon/agentypes/messages.js';
import { showSessionSelector } from '../session/session-selector.js';

export class AppHeader extends DisposableObject {
    readonly container: HTMLElement;

    constructor(app: AppController) {
        super();

        const appIcon = makeAppIcon();
        const contextMeter = this.disposables.add(new ContextMeter(app));
        const sessionSelector = this.disposables.add(new SessionSelectorButton(app));

        this.container = div({
            class: style.app_header,
            child: div({
                class: style.app_header_content,
                children: [appIcon, sessionSelector.container, contextMeter.container]
            })
        });

        this.disposables.add(
            app.sessions.subscribe(sessions => {
                if (sessions.length === 0) {
                }
            })
        );
    }
}

class ContextMeter extends DisposableObject {
    readonly container: HTMLElement;

    private readonly sessionSubs: DisposableStore;
    private activeSession?: SessionController;
    private contextWindow?: number;

    constructor(app: AppController) {
        super();
        this.sessionSubs = this.disposables.add(new DisposableStore());
        this.disposables.add(
            app.activeSession.subscribe(session => {
                this.setActiveSession(session);
            })
        );

        this.container = div({
            class: style.context_meter
        });

        const s = 22;
        const c = s / 2;
        const d = s - 4; // Avoid clipping
        const r = d / 2;
        this.container.innerHTML = `
<svg viewBox="0 0 ${s} ${s}" width="${s}" height="${s}" transform="rotate(-90)">
<circle class="${style.meter_bg}" cx="${c}" cy="${c}" r="${r}" />
<circle class="${style.meter_progress}" cx="${c}" cy="${c}" r="${r}" pathLength="100" />
  </svg>`;
    }

    private setActiveSession(session: SessionController | undefined) {
        this.sessionSubs.clear();
        this.activeSession = session;

        this.contextWindow = session?.metadata.model?.context_window;
        if (this.contextWindow == null || session == null) {
            this.container.style.display = 'none';
            return;
        }
        this.container.style.display = '';

        session.sessionMessages.then(messages => {
            if (this.activeSession === session && !this.isDisposed) {
                // Find the last message of type 'assistant' and set the token usage based on that.
                let set = false;
                for (let i = messages.length - 1; i >= 0; i--) {
                    const msg = messages[i];
                    if (msg.mtype === 'assistant') {
                        this.setTokenUsage(msg.token_usage);
                        set = true;
                        break;
                    }
                }
                if (!set) {
                    this.setUsage(0);
                }
            }
        });

        this.sessionSubs.push(
            session.onNewMessage.subscribe(msg => {
                if (msg.mtype === 'assistant') {
                    this.setTokenUsage(msg.token_usage);
                }
            }),
            session.onStreamingMessage.subscribe(msg => {
                this.setTokenUsage(msg.partial.token_usage);
            })
        );
    }

    private setTokenUsage(tokenUsage: TokenUsage) {
        this.setUsage(tokenUsage.total);
    }

    private setUsage(usage: number) {
        const max = this.contextWindow;
        if (max == null || max <= 0 || !isFinite(max)) {
            this.setMeterState(0, 'Context window usage unavailable');
            return;
        }

        const percentage = Math.max(0, Math.min(100, Math.round((100 * usage) / max)));
        this.setMeterState(
            percentage,
            `Context window usage: ${percentage}% (${usage.toLocaleString()} / ${max.toLocaleString()})`
        );
    }

    private setMeterState(progress: number, title: string) {
        this.container.style.setProperty('--context-meter-progress', String(progress));
        this.container.title = title;
    }
}

class SessionSelectorButton extends DisposableObject {
    readonly container: HTMLElement;

    constructor(app: AppController) {
        super();
        this.container = makeHeaderIcon(
            '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none"><path fill="currentColor" d="M17.857 12.509a.6.6 0 0 1 .069.485.65.65 0 0 1-.32.39l-8.285 4.49a.73.73 0 0 1-.696 0L.34 13.384a.65.65 0 0 1-.313-.391.6.6 0 0 1 .072-.482.7.7 0 0 1 .417-.297.74.74 0 0 1 .52.061l7.94 4.302 7.94-4.302a.74.74 0 0 1 .522-.064c.176.044.327.151.419.298m-.942-4.082-7.94 4.301-7.94-4.301a.74.74 0 0 0-.506-.04.68.68 0 0 0-.399.292.6.6 0 0 0-.074.468c.04.158.143.297.29.388l8.284 4.49a.73.73 0 0 0 .696 0l8.285-4.49a.7.7 0 0 0 .205-.165.597.597 0 0 0 .051-.716.7.7 0 0 0-.18-.19.72.72 0 0 0-.516-.122.7.7 0 0 0-.256.085M0 5.132c0-.113.032-.223.093-.32a.67.67 0 0 1 .252-.234L8.63.088a.73.73 0 0 1 .696 0l8.285 4.49c.104.056.19.137.25.234a.61.61 0 0 1 0 .64.67.67 0 0 1-.25.234l-8.285 4.49a.73.73 0 0 1-.696 0L.345 5.686a.67.67 0 0 1-.252-.234.6.6 0 0 1-.093-.32m2.06 0L8.976 8.88l6.915-3.748-6.915-3.748z"/></svg>',
            style.app_header_icon_button
        );
        this.container.onclick = ev => {
            ev.preventDefault();
            ev.stopPropagation();
            showSessionSelector(app);
        };
        this.disposables.add(
            app.sessions.subscribe(sessions => {
                this.container.style.display = sessions.length > 1 ? '' : 'none';
            })
        );
    }
}

function makeHeaderIcon(html: string, title: string): HTMLElement {
    const icon = div({ class: style.app_header_icon_button });
    icon.innerHTML = html;
    icon.title = title;
    return icon;
}

function makeAppIcon(): HTMLElement {
    return makeHeaderIcon(
        `<a class="${style.app_header_icon_button}" href="https://github.com/ethereon/agentron/" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="18" fill="none"><path fill="currentColor" d="M5.918.043c.707-.13 1.53.025 2.478.585l.093.056c.05.032.135.087.226.134A.6.6 0 0 0 8.967.9h1.014c.371 0 .617-.176.706-.217.987-.605 1.84-.774 2.569-.64.73.134 1.33.57 1.814 1.16.824 1.002 1.322 2.457 1.564 3.67 1.74.303 2.815.719 2.815 1.178 0 .925-4.354 1.675-9.724 1.675C4.354 7.726 0 6.976 0 6.051c0-.433.958-.829 2.53-1.126.238-1.223.738-2.706 1.574-3.723C4.589.612 5.189.177 5.918.043"/><path fill="currentColor" opacity="0.7" fill-rule="evenodd" d="M16.452 13.22a4.73 4.73 0 0 1-4.73 4.728H7.727a4.73 4.73 0 0 1-4.729-4.728V8.992c1.747.288 4.117.466 6.728.466s4.98-.178 6.727-.466zm-8.765-2.606a.964.964 0 0 0-.964.963v1.184a.964.964 0 0 0 1.928 0v-1.184a.963.963 0 0 0-.964-.963m4.25 0a.964.964 0 0 0-.964.963v1.184a.964.964 0 0 0 1.928 0v-1.184a.964.964 0 0 0-.964-.963" clip-rule="evenodd"/></svg></a>`,
        'Agentron'
    );
}
