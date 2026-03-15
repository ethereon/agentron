import { div } from '@ethereon/ein/dom/utils';
import { SessionView } from '../session/session-view.js';
import { DisposableObject } from '@ethereon/ein/disposable';

export class AppView extends DisposableObject {
    readonly container: HTMLElement;

    private readonly sessionView: SessionView;
    private sessions?: string[];

    constructor() {
        super();
        this.sessionView = this.disposables.add(new SessionView());
        this.container = div({
            child: this.sessionView.container
        });
        this.setup();
    }

    async setup() {
        const response = await fetch('/api/sessions');
        const sessions = await response.json();
        this.sessions = sessions;
        this.sessionView.setSession(sessions[0]);
    }
}
