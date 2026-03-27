import * as style from '../../gen/styles/components/collapsible.js';

import { div } from '@ethereon/ein/dom/utils';
import { makeIcon } from '../../icons.js';

type LazyContentProvider = () => HTMLElement;

export interface CollapsibleParams {
    content: HTMLElement | LazyContentProvider;
    isExpanded: boolean;

    title?: string;
    titleClass?: string;

    headerContent?: HTMLElement;
    onExpansionChange?: (isExpanded: boolean) => void;
}

export class Collapsible {
    readonly container: HTMLElement;
    readonly toggler: HTMLElement;
    readonly header: HTMLElement;
    readonly subview: HTMLElement;
    readonly content: LazyContentProvider;

    onExpansionChange?: (isExpanded: boolean) => void;

    private _isExpanded?: boolean;

    constructor(params: CollapsibleParams) {
        if (params.onExpansionChange) {
            this.onExpansionChange = params.onExpansionChange;
        }

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

        const gutter = div({
            class: style.collapsible_content_gutter
        });

        const toggle = () => this.setExpanded(!this._isExpanded);
        this.header.onmousedown = toggle;
        gutter.onmousedown = toggle;

        this.container = div({
            class: style.collapsible,
            children: [
                this.header,
                div({
                    class: style.collapsible_content_container,
                    children: [gutter, this.subview]
                })
            ]
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
        this.onExpansionChange?.(expanded);
    }

    get isExpanded(): boolean {
        return !!this._isExpanded;
    }

    static element(params: CollapsibleParams): HTMLElement {
        return new this(params).container;
    }
}
