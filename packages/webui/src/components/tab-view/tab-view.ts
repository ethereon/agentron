import { div } from '@ethereon/ein/dom/utils';
import type { TabBar } from '../tab-bar/tab-bar.js';

type Tab = () => HTMLElement;

interface TabViewParams {
    tabs: Tab[];
    tabBar?: TabBar;
    selectedIndex?: number;
    onSelected?: (index: number) => void;
}

export class TabView {
    readonly container: HTMLElement;
    readonly tabs: Tab[];

    tabBar?: TabBar;
    onSelected?: (index: number) => void;

    private _selectedIndex = -1;

    constructor(params: TabViewParams) {
        this.container = div({});
        this.tabs = params.tabs;
        this.onSelected = params.onSelected;

        if (params.tabBar) {
            this.tabBar = params.tabBar;
            this.tabBar.onSelected = index => this.selectTabAtIndex(index);
        }

        this.selectTabAtIndex(params.selectedIndex ?? Math.min(this.tabs.length, 1) - 1);
    }

    selectTabAtIndex(index: number): void {
        if (index === this._selectedIndex) {
            return;
        }
        this._selectedIndex = index;
        this.container.replaceChildren(this.tabs[index]());
        this.tabBar?.setSelectedIndex(index);
        this.onSelected?.(index);
    }
}
