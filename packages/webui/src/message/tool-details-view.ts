import * as style from '../gen/styles/message.js';

import { ToolCall, ToolResult } from '@ethereon/agentypes/messages.js';
import { TabBar } from '../components/tab-bar/tab-bar.js';
import { TabView } from '../components/tab-view/tab-view.js';
import { renderJsonTree } from '../components/json-tree/json-tree.js';
import { div } from '@ethereon/ein/dom/utils';

export interface IToolDetailsView {
    readonly container: HTMLElement;

    renderResults(result: ToolResult): void;
}
function makeResultView(result: ToolResult): HTMLElement {
    let resultText = result.content?.text;
    if (resultText == null) {
        resultText = 'No output produced.';
    }
    const resultView = div({
        classes: [style.tool_call_result, result.success ? style.success : style.failed],
        text: resultText
    });
    return resultView;
}

class ToolDetailsView implements IToolDetailsView {
    readonly container: HTMLElement;

    private readonly tabBar: TabBar;
    private readonly tabView: TabView;

    private argsView?: HTMLElement;
    private resultView?: HTMLElement;

    constructor(
        readonly toolCall: ToolCall,
        result?: ToolResult
    ) {
        const selectedIndex = result ? 1 : 0;
        if (result != null) {
            this.renderResults(result);
        }

        this.tabBar = new TabBar({
            tabs: ['Arguments', 'Results'],
            selectedIndex
        });

        this.tabView = new TabView({
            tabs: [() => this.getArgsView(), () => this.getResultView()],
            selectedIndex,
            tabBar: this.tabBar
        });
        this.tabView.container.classList.add(style.tool_call_details_content);

        this.container = div({
            class: style.tool_call_details,
            children: [this.tabBar.container, this.tabView.container]
        });
    }

    renderResults(result: ToolResult) {
        if (this.resultView != null) {
            return;
        }
        this.resultView = makeResultView(result);
        this.tabView?.selectTabAtIndex(1);
    }

    private getArgsView(): HTMLElement {
        if (!this.argsView) {
            this.argsView = renderJsonTree(this.toolCall.arguments, { unwrapRoot: true });
        }
        return this.argsView;
    }

    private getResultView(): HTMLElement {
        if (this.resultView == null) {
            return div({
                text: 'Tool result not yet available.'
            });
        }
        return this.resultView;
    }
}

class REPLDetailsView implements IToolDetailsView {
    readonly container: HTMLElement;

    private resultView?: HTMLElement;

    constructor(
        readonly toolCall: ToolCall,
        result?: ToolResult
    ) {
        this.container = div({
            classes: [style.tool_call_details, style.tool_call_details_content],
            child: div({
                classes: [style.repl_details_input, style.tool_call_result],
                children: [
                    div({
                        class: style.prompt,
                        text: '>>>'
                    }),
                    div({
                        text:
                            (toolCall.arguments.code as string) ??
                            '<internal error: no code argument>'
                    })
                ]
            })
        });

        if (result) {
            this.renderResults(result);
        }
    }

    renderResults(result: ToolResult): void {
        if (this.resultView != null) {
            return;
        }
        this.resultView = makeResultView(result);
        this.container.appendChild(this.resultView);
    }
}

export function makeToolDetailsView(toolCall: ToolCall, result?: ToolResult): IToolDetailsView {
    switch (toolCall.name) {
        case 'run_in_python_repl':
            return new REPLDetailsView(toolCall, result);

        default:
            return new ToolDetailsView(toolCall, result);
    }
}
