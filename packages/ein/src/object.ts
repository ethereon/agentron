const hasOwnProperty = Object.prototype.hasOwnProperty;

export function clone<T>(src: Readonly<T>, ...substitutions: Readonly<Partial<T>>[]): T {
    return Object.assign({}, src, ...substitutions);
}

// This utility has a few advantages over using Object.assign.
// In particular, it ensures the substitution is a valid Partial<T> while Object.assign does not.
// It also clearly specifies intent and is explicitly designed for the single mandatory substition case.
// For a zero or more substitution variant, clone may be used instead.
export function substitute<T>(src: T, substitution: Partial<T>): T {
    return Object.assign({}, src, substitution);
}

export function isShallowEqual<T>(a: T, b: T): boolean {
    if (Object.is(a, b)) {
        return true;
    }
    if (typeof a !== 'object' || a === null || typeof b !== 'object' || b === null) {
        return false;
    }
    const keysA = Object.keys(a);
    const keysB = Object.keys(b);
    const numKeys = keysA.length;
    if (numKeys !== keysB.length) {
        return false;
    }
    for (let i = 0; i < numKeys; ++i) {
        const key = keysA[i];
        if (!hasOwnProperty.call(a, key) || !Object.is((a as any)[key], (b as any)[key])) {
            return false;
        }
    }
    return true;
}

export function isDeepEqual<T extends object>(a: T, b: T): boolean {
    if (Object.is(a, b)) {
        return true;
    }
    if (typeof a !== 'object' || a === null || typeof b !== 'object' || b === null) {
        return false;
    }
    const keysA = Object.keys(a);
    const keysB = Object.keys(b);
    const numKeys = keysA.length;
    if (numKeys !== keysB.length) {
        return false;
    }
    for (let i = 0; i < numKeys; ++i) {
        const key = keysA[i];
        if (!hasOwnProperty.call(a, key) || !isDeepEqual((a as any)[key], (b as any)[key])) {
            return false;
        }
    }
    return true;
}
