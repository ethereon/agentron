import { div } from '@ethereon/ein/dom/utils';
import { SessionView } from '../session/session-view.js';
import { DisposableObject } from '@ethereon/ein/disposable';

export class AppView extends DisposableObject {
    readonly container: HTMLElement;

    private readonly sessionView: SessionView;

    constructor() {
        super();
        this.sessionView = this.disposables.add(new SessionView());
        this.container = div({
            child: this.sessionView.container
        });
    }
}
