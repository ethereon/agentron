import * as style from '../gen/styles/message.js';

import type {
    AgentMessage,
    AssistantContent,
    AssistantMessage,
    StreamingMessage,
    SystemMessage,
    ToolCall,
    ToolResult,
    ToolResultMessage,
    UserMessage
} from '@ethereon/flux/agent-message';

import { div, span } from '@ethereon/ein/dom/utils';
import { Collapsible } from '../components/collapsible/collapsible.js';
import { renderJsonTree } from '../components/json-tree/json-tree.js';
import { TabBar } from '../components/tab-bar/tab-bar.js';
import { TabView } from '../components/tab-view/tab-view.js';
import { makeIcon } from '../icons.js';

export type AgentMessageView = SystemMessageView | UserMessageView | AssistantMessageView;

export function renderAgentMessage(message: AgentMessage): AgentMessageView {
    const mtype = message.mtype;
    switch (mtype) {
        case 'system':
            return new SystemMessageView(message);

        case 'user':
            return new UserMessageView(message);

        case 'assistant':
            return new AssistantMessageView(message);

        case 'tool_result':
            throw new Error('Tool results should be handled out of band.');

        default:
            mtype satisfies never;
            throw new Error(`Unsupported message type: ${mtype}`);
    }
}

class SystemMessageView {
    readonly container: HTMLElement;

    constructor(msg: SystemMessage) {
        this.container = Collapsible.element({
            title: 'System Prompt',
            titleClass: style.message_title,
            content: div({
                class: style.message_text,
                text: msg.content.text
            }),
            isExpanded: false
        });
    }
}

class UserMessageView {
    readonly container: HTMLElement;

    constructor(msg: UserMessage) {
        this.container = Collapsible.element({
            title: 'User',
            titleClass: style.message_title,
            content: div({
                class: style.message_text,
                text: msg.content.text
            }),
            isExpanded: true
        });
    }
}

export class AssistantMessageView {
    readonly container: HTMLElement;

    private readonly subviews: AssistantSubView[] = [];

    constructor(msg: AssistantMessage) {
        this.container = div({
            class: style.assistant_message_container
        });
        this.syncToMessage(msg);
    }

    // This may be called on initialization, or once streaming updates are complete
    // (e.g.: to insert non-streaming content like tool calls).
    syncToMessage(msg: AssistantMessage) {
        const content = msg.content;
        const subviews = this.subviews;
        for (let i = subviews.length; i < content.length; ++i) {
            const newSubview = this.renderSubView(content[i]);
            subviews.push(newSubview);
            this.container.appendChild(newSubview.container);
        }
    }

    applyStreamingUpdate(update: StreamingMessage) {
        switch (update.type) {
            case 'text_start':
                this.subviews.push(new AssistantResponseView(''));
                break;

            case 'reasoning_start':
                this.subviews.push(new ReasoningView(''));
                break;

            case 'text_delta':
                this.patchSubView(update, AssistantResponseView);
                break;

            case 'reasoning_delta':
                this.patchSubView(update, ReasoningView);
                break;
        }

        // Sanity check
        if (update.content_index !== this.subviews.length - 1) {
            throw new Error(
                `Expected streaming update content index to correspond to latest subview index. Instead got content index ${update.content_index} and latest subview index ${this.subviews.length - 1}`
            );
        }
    }

    attachToolResult(msg: ToolResultMessage) {
        const callId = msg.call_id;
        for (const subView of this.subviews) {
            if (subView instanceof ToolCallView && subView.toolCall.id === callId) {
                subView.setResult(msg.result);
                return;
            }
        }
        throw new Error(`No subview found for tool result with call ID ${callId}`);
    }

