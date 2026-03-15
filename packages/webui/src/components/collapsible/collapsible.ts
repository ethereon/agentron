import * as style from '../../gen/styles/components/collapsible.js';

import { div } from '@ethereon/ein/dom/utils';
import { makeIcon } from '../../icons.js';

type LazyContentProvider = () => HTMLElement;

interface CollapsibleParams {
    content: HTMLElement | LazyContentProvider;
    isExpanded: boolean;

    title?: string;
    titleClass?: string;

    headerContent?: HTMLElement;
}

export class Collapsible {
    readonly container: HTMLElement;
    readonly toggler: HTMLElement;
    readonly header: HTMLElement;
    readonly subview: HTMLElement;
    readonly content: LazyContentProvider;

    private _isExpanded?: boolean;

    constructor(params: CollapsibleParams) {
        this.toggler = div({
            class: style.collapsible_toggler
        });

        this.subview = div({
            class: style.collapsible_content
        });

        this.header = div({
            class: style.collapsible_header,
            children: [
                this.toggler,
                params.headerContent ??
                    div({
                        text: params.title,
                        class: params.titleClass
                    })
            ]
        });

        this.header.onmousedown = () => this.setExpanded(!this._isExpanded);

        this.container = div({
            class: style.collapsible,
            children: [this.header, this.subview]
        });

        const content = params.content;
        this.content = typeof content === 'function' ? content : () => content;

        this.setExpanded(params.isExpanded);
    }

    setExpanded(expanded: boolean) {
        if (this._isExpanded === expanded) {
            return;
        }
        this._isExpanded = expanded;
        this.toggler.replaceChildren(makeIcon(expanded ? 'ChevronDown' : 'ChevronRight'));
        this.subview.replaceChildren(...(expanded ? [this.content()] : []));
    }

    static element(params: CollapsibleParams): HTMLElement {
        return new Collapsible(params).container;
    }
}
