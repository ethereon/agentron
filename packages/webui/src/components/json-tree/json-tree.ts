import * as style from '../../gen/styles/components/json-tree.js';

import { div, span } from '@ethereon/ein/dom/utils';
import { Collapsible } from '../collapsible/collapsible.js';

type JsonCollection = Array<unknown> | Record<string, unknown>;

interface RenderJsonTreeParams {
    // If true, skips rendering a solitary root node (when it's a collection)
    // So instead this:
    //      <object>
    //          <key>: <value>
    // you get this:
    //      <key>: <value>
    unwrapRoot?: boolean;
}

export function renderJsonTree(value: unknown, options?: RenderJsonTreeParams): HTMLElement {
    const unwrapRoot = options?.unwrapRoot ?? false;
    const tree = isCollection(value)
        ? renderCollection(value, undefined, true, unwrapRoot)
        : renderPrimitive(undefined, value);
    tree.classList.add(style.json_tree);

    if (unwrapRoot) {
        tree.classList.add(style.json_tree_root_collection);
    }

    return tree;
}

function isCollection(value: unknown): value is JsonCollection {
    return Array.isArray(value) || isObject(value);
}

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function renderCollection(
    value: JsonCollection,
    label?: string,
    isRoot = false,
    unwrapped = false
): HTMLElement {
    const content = div({
        class: style.json_tree_collection
    });

    if (Array.isArray(value)) {
        if (value.length === 0) {
            content.appendChild(div({ text: '[]' }));
        } else {
            value.forEach((item, index) => content.appendChild(renderEntry(`[${index}]`, item)));
        }
    } else {
        const entries = Object.entries(value);
        if (entries.length === 0) {
            content.appendChild(div({ text: '{}' }));
        } else {
            for (const [key, item] of entries) {
                content.appendChild(renderEntry(key, item));
            }
        }
    }

    return unwrapped
        ? content
        : Collapsible.element({
              headerContent: buildCollectionTitle(label, value),
              content,
              isExpanded: isRoot
          });
}

function renderEntry(label: string, value: unknown): HTMLElement {
    if (isCollection(value)) {
        return renderCollection(value, label);
    }
    return renderPrimitive(label, value);
}

function renderPrimitive(label: string | undefined, value: unknown): HTMLElement {
    const text = formatPrimitive(value);
    if (!label) {
        return div({
            text
        });
    }
    return div({
        class: style.json_tree_pair,
        children: [
            div({ class: style.json_tree_label, text: `${label}: ` }),
            div({
                class: style.json_tree_primitive,
                text
            })
        ]
    });
}

function formatPrimitive(value: unknown): string {
    switch (typeof value) {
        case 'string':
            return value.length > 50 || value.includes('\n') ? value : JSON.stringify(value);

        case 'number':
        case 'boolean':
        case 'bigint':
            return String(value);

        case 'undefined':
            return 'undefined';

        case 'function':
            return '[function]';

        case 'symbol':
            return String(value);

        case 'object':
            return value === null ? 'null' : '[unsupported object]';

        default:
            return String(value);
    }
}

function buildCollectionTitle(label: string | undefined, value: JsonCollection): HTMLElement {
    let typeName: string;
    let count: number;
    if (Array.isArray(value)) {
        typeName = 'Array';
        count = value.length;
    } else {
        typeName = 'Object';
        count = Object.keys(value).length;
    }
    const children: HTMLElement[] = [
        span({ text: typeName }),
        span({ text: `  (${count})`, class: style.json_tree_count })
    ];
    if (label) {
        children.unshift(span({ text: `${label}: `, class: style.json_tree_label }));
    }
    return div({ children });
}
