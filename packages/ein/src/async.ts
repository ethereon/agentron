interface RejectionRecord {
    index: number;
    value: any;
}

export interface BatchAsyncResult<T> {
    results: (T | null)[];
    rejections?: RejectionRecord[];
}

export function sleep(ms: number): Promise<void> {
    return new Promise<void>(resolve => setTimeout(resolve, ms));
}

export function animationSleep(ms: number): Promise<void> {
    let onDone: () => void;
    const delayPromise = new Promise<void>(resolve => (onDone = resolve));
    let startTime: number;
    const tick = (timestamp: number) => {
        if (startTime == null) {
            startTime = timestamp;
        } else if (timestamp - startTime >= ms) {
            onDone();
            return;
        }
        requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    return delayPromise;
}

const enum DeferredState {
    PENDING = 0,
    RESOLVED = 1,
    REJECTED = 2
}

export class Deferred<T = void> implements PromiseLike<T> {
    #state: DeferredState = DeferredState.PENDING;
    readonly #promise: Promise<T>;
    readonly #resolver: (value: T) => void;
    readonly #rejector: (reason: any) => void;

    constructor(public readonly name?: string) {
        const { promise, resolve, reject } = makePromise<T>();
        this.#promise = promise;
        this.#resolver = resolve;
        this.#rejector = reject;
    }

    resolve(value: T) {
        this.settle(this.#resolver, value, DeferredState.RESOLVED);
    }

    reject(reason?: any) {
        this.settle(this.#rejector, reason, DeferredState.REJECTED);
    }

    get hasSettled() {
        return this.#state !== DeferredState.PENDING;
    }

    get isRejected() {
        return this.#state === DeferredState.REJECTED;
    }

    get isResolved() {
        return this.#state === DeferredState.RESOLVED;
    }

    then<TResult1 = T, TResult2 = never>(
        onfulfilled?: ((value: T) => TResult1 | PromiseLike<TResult1>) | undefined | null,
        onrejected?: ((reason: any) => TResult2 | PromiseLike<TResult2>) | undefined | null
    ): PromiseLike<TResult1 | TResult2> {
        return this.#promise.then(onfulfilled, onrejected);
    }

    private settle<HandlerType extends Function, ArgType>(
        handler: HandlerType,
        arg: ArgType,
        state: DeferredState
    ) {
        if (this.hasSettled) {
            const name = this.name ?? '<anonymous>';
            throw Error(`Deferred instance "${name}" already settled.`);
        }
        this.#state = state;
        handler?.(arg);
    }
}

export class AsyncMutex {
    #lastPromise: Promise<void> = Promise.resolve();

    async lock(): Promise<() => void> {
        // Create a new promise that resolves on unlock
        let unlock: () => void;
        const thisPromise = new Promise<void>(resolve => {
            unlock = resolve;
        });

        // The next lock will need to await the completion of the promise above.
        const priorPromise = this.#lastPromise;
        this.#lastPromise = thisPromise;

        // "Acquire the lock" by waiting for the prior promise's completion.
        await priorPromise;

        // On resolution, the caller holds the lock until the unlock function is invoked.
        return unlock!;
    }
}

export interface AsyncQueueOptions {
    // Maximum number of queued tasks.
    // If provided, the queue will immediately reject new tasks once the limit is reached.
    // If unspecified, the queue has unlimited capacity.
    maxPending?: number;
}

export class AsyncQueueFullError extends Error {}

// Ensures that asyncs are executed sequentially in-order.
// Rejections of promises along the way do not interrupt the queue.
export class AsyncQueue {
    declare private prior?: Promise<void>;
    declare private count: number;
    declare private readonly maxPending: number;

    constructor(options?: AsyncQueueOptions) {
        this.count = 0;
        this.maxPending = options?.maxPending ?? -1;
    }

    // Schedules the function to be invoked once it's its turn.
    // Returns a promise that resolves to the produced promise's
    // fulfilled value.
    async enqueue<T>(asyncFunc: () => Promise<T>): Promise<T> {
        if (this.maxPending > 0 && this.count >= this.maxPending) {
            return Promise.reject(
                new AsyncQueueFullError(`Async queue limit reached (${this.maxPending})`)
            );
        }

        // Swap out prior
        let resolveThisTask: () => void;
        const taskPromise = new Promise<void>(resolve => (resolveThisTask = resolve));
        const prior = this.prior;
        this.prior = taskPromise;
        this.count++;

        // Wait for this task's turn
        if (prior != null) {
            await prior;
        }

        try {
            return await asyncFunc();
        } finally {
            resolveThisTask!();
            this.count--;
            // If there's nothing else in the queue, clear all state.
            if (this.prior === taskPromise) {
                this.prior = undefined;
            }
        }
    }

    get numPending(): number {
        return this.count;
    }
}

export async function* asFulfilled<T>(promises: Promise<T>[]): AsyncGenerator<T> {
    const neverSettled = new Promise(() => undefined);
    let offset = 0;

    while (offset < promises.length) {
        const indexedPromises: Promise<[number, T]>[] = [];
        for (let i = offset; i < promises.length; ++i) {
            const batchIndex = i - offset;
            indexedPromises.push(promises[i].then(value => [batchIndex, value]));
        }

        offset = promises.length;
        let numPending = indexedPromises.length;

        while (numPending > 0) {
            const [index, value] = await Promise.any(indexedPromises);
            indexedPromises[index] = neverSettled as any;
            yield value;
            --numPending;
        }
    }
}

export async function completionOfExtendablePromises<T>(promises: Promise<T>[]): Promise<T[]> {
    let offset = 0;
    const results: T[] = [];
    while (offset < promises.length) {
        const currentBatch = promises.slice(offset);
        results.push(...(await Promise.all(currentBatch)));
        offset += currentBatch.length;
    }
    return results;
}

export async function applyAsyncLimited<InputType, OutputType>(
    inputs: InputType[],
    maxConcurrent: number,
    func: (arg: InputType) => Promise<OutputType>
): Promise<BatchAsyncResult<OutputType>> {
    if (maxConcurrent <= 0) {
        throw Error(`Invalid value for maxConcurrent: ${maxConcurrent}`);
    }

    const activeTasks: Promise<void>[] = [];
    const results = Array<OutputType>(inputs.length);
    const numInputs = inputs.length;
    let rejections: RejectionRecord[] | undefined;

    for (let inputIndex = 0; inputIndex < numInputs; ++inputIndex) {
        // If at capacity, wait for something to complete.
        if (activeTasks.length >= maxConcurrent) {
            await Promise.race(activeTasks);
        }

        // Push new task
        const outputIndex = inputIndex;
        const task = func(inputs[inputIndex])
            .then(result => {
                // Set the output
                results[outputIndex] = result;
                // Remove from active tasks
                activeTasks.splice(activeTasks.indexOf(task), 1);
            })
            .catch(rejection => {
                // Record the rejection
                if (rejections == null) {
                    rejections = [];
                }
                rejections.push({ index: outputIndex, value: rejection });
                // Remove from active tasks
                activeTasks.splice(activeTasks.indexOf(task), 1);
            });
        activeTasks.push(task);
    }

    await Promise.all(activeTasks);

    return { results, rejections };
}

export async function guarded<T>(promise: Promise<T>): Promise<[T | null, Error | null]> {
    try {
        return [await promise, null];
    } catch (err) {
        return [null, err as Error];
    }
}

export async function ignoreErrors<T>(promise: Promise<T>): Promise<T | null> {
    try {
        return await promise;
    } catch (err) {
        return null;
    }
}

export class AsyncTaskTimeout extends Error {}

export async function withTimeout<T>(
    promise: Promise<T>,
    timeout: number,
    timeoutMessage?: string
): Promise<T> {
    return Promise.race([
        promise,
        sleep(timeout).then(() => {
            throw new AsyncTaskTimeout(timeoutMessage);
        })
    ]);
}

// NOTE(saumitro): Deprecate once Promise.withResolvers() is widely supported.
export function makePromise<T>(): {
    promise: Promise<T>;
    resolve: (value: T) => void;
    reject: (reason?: any) => void;
} {
    let resolve: (value: T) => void;
    let reject: (reason?: any) => void;
    const promise = new Promise<T>((_resolve, _reject) => {
        resolve = _resolve;
        reject = _reject;
    });
    return { promise, resolve: resolve!, reject: reject! };
}
