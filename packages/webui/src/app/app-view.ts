import * as style from '../gen/styles/app.js';

import { div } from '@ethereon/ein/dom/utils';
import { DisposableObject } from '@ethereon/ein/disposable';
import { DisposableElementParent } from '@ethereon/ein/dom/disposable';

import { app } from './app-controller.js';
import { SessionView } from '../session/session-view.js';
import { AppHeader } from './app-header.js';

export class AppView extends DisposableObject {
    readonly container: HTMLElement;

    private readonly header: AppHeader;

    constructor() {
        super();
        this.header = this.disposables.add(new AppHeader());

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
                    } else {
                        sessionView.dispose();
                    }
                });
            })
        );
    }
}
