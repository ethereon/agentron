export interface Disposable {
    dispose(): void;
}

export interface DisposableOwner {
    possessDisposable(disposable: Disposable): void;
}

export class DisposableStore implements Disposable, DisposableOwner {
    private _isDisposed = false;
    private disposables = new Set<Disposable>();

    dispose() {
        if (this._isDisposed) {
            console.warn(Error('Re-dispose attempt detected').stack);
            return;
        }
        this._isDisposed = true;
        this.clear();
    }

    clear() {
        this.disposables.forEach(disposable => disposable.dispose());
        this.disposables.clear();
    }

    add<T extends Disposable>(disposable: T): T {
        if (!this._isDisposed) {
            this.disposables.add(disposable);
        } else {
            console.warn(Error('Adding disposable to a disposed store').stack);
        }
        return disposable;
    }

    push(...disposables: Disposable[]) {
        disposables.forEach(disposable => this.add(disposable));
    }

    possessDisposable(disposable: Disposable) {
        this.add(disposable);
    }

    get size(): number {
        return this.disposables.size;
    }

    get isDisposed(): boolean {
        return this._isDisposed;
    }
}

export class DisposableSlot<T extends Disposable = Disposable>
    implements Disposable, DisposableOwner
{
    value: T | null = null;

    constructor(owner: DisposableOwner) {
        owner?.possessDisposable(this);
    }

    get isEmpty(): boolean {
        return this.value == null;
    }

    set(newValue: T | null): T | null {
        if (newValue !== this.value) {
            const priorValue = this.value;
            this.value = newValue;
            // Deliberately order priorValue.dispose() after the new value assignment,
            // so that priorValue may safely reference its own slot in its dispose.
            priorValue?.dispose();
        }
        return newValue;
    }

    clear() {
        this.set(null);
    }

    // Clears the slot without disposing off any prior value.
    disown(): T | null {
        const value = this.value;
        if (value != null) {
            this.value = null;
        }
        return value;
    }

    dispose() {
        this.set(null);
    }

    possessDisposable(disposable: T) {
        this.set(disposable);
    }
}

export class DisposableObject implements Disposable, DisposableOwner {
    declare private _disposables?: DisposableStore;
    declare private _disposablesTable?: Map<any, Disposable>;
    declare protected _isDisposed?: boolean;

    get disposables(): DisposableStore {
        let disposables = this._disposables;
        if (disposables === undefined) {
            disposables = this._disposables = new DisposableStore();
        }
        return disposables;
    }

    dispose() {
        if (this._isDisposed === true) {
            console.warn(`Over-dispose detected (${this.constructor.name})`);
            return;
        }
        this._isDisposed = true;
        if (this._disposablesTable !== undefined) {
            this._disposablesTable.forEach(disposable => disposable.dispose());
            this._disposablesTable.clear();
        }
        this._disposables?.dispose();
    }

    // Sets / replaces the disposable associated with the given key.
    // Any previously associated disposable is disposed.
    setDisposable(key: any, disposable: Disposable | null) {
        if (this._isDisposed) {
            console.warn('setDisposable called on disposed DisposableObject');
            disposable?.dispose();
            return;
        }
        if (this._disposablesTable == null) {
            this._disposablesTable = new Map();
        }
        this._disposablesTable.get(key)?.dispose();
        if (disposable) {
            this._disposablesTable.set(key, disposable);
        } else {
            this._disposablesTable.delete(key);
        }
    }

    getDisposable<T>(key: any): T {
        return this._disposablesTable?.get(key) as T;
    }

    possessDisposable(disposable: Disposable) {
        this.disposables.add(disposable);
    }

    get isDisposed(): boolean {
        return this._isDisposed ?? false;
    }
}

export class DisposableCollection<T extends Disposable> {
    constructor(public readonly items: T[]) {}

    dispose() {
        for (const item of this.items) {
            item.dispose();
        }
    }
}

export class RefCounted<T extends Disposable> implements Disposable {
    protected _count = 1;
    constructor(public readonly object: T) {}

    retain(): this {
        if (this.isDestroyed) {
            throw Error('Attempted retain on destroyed RefCounted object.');
        }
        this._count++;
        return this;
    }

    dispose() {
        this._count--;
        if (this._count === 0) {
            this.object.dispose();
            (this as any).object = undefined;
        } else if (this._count < 0) {
            console.warn('Over-release detected for RefCounted instance.');
        }
    }

    get isDestroyed(): boolean {
        return this._count <= 0;
    }
}

// A mutable reference to a disposable object that's auto-cleared when
// the referenced object is disposed.
export class WeakDisposableObject<T extends DisposableObject> {
    declare private _instance?: T;

    get exists(): boolean {
        return this._instance != null;
    }

    get instance(): T | undefined {
        return this._instance;
    }

    link(instance: T): T | undefined {
        if (instance.isDisposed) {
            console.warn('Weak reference to an already disposed object.');
            this.clear();
            return undefined;
        }

        this._instance = instance;
        instance.disposables.add({
            dispose: () => {
                if (this._instance === instance) {
                    this.clear();
                }
            }
        });

        return instance;
    }

    clear(): void {
        if (this._instance != null) {
            this._instance = undefined;
        }
    }
}

export class DisposableMap<K, V extends Disposable> implements Disposable {
    private readonly _map = new Map<K, V>();
    private _isDisposed = false;

    dispose() {
        if (this._isDisposed) {
            console.warn(Error('Re-dispose attempt detected').stack);
            return;
        }
        this._isDisposed = true;
        this.clear();
    }

    get(key: K): V | undefined {
        return this._map.get(key);
    }

    set(key: K, value: V): this {
        this._map.get(key)?.dispose();
        this._map.set(key, value);
        return this;
    }

    delete(key: K): boolean {
        const value = this._map.get(key);
        if (value == null) {
            return false;
        }
        value.dispose();
        this._map.delete(key);
        return true;
    }

    clear(): void {
        for (const item of this._map.values()) {
            item.dispose();
        }
        this._map.clear();
    }

    keys() {
        return this._map.keys();
    }

    values() {
        return this._map.values();
    }

    entries() {
        return this._map.entries();
    }

    has(key: K): boolean {
        return this._map.has(key);
    }

    get size(): number {
        return this._map.size;
    }

    rawMap(): Map<K, V> {
        return this._map;
    }

    [Symbol.iterator](): IterableIterator<[K, V]> {
        return this._map[Symbol.iterator]();
    }
}

// A disposable-friendly interruption flag.
//
// Example usage with a DisposableSlot:
//
//     this.activeSession = new DisposableSlot<Interruptible>(this);
//     ...
//     /* Create a new session flag. Interrupts any prior sessions. */
//     const session = this.activeSession.set(new Interruptible());
//     const result = await ....
//     if (session.isInterrupted) {
//         /* Either preempted, canceled or owner disposed. Bail out. */
//         ...
//     }
//
export class Interruptible implements Disposable {
    private _isInterrupted = false;

    get isInterrupted(): boolean {
        return this._isInterrupted;
    }

    interrupt(): void {
        this._isInterrupted = true;
    }

    // Auto-interrupt on dispose.
    // Safe to use without disposing though.
    dispose(): void {
        this.interrupt();
    }
}
