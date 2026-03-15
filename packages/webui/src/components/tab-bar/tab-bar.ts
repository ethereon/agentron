import * as style from '../../gen/styles/components/tab-bar.js';

import { div } from '@ethereon/ein/dom/utils';

type OnSelectCallback = (index: number) => void;

interface TabParams {
    tabs: string[];
    onSelected?: OnSelectCallback;
    selectedIndex?: number;
}

export class TabBar {
    readonly container: HTMLElement;
    onSelected?: OnSelectCallback;

    private tabs: HTMLElement[] = [];
    private _selectedIndex = -1;

    constructor(params: TabParams) {
        this.container = div({
            class: style.tab_bar
        });
        this.configure(params);
    }

    configure(params: TabParams) {
        if (params.onSelected != null) {
            this.onSelected = params.onSelected;
        }
        this.tabs = params.tabs.map((label, index) => this.makeTab(label, index));
        this.container.replaceChildren(...this.tabs);
        this._selectedIndex = -1;
        this.setSelectedIndex(params.selectedIndex ?? Math.min(this.tabs.length, 1) - 1);
    }

    get selectedIndex(): number {
        return this._selectedIndex;
    }

    setSelectedIndex(index: number): void {
        if (index === this._selectedIndex) {
            return;
        }
        this._selectedIndex = index;
        this.tabs.forEach((tab, i) => tab.classList.toggle(style.selected, i === index));
        this.onSelected?.(index);
    }

    protected makeTab(label: string, index: number): HTMLElement {
        const tab = div({
            class: style.tab,
            text: label
        });
        tab.onmousedown = () => this.setSelectedIndex(index);
        return tab;
    }
}
