import { DisposableObject, DisposableStore } from '@ethereon/ein/disposable';
import * as style from '../gen/styles/app.js';

import { div } from '@ethereon/ein/dom/utils';
import { AppController } from './app-controller.js';
import { SessionController } from '../session/session-controller.js';
import { TokenUsage } from '@ethereon/agentypes/messages.js';

export class AppHeader extends DisposableObject {
    readonly container: HTMLElement;

    constructor(app: AppController) {
        super();

        const contextMeter = this.disposables.add(new ContextMeter(app));

        this.container = div({
            class: style.app_header,
            child: div({
                class: style.app_header_content,
                children: [makeAppIcon(), contextMeter.container]
            })
        });
    }
}

function makeAppIcon(): HTMLElement {
    const icon = div({ class: style.app_icon });
    icon.innerHTML =
        '<a href="https://github.com/ethereon/agentron/" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="18" fill="none"><path fill="currentColor" d="M5.918.043c.707-.13 1.53.025 2.478.585l.093.056c.05.032.135.087.226.134A.6.6 0 0 0 8.967.9h1.014c.371 0 .617-.176.706-.217.987-.605 1.84-.774 2.569-.64.73.134 1.33.57 1.814 1.16.824 1.002 1.322 2.457 1.564 3.67 1.74.303 2.815.719 2.815 1.178 0 .925-4.354 1.675-9.724 1.675C4.354 7.726 0 6.976 0 6.051c0-.433.958-.829 2.53-1.126.238-1.223.738-2.706 1.574-3.723C4.589.612 5.189.177 5.918.043"/><path fill="currentColor" opacity="0.7" fill-rule="evenodd" d="M16.452 13.22a4.73 4.73 0 0 1-4.73 4.728H7.727a4.73 4.73 0 0 1-4.729-4.728V8.992c1.747.288 4.117.466 6.728.466s4.98-.178 6.727-.466zm-8.765-2.606a.964.964 0 0 0-.964.963v1.184a.964.964 0 0 0 1.928 0v-1.184a.963.963 0 0 0-.964-.963m4.25 0a.964.964 0 0 0-.964.963v1.184a.964.964 0 0 0 1.928 0v-1.184a.964.964 0 0 0-.964-.963" clip-rule="evenodd"/></svg></a>';
    icon.title = 'Agentron';
    return icon;
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

        const meter = div({});
        const s = 20;
        const c = s / 2;
        const d = s - 4; // Avoid clipping
        const r = d / 2;
        meter.innerHTML = `
<svg viewBox="0 0 ${s} ${s}" width="${s}" height="${s}" transform="rotate(-90)">
<circle class="meter-bg" cx="${c}" cy="${c}" r="${r}" />
<circle class="meter-progress" cx="${c}" cy="${c}" r="${r}" pathLength="100" />
  </svg>`;

        this.container = div({
            class: style.context_meter,
            child: meter
        });
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
                    this.setProgress(0);
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
        this.setProgress(tokenUsage.total);
    }

    private setProgress(usage: number) {
        const max = this.contextWindow;
        if (max == null || max <= 0 || !isFinite(max)) {
            this.setProgress(0);
            this.container.title = 'Context usage unavailable';
            return;
        }
        const percentage = Math.round((100 * usage) / max);
        this.container.style.setProperty('--context-meter-progress', String(percentage));
        this.container.title = `Context window usage: ${percentage}% (${usage.toLocaleString()} / ${max.toLocaleString()})`;
    }
}
