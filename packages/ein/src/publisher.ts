import type { Disposable, DisposableOwner } from './disposable.js';

class Subscription<MessageType = unknown> implements Disposable {
    constructor(private publisher: Publisher<MessageType>) {}

    dispose() {
        if (this.publisher != null) {
            this.publisher.remove(this);
            (this as any).publisher = null;
        }
    }
}

export type Subscriber<MessageType> = (message: MessageType) => void;

export class Publisher<MessageType = void> implements Disposable {
    private subscriptions = new Map<Subscription<MessageType>, Subscriber<MessageType>>();

    constructor(owner: DisposableOwner | null) {
        owner?.possessDisposable(this);
    }

    subscribe(subscriber: Subscriber<MessageType>): Disposable {
        if (this.subscriptions == null) {
            throw Error('Attempted to subscribe to a disposed publisher.');
        }
        const subscription = new Subscription(this);
        this.subscriptions.set(subscription, subscriber);
        return subscription;
    }

    // Adds a subscriber that receives at most one message from this publisher.
    // The subscriber is auto-removed after a single message has been delivered.
    once(subscriber: Subscriber<MessageType>): Disposable {
        // There's an edge case here that needs to be guarded against:
        // It's possible for the subscribe invocation to trigger immediately.
        // For instance, calling once on an Observable with a current value.
        // If we were to directly assign `const sub = this.subscribe(...)`, the sub variable
        // would be uninitialized in the callback. As a mitigation, we pre-initialize it
        // and introduce an explicit flag to track the disposed-before-assignment case.
        let sub: Disposable | undefined = undefined;
        let disposed = false;

        sub = this.subscribe(msg => {
            sub?.dispose();
            disposed = true;
            subscriber(msg);
        });

        if (disposed) {
            // Implies the subscription callback was invoked immediately on subscribe.
            sub!.dispose();
        }
        return sub!;
    }

    publish(message: MessageType): void {
        if (this.subscriptions != null) {
            for (const subscriber of this.subscriptions.values()) {
                subscriber(message);
            }
        }
    }

    remove(subscription: Subscription<MessageType>): void {
        if (this.subscriptions != null) {
            this.subscriptions.delete(subscription);
        }
    }

    dispose(): void {
        if (this.subscriptions != null) {
            for (let subscription of this.subscriptions.keys()) {
                subscription.dispose();
            }
            (this as any).subscriptions = null;
        }
    }

    get subscriptionCount(): number {
        return this.subscriptions.size;
    }
}

export class Observable<ValueType> extends Publisher<ValueType> {
    protected _value?: ValueType;

    constructor(owner: DisposableOwner, initialValue?: ValueType) {
        super(owner);
        if (initialValue !== undefined) {
            this.set(initialValue);
        }
    }

    override publish(value: ValueType) {
        this.set(value);
        super.publish(value);
    }

    override subscribe(subscriber: Subscriber<ValueType>): Disposable {
        if (this._value !== undefined) {
            subscriber(this._value);
        }
        return super.subscribe(subscriber);
    }

    // Subscribe without being notified of the current value (similar to Publisher's default behavior)
    subscribeFuture(subscriber: Subscriber<ValueType>): Disposable {
        return super.subscribe(subscriber);
    }

    // Changes the value to undefined without publishing.
    clear(): void {
        this.set(undefined);
    }

    get value(): ValueType | undefined {
        return this._value;
    }

    protected set(value: ValueType | undefined): void {
        this._value = value;
    }
}

// An Observable for Disposable value types.
// The observable owns value and auto-disposes it whenever a new value is set,
// essentially acting as a combined Observable and DisposableSlot.
export class ObservableDisposable<
    ValueType extends Disposable | undefined | null
> extends Observable<ValueType> {
    override dispose(): void {
        this.clear();
        super.dispose();
    }

    protected override set(value: ValueType | undefined): void {
        if (this._value != null && this._value !== value) {
            this._value.dispose();
        }
        super.set(value);
    }
}
