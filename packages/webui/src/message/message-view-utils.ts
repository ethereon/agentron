import * as style from '../gen/styles/message.js';

import { div } from '@ethereon/ein/dom/utils';
import { Collapsible, CollapsibleParams } from '../components/collapsible/collapsible.js';

const enum Limits {
    MAX_PREVIEW_LENGTH = 80
}

export function makeCollapsibleMessageElement(params: CollapsibleParams): HTMLElement {
    return makeCollapsibleMessage(params).container;
}

export function makeCollapsibleMessage(params: CollapsibleParams): Collapsible {
    const collapsible = new Collapsible(params);
    const sourceContent = params.content;
    if (!(sourceContent instanceof HTMLElement)) {
        throw new Error('Collapsible content must be an HTMLElement.');
    }

    let previewSet = false;
    const preview = div({
        class: style.message_preview
    });
    const onExpansionChange = (isExpanded: boolean) => {
        // Hide preview when expanded
        preview.style.display = isExpanded ? 'none' : '';

        // Auto-set preview based on the content
        if (!isExpanded && !previewSet) {
            const textContent = sourceContent.textContent;
            if (textContent != null) {
                const previewText = makePreviewSnippet(textContent);
                if (previewText.length > 0) {
                    preview.textContent = previewText;
                    previewSet = true;
                }
            }
        }
    };
    collapsible.header.appendChild(preview);
    collapsible.onExpansionChange = onExpansionChange;
    onExpansionChange(collapsible.isExpanded);

    return collapsible;
}

export function makePreviewSnippet(content: string): string {
    let previewText = content.trim().split('\n', 1)[0].trim();
    if (previewText.length > Limits.MAX_PREVIEW_LENGTH) {
        previewText = previewText.slice(0, Limits.MAX_PREVIEW_LENGTH);
    }
    if (previewText.length > 0) {
        return `${previewText}${previewText.length < content.length ? '…' : ''}`;
    }
    return previewText;
}