    private patchSubView(
        update: StreamingMessage,
        expectedType: new (...args: any[]) => MutableContentView
    ) {
        const subView = this.subviews.at(-1);
        if (!subView) {
            throw new Error(`No subview found to apply streaming update`);
        }
        if (!(subView instanceof expectedType)) {
            throw new Error(
                `Expected latest subview to be ${expectedType.name} when applying streaming update. Instead got ${subView.constructor.name}`
            );
        }
        // Use the full content rather than the delta for now.
        // The pi backend often sends a non-empty initial content on the '[text/reasoning]_start'
        // events that are duplicated on the following '[text/reasoning]_delta' events.
        // For now, the full content route makes this update a bit simpler and more robust.
        const newContent = update.partial.content[update.content_index];
        switch (newContent.type) {
            case 'text':
            case 'reasoning':
                break;
            default:
                throw new Error(
                    `Expected content corresponding to streaming text update to be of type text. Instead got ${newContent.type}`
                );
        }
        subView.syncContent(newContent.text);
    }

    private renderSubView(content: AssistantContent): AssistantSubView {
        switch (content.type) {
            case 'text':
                return new AssistantResponseView(content.text);

            case 'reasoning':
                return new ReasoningView(content.text);

            case 'tool_call':
                return new ToolCallView(content);

            default:
                content satisfies never;
                throw new Error(`Unsupported assistant content type: ${(content as any).type}`);
        }
    }
}

type AssistantSubView = ReasoningView | AssistantResponseView | ToolCallView;

class MutableContentView {
    readonly contentView: HTMLElement;

    constructor(initialContent: string) {
        this.contentView = div({
            class: style.message_text,
            text: initialContent
        });
    }

    syncContent(newContent: string) {
        this.contentView.textContent = newContent;
    }
}

class ReasoningView extends MutableContentView {
    readonly container: HTMLElement;

    constructor(reasoning: string) {
        super(reasoning);
        this.contentView.classList.add(style.reasoning);
        this.container = Collapsible.element({
            title: 'Reasoning',
            titleClass: style.message_title,
            content: this.contentView,
            isExpanded: true
        });
    }
}

class AssistantResponseView extends MutableContentView {
    readonly container: HTMLElement;

    constructor(response: string) {
        super(response);
        this.container = Collapsible.element({
            title: 'Assistant',
            titleClass: style.message_title,
            content: this.contentView,
            isExpanded: true
        });
    }
}

class ToolCallView {
    readonly container: HTMLElement;

    private detailsView?: ToolDetailsView;
    private result?: ToolResult;
    private statusIcon: HTMLElement;

    constructor(readonly toolCall: ToolCall) {
        this.statusIcon = div({
            class: style.tool_call_status_icon
        });

        this.container = Collapsible.element({
            headerContent: div({
                class: style.tool_call_header,
                children: [
                    span({ text: 'Tool: ', class: style.message_title }),
                    span({ text: toolCall.name, class: style.tool_call_name }),
                    this.statusIcon
                ]
            }),
            content: () => {
                // Lazily instantiate the details view.
                if (this.detailsView == null) {
                    this.detailsView = new ToolDetailsView(this.toolCall, this.result);
                }
                return this.detailsView.container;
            },
            isExpanded: false
        });
    }

    setResult(toolResult: ToolResult) {
        if (this.result != null) {
            throw new Error(`Tool result for call ID ${this.toolCall.id} has already been set.`);
        }
        this.result = toolResult;
        this.detailsView?.renderResults(toolResult);
        this.statusIcon.replaceChildren(makeIcon(toolResult.success ? 'Check' : 'Cross'));
        this.statusIcon.classList.toggle(style.failed, !toolResult.success);
    }
}

class ToolDetailsView {
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

        this.container = div({
            class: style.tool_call_details,
            children: [this.tabBar.container, this.tabView.container]
        });
    }

    renderResults(result: ToolResult) {
        if (this.resultView != null) {
            return;
        }
        let resultText = result.content?.text;
        if (resultText == null) {
            resultText = 'No output produced.';
        }
        if (result.internal_error) {
            resultText += '\n\nInternal Error:\n' + result.internal_error;
        }
        this.resultView = div({ text: resultText });
        this.tabView?.selectTabAtIndex(1);
    }

    getArgsView(): HTMLElement {
        if (!this.argsView) {
            this.argsView = renderJsonTree(this.toolCall.arguments);
        }
        return this.argsView;
    }

    getResultView(): HTMLElement {
        if (this.resultView == null) {
            return div({
                text: 'Tool result not yet available.'
            });
        }
        return this.resultView;
    }
}
