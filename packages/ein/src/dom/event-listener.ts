import type { Disposable } from '../disposable.js';

type EventTargetType = HTMLElement | Document | Window | EventTarget;

// Overload for HTML elements
export function listenForEvent<T extends HTMLElement, K extends keyof HTMLElementEventMap>(
    element: T,
    type: K,
    listener: (this: T, ev: HTMLElementEventMap[K]) => any,
    options?: boolean | AddEventListenerOptions
): Disposable;

// Overload for window
export function listenForEvent<K extends keyof WindowEventMap>(
    element: Document,
    type: K,
    listener: (this: Document, ev: WindowEventMap[K]) => any,
    options?: boolean | AddEventListenerOptions
): Disposable;

// Overload for document
export function listenForEvent<K extends keyof DocumentEventMap>(
    element: Window,
    type: K,
    listener: (this: Window, ev: DocumentEventMap[K]) => any,
    options?: boolean | AddEventListenerOptions
): Disposable;

// Overload for event sources
export function listenForEvent<EventType extends Event>(
    target: EventTarget,
    type: string,
    listener: (this: EventTarget, ev: EventType) => any,
    options?: boolean | AddEventListenerOptions
): Disposable;

// Implementation signature (not visible to external callers as per TypeScript spec)
export function listenForEvent(
    target: EventTargetType,
    type: string,
    listener: (this: EventTargetType, ev: Event) => any,
    options?: boolean | AddEventListenerOptions
): Disposable {
    target.addEventListener(type, listener, options);
    return {
        dispose: () => {
            target.removeEventListener(type, listener, options);
        }
    };
}
