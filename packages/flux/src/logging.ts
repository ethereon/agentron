import { type Disposable, DisposableObject, DisposableStore } from '@ethereon/ein/disposable';
import { Publisher } from '@ethereon/ein/publisher';
import { inspect } from 'node:util';

export const enum LogLevel {
    DEBUG,
    INFO,
    WARNING,
    ERROR
}

export interface LogFlags {
    skipConsole?: boolean;
    coalesce?: boolean;
}

export type LogPersistenceLevel = LogLevel | null;

export interface LogMessage {
    text: string;
    level: LogLevel;
    count?: number;
}

const enum Limits {
    MAX_MESSAGES = 5_000
}

type LoggerHook = (logger: Logger) => void;

// Global state
const loggerTable = new Map<string, Logger>();
const loggerHooks = new Set<LoggerHook>();

interface LoggerParams {
    key: string;
    name?: string;
    flags?: LogFlags;
}

export class Logger extends DisposableObject {
    static stuff: number[] = [];

    public readonly key: string;
    public readonly name: string;
    public readonly flags: LogFlags;
    public readonly messages: LogMessage[] = [];
    public readonly onNewMessage = new Publisher<LogMessage>(this);

    // The total number of messages (including those that have been pruned).
    public totalMessages = 0;

    private minPersistenceLevel: number = LogLevel.INFO;

    protected constructor(params: LoggerParams) {
        super();
        this.key = params.key;
        this.name = params.name ?? params.key;
        this.flags = params.flags ?? {};

        DEV_MODE: this.minPersistenceLevel = LogLevel.DEBUG;

        Logger.register(this);
    }

    static get(params: LoggerParams): Logger {
        let logger = loggerTable.get(params.key);
        if (logger == null) {
            logger = new this(params);
        }
        return logger;
    }

    static register(logger: Logger) {
        if (logger.key == null) {
            throw Error('Logger has null key');
        }
        loggerTable.set(logger.key, logger);

        for (const hook of loggerHooks) {
            hook(logger);
        }
    }

    static all(): IterableIterator<Logger> {
        return loggerTable.values();
    }

    // Registers a callback that's invoked for all existing
    // and future loggers.
    // Returns a disposable for removing the hook.
    static registerHook(hook: LoggerHook): Disposable {
        loggerHooks.add(hook);
        for (const logger of this.all()) {
            hook(logger);
        }
        return {
            dispose: () => {
                loggerHooks.delete(hook);
            }
        };
    }

    static createConsoleLoggingLookupTable(): Array<typeof console.log> {
        const lut: Array<typeof console.log> = [];
        lut[LogLevel.DEBUG] = console.debug;
        lut[LogLevel.INFO] = console.log;
        lut[LogLevel.WARNING] = console.warn;
        lut[LogLevel.ERROR] = console.error;
        return lut;
    }

    static registerLogToConsoleHook(
        minLevel: LogLevel,
        formatter?: (msg: LogMessage) => string
    ): Disposable {
        // LUT from logging levels -> console logging functions
        const lut = Logger.createConsoleLoggingLookupTable();

        // Message formatter
        const format: (msg: LogMessage) => string =
            // User provided formatter
            formatter ??
            // Default formatter
            (msg => msg.text);

        // Hook for logging to console
        const outputToConsole = (msg: LogMessage) => {
            if (msg.level >= minLevel) {
                lut[msg.level](format(msg));
            }
        };
        const disposables = new DisposableStore();
        disposables.add(
            Logger.registerHook(logger => {
                // Guard against infinite recursion when dealing with loggers
                // that capture console output (eg: ConsoleToLogHook).
                if (logger.flags.skipConsole !== true) {
                    disposables.add(logger.onNewMessage.subscribe(outputToConsole));
                }
            })
        );
        return disposables;
    }

    static registerConsoleToLogHook(minLevel: LogLevel, logger: Logger): void {
        if (logger.flags.skipConsole !== true) {
            throw Error('Console logger must have skipConsole flag set to true.');
        }

        const capture = (funcName: 'error' | 'warn' | 'log' | 'debug', level: LogLevel) => {
            const original = console[funcName];
            logger.disposables.add({
                dispose: () => {
                    console[funcName] = original;
                }
            });
            return function (...args: any[]) {
                // Call the original console function
                original.apply(console, args);
                // Route to the logger as well
                logger.push(args, level);
            };
        };

        switch (minLevel) {
            case LogLevel.DEBUG:
                console.debug = capture('debug', LogLevel.DEBUG);
            // Fallthrough

            case LogLevel.INFO:
                console.log = capture('log', LogLevel.INFO);
            // Fallthrough

            case LogLevel.WARNING:
                console.warn = capture('warn', LogLevel.WARNING);
            // Fallthrough

            case LogLevel.ERROR:
                console.error = capture('error', LogLevel.ERROR);
        }
    }

    debug(...args: any[]): void {
        this.push(args, LogLevel.DEBUG);
    }

    info(...args: any[]): void {
        this.push(args, LogLevel.INFO);
    }

    warn(...args: any[]): void {
        this.push(args, LogLevel.WARNING);
    }

    error(...args: any[]): void {
        this.push(args, LogLevel.ERROR);
    }

    inconsistency(...args: any[]): void {
        this.push(args, LogLevel.ERROR);
    }

    // Identical to info.
    // Preserved for loggers that require compatibility with a console interface.
    log(...args: any[]): void {
        this.push(args, LogLevel.INFO);
    }

    push(args: any[], level: LogLevel) {
        const msg = { text: format(args), level };
        if (level >= this.minPersistenceLevel) {
            if (this.flags.coalesce !== true || !this.maybeCoalesce(msg)) {
                this.messages.push(msg);
                this.totalMessages++;
                if (this.messages.length > Limits.MAX_MESSAGES) {
                    this.messages.shift();
                }
            }
        }
        this.onNewMessage.publish(msg);
    }

    // Passing `null` effectively prevents all persistence.
    setMinPersistenceLevel(level: LogPersistenceLevel) {
        this.minPersistenceLevel = level ?? LogLevel.ERROR + 1;
    }

    // Returns a log-like object whose methods auto-prefix all messages.
    prefixed(prefix: string) {
        const makePrefixed = (logFunc: (...args: any[]) => void) => {
            logFunc = logFunc.bind(this);
            return (...args: any[]) => {
                logFunc(prefix + format(args));
            };
        };

        return {
            debug: makePrefixed(this.debug),
            log: makePrefixed(this.log),
            info: makePrefixed(this.info),
            warn: makePrefixed(this.warn),
            error: makePrefixed(this.error),
            inconsistency: makePrefixed(this.inconsistency)
        };
    }

    private maybeCoalesce(msg: LogMessage): boolean {
        const lastMessage = this.messages[this.messages.length - 1];
        if (
            lastMessage != null &&
            lastMessage.level === msg.level &&
            lastMessage.text === msg.text
        ) {
            lastMessage.count = (lastMessage.count ?? 1) + 1;
            return true;
        }
        return false;
    }
}

export function format(args: any[]): string {
    const numArgs = args.length;
    if (numArgs === 0) {
        return '';
    }

    const firstArg = args[0];
    if (typeof firstArg === 'string') {
        switch (numArgs) {
            case 1:
                // Fast path: single string arg
                return firstArg;

            case 2:
                // Fast path: string + single other arg
                return `${firstArg} ${inspect(args[1])}`;

            default:
                return `${firstArg} ${inspect(args.slice(1))}`;
        }
    }

    return inspect(numArgs === 1 ? firstArg : args);
}

export const log = Logger.get({
    key: 'core',
    name: 'Main'
});
