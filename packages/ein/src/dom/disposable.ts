import { type Disposable, DisposableObject } from '../disposable.js';

// An HTML element wrapped in a disposable interface.
export interface DisposableElement<
    ElementType extends HTMLElement = HTMLElement
> extends Disposable {
    container: ElementType;
}

export type DisposableDiv = DisposableElement<HTMLDivElement>;

export class DisposableElementSlot<
    ChildType extends DisposableElement = DisposableElement
> implements Disposable {
    private _child?: ChildType;

    constructor(public readonly parent: HTMLElement) {}

    get value(): ChildType | undefined {
        return this._child;
    }

    set value(newChild: ChildType | undefined | null) {
        if (newChild === this._child) {
            return;
        }
        if (newChild == null) {
            this.clear();
            return;
        }
        const newContainer = newChild.container;
        if (newContainer == null) {
            console.error('null child container detected.');
            return;
        }
        if (this._child?.container != null) {
            this.parent.replaceChild(newContainer, this._child.container);
            this._child.dispose();
        } else {
            this.parent.appendChild(newContainer);
        }
        this._child = newChild;
    }

    clear() {
        this._child?.dispose?.();
        this._child = undefined;
        this.parent.replaceChildren();
    }

    dispose() {
        this._child?.dispose?.();
        this._child = undefined;
    }
}

export class DisposableElementParent<ChildType extends DisposableElement = DisposableElement>
    extends DisposableObject
    implements DisposableDiv
{
    readonly container: HTMLDivElement;

    private readonly _content: DisposableElementSlot<ChildType>;

    constructor() {
        super();
        this.container = document.createElement('div');
        this._content = new DisposableElementSlot(this.container);
    }

    set content(newContent: ChildType | undefined | null) {
        this._content.value = newContent;
    }

    get content(): ChildType | undefined {
        return this._content.value;
    }

    override dispose() {
        this._content.dispose();
        super.dispose();
    }
}

function noOp() {}

export function asDisposableElement<ElemType extends HTMLElement>(
    container: ElemType
): DisposableElement<ElemType> {
    return { container, dispose: noOp };
}
