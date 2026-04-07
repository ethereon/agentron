type NullaryFunc = () => void;

type TimeoutHandle = NodeJS.Timeout | number;

// Invoke `func` after `delayMilliseconds` have passed since the last call.
// Each call restarts the delay timer.
export function debounce(delayMilliseconds: number, func: NullaryFunc): NullaryFunc {
    let timeoutHandle: TimeoutHandle | null = null;
    return () => {
        // Cancel any pending invocation
        if (timeoutHandle != null) {
            clearTimeout(timeoutHandle);
        }
        // Schedule a tentative invocation after delay
        timeoutHandle = setTimeout(() => func(), delayMilliseconds);
    };
}

// Invoke `func` once at the end of `delayMilliseconds`.
// Any additional calls during the delay period are skipped.
export function trailingThrottle(delayMilliseconds: number, func: NullaryFunc): NullaryFunc {
    let timeoutHandle: TimeoutHandle | null = null;
    return () => {
        // Only schedule if a prior invocation isn't already pending.
        if (timeoutHandle == null) {
            timeoutHandle = setTimeout(() => {
                func();
                timeoutHandle = null;
            }, delayMilliseconds);
        }
    };
}

// Invoke `func` immediately and then skip all calls until `delayMilliseconds` have passed.
// The throttled function forwards any given arguments to `func`, and returns either undefined
// (when `func` is not invoked) or the return value from `func`.
export function leadingThrottle<T extends (...args: any[]) => any>(
    delayMilliseconds: number,
    func: T
): (...args: Parameters<T>) => ReturnType<T> | undefined {
    let skip = false;
    return (...args: Parameters<T>) => {
        if (skip) {
            return;
        }
        // Immediately invoke and skip all further invocations until
        // the timeout is complete.
        skip = true;
        setTimeout(() => {
            skip = false;
        }, delayMilliseconds);
        return func(...args);
    };
}

// Invoke `func` immediately` and then coalesces and schedules any intermediate invocations
// to be spaced out by `delayMilliseconds` (unlike `leadingThrottle`, which entirely ignores
// any intermediate invocations).
export function spacedThrottle(delayMilliseconds: number, func: NullaryFunc): NullaryFunc {
    let skip = false;
    let scheduled = false;
    const throttled = () => {
        if (skip) {
            // Skip for now, but ensure an invocation is triggered at the end of the delay.
            if (!scheduled) {
                scheduled = true;
            }
            return;
        }
        // Immediately invoke and skip all further invocations until
        // the timeout is complete.
        skip = true;
        setTimeout(() => {
            skip = false;
            // If another invocation was scheduled during the delay,
            // trigger it now recursively (re-initiating a delay).
            if (scheduled) {
                scheduled = false;
                throttled();
            }
        }, delayMilliseconds);
        func();
    };
    return throttled;
}

// A more flexible version of `trailingThrottle`.
export class TrailingThrottler {
    declare private pending?: TimeoutHandle;

    constructor(
        private readonly delayMilliseconds: number,
        private readonly func: NullaryFunc
    ) {}

    schedule() {
        if (this.pending == null) {
            this.pending = setTimeout(() => {
                this.func();
                this.pending = undefined;
            }, this.delayMilliseconds);
        }
    }

    get isPending(): boolean {
        return this.pending != null;
    }

    // Cancels any scheduled invocation.
    // Returns true if a invocation was previously scheduled (and canceled),
    // and false otherwise (nothing scheduled).
    cancel(): boolean {
        if (this.pending != null) {
            clearTimeout(this.pending);
            this.pending = undefined;
            return true;
        }
        return false;
    }

    invokeImmediately(onlyIfPending: boolean): void {
        if (this.cancel() || !onlyIfPending) {
            this.func();
        }
    }
}

// Given a callback invoker (eg: requestAnimationFrame, scheduleRead, scheduleWrite, ...)
// and a callback function, returns a new nullary function that invokes the callback using
// the invoker only if no prior invocation is pending.
export function callbackBound(
    callbackInvoker: (func: NullaryFunc) => void,
    callback: NullaryFunc
): NullaryFunc {
    let isScheduled = false;
    const clearFlagAndInvokeCallback = () => {
        isScheduled = false;
        callback();
    };
    return () => {
        if (!isScheduled) {
            isScheduled = true;
            callbackInvoker(clearFlagAndInvokeCallback);
        }
    };
}

// NOTE: You very likely want to explicitly specify a timeout option here.
// See: https://developer.mozilla.org/en-US/docs/Web/API/Background_Tasks_API
export function idleCallbackBound(func: NullaryFunc, options: IdleRequestOptions): NullaryFunc {
    return callbackBound(callback => requestIdleCallback(callback, options), func);
}
