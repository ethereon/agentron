import * as style from '../gen/styles/app.js';

import { type AppController } from './app-controller.js';

import { div } from '@ethereon/ein/dom/utils';
import { SessionView } from '../session/session-view.js';
import { DisposableObject } from '@ethereon/ein/disposable';
import { AppHeader } from './app-header.js';
import { DisposableElementParent } from '@ethereon/ein/dom/disposable';

export class AppView extends DisposableObject {
    readonly container: HTMLElement;

    private readonly header: AppHeader;

    constructor(app: AppController) {
        super();
        this.header = this.disposables.add(new AppHeader(app));

        const sessionParent = this.disposables.add(new DisposableElementParent<SessionView>());
        sessionParent.container.classList.add(style.app_content);

        this.container = div({
            class: style.app,
            children: [this.header.container, sessionParent.container]
        });

        this.disposables.add(
            app.activeSession.subscribe(async session => {
                if (session == null) {
                    sessionParent.content = undefined;
                    return;
                }
                // Swap in the new session view after it finishes the initial
                // render to avoid jank/flickering.
                const sessionView = new SessionView(session);
                await sessionView.initialRenderComplete;
                requestAnimationFrame(() => {
                    if (!this.isDisposed && app.activeSession.value?.id === session.id) {
                        sessionParent.content = sessionView;
                    }
                });
            })
        );
    }
}
