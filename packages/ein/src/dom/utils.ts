interface MakeElementOptions {
    // Class names (mutually exclusive)
    class?: string;
    classes?: string[];

    // Contents (mutually exclusive)
    child?: Node;
    children?: Array<Node>;
    text?: string;
}

interface MakeButtonOptions extends MakeElementOptions {
    onClick?: () => void;
}

export function make<K extends keyof HTMLElementTagNameMap>(
    element: K,
    options: MakeElementOptions
): HTMLElementTagNameMap[K] {
    const elem = document.createElement(element);

    // Class names
    if (options.class) {
        elem.className = options.class;
    } else if (options.classes) {
        elem.classList.add(...options.classes);
    }

    // Children
    if (options.child) {
        elem.appendChild(options.child);
    } else if (options.children) {
        elem.append(...options.children);
    } else if (options.text) {
        elem.textContent = options.text;
    }

    return elem;
}

export function div(options: MakeElementOptions): HTMLDivElement {
    return make('div', options);
}

export function span(options: MakeElementOptions): HTMLSpanElement {
    return make('span', options);
}

export function textNode(text: string): Text {
    return document.createTextNode(text);
}

export function emptyNode(): Node {
    return document.createTextNode('');
}

export function button(options: MakeButtonOptions): HTMLButtonElement {
    const btn = make('button', options);
    if (options.onClick) {
        btn.onclick = options.onClick;
    }
    return btn;
}

export function updateTextContent(node: Node, text: string): boolean {
    if (text == null) {
        text = '';
    }
    if (node.textContent !== text) {
        node.textContent = text;
        return true;
    }
    return false;
}

export function setOnlyChild(parent: HTMLElement, child: Node | null): void {
    if (child != null) {
        parent.replaceChildren(child);
    } else {
        parent.replaceChildren();
    }
}

export function withClass<T extends Element>(node: T, ...classNames: string[]): T {
    node.classList.add(...classNames);
    return node;
}

export function clickable<T extends HTMLElement>(node: T, onclick: () => void): T {
    node.onclick = onclick;
    return node;
}

interface RunWhenConnectedParams {
    element: HTMLElement;

    // Defaults to 5
    maxFramesToWait?: number;

    // Whether to defer for a frame even when the element is connected.
    // Defaults to false.
    alwaysDefer?: boolean;
}

export function runWhenConnected(params: RunWhenConnectedParams, callback: () => void): void {
    _runWhenConnected(
        params.element,
        params.maxFramesToWait ?? 5,
        params.alwaysDefer ?? false,
        callback
    );
}

function _runWhenConnected(
    element: HTMLElement,
    maxFramesToWait: number,
    alwaysDefer: boolean,
    func: () => void
): void {
    if (element.isConnected && !alwaysDefer) {
        func();
    } else if (maxFramesToWait > 0) {
        requestAnimationFrame(() => _runWhenConnected(element, maxFramesToWait - 1, false, func));
    }
}

export function isCurrentFocusTrivial(): boolean {
    return Boolean(
        // Body is the fallback/default active element
        document.activeElement === document.body &&
        // Ensure no text selection exists: don't want to interrupt the
        // selection (which can occur even when the active element is body).
        document.getSelection()?.isCollapsed
    );
}

export function classNames(...candidates: Array<string | false>): string {
    return candidates.filter(x => Boolean(x)).join(' ');
}
