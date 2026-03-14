import * as net from 'node:net';
import * as fs from 'node:fs';
import * as path from 'node:path';

import { EventEmitter } from 'node:events';

export interface RpcRequest {
    id: string | number;
    method: string;
    params?: unknown[];
}

export interface RpcResponse {
    id: string | number | null;
    result?: unknown;
    error?: RpcError;
}

export interface RpcNotification {
    method: string;
    params?: unknown[];
}

export interface RpcError {
    code: number;
    message: string;
    data?: unknown;
}

export type RpcHandler = (...args: any[]) => any;

interface RpcHandlerOptions {
    wantsSocket?: boolean;
}

interface RpcHandlerEntry {
    handler: RpcHandler;
    options?: RpcHandlerOptions;
}

export interface RpcServerOptions {
    /** Path to the Unix domain socket file. */
    socketPath: string;
    /** Maximum number of pending connections in the backlog queue (default: 128). */
    backlog?: number;
    /** If true, an existing socket file will be removed before binding (default: true). */
    removeExistingSocket?: boolean;
    /** Timeout in milliseconds for a single method call (default: 30_000). */
    methodTimeout?: number;
}

// Error Codes (JSON-RPC 2.0 compatible)
export const RpcErrorCode = {
    PARSE_ERROR: -32700,
    INVALID_REQUEST: -32600,
    METHOD_NOT_FOUND: -32601,
    INVALID_PARAMS: -32602,
    INTERNAL_ERROR: -32603,
    SERVER_ERROR: -32000,
    TIMEOUT: -32001
} as const;

// A JSON-RPC–style server that communicates over a Unix domain socket.
// Handlers are registered by calling `this.register(name, fn)` and then
// `start()` is called to begin accepting connections.
//
// Wire format: newline-delimited JSON  (each message is one UTF-8 line).
//
// Example:
// ```ts
// class MathServer extends UnixRpcServer {
//   constructor() {
//     super({ socketPath: "/tmp/math.sock" });
//     this.register("add", (a: unknown, b: unknown) => (a as number) + (b as number));
//   }
// }
//
// const server = new MathServer();
// await server.start();
// ```
export class UnixRpcServer extends EventEmitter {
    protected readonly socketPath: string;
    private readonly backlog: number;
    private readonly removeExistingSocket: boolean;
    private readonly methodTimeout: number;

    private server: net.Server | null = null;
    private readonly handlers = new Map<string, RpcHandlerEntry>();
    private readonly activeConnections = new Set<net.Socket>();

    constructor(options: RpcServerOptions) {
        super();
        this.socketPath = options.socketPath;
        this.backlog = options.backlog ?? 128;
        this.removeExistingSocket = options.removeExistingSocket ?? true;
        this.methodTimeout = options.methodTimeout ?? 30_000;
    }

    // Register a named RPC method.  The handler may be synchronous or async.
    // Re-registering an existing name overwrites the previous handler.
    register(method: string, handler: RpcHandler, options?: RpcHandlerOptions): void {
        this.handlers.set(method, { handler, options });
    }

    // Remove a previously registered method.
    unregister(method: string): boolean {
        return this.handlers.delete(method);
    }

    // Returns the names of all currently registered methods.
    get registeredMethods(): string[] {
        return [...this.handlers.keys()];
    }

    // Start listening on the configured socket path.
    async start(): Promise<void> {
        if (this.server) {
            throw new Error('Server is already running');
        }

        await this.ensureSocketDirectory();

        if (this.removeExistingSocket) {
            await this.removeSocketFile();
        }

        return new Promise((resolve, reject) => {
            this.server = net.createServer(socket => this.onConnection(socket));

            this.server.on('error', err => {
                this.emit('error', err);
                reject(err);
            });

            this.server.listen({ path: this.socketPath, backlog: this.backlog }, () => {
                this.emit('listening', this.socketPath);
                resolve();
            });
        });
    }

    // Gracefully stop the server and close all active connections.
    async stop(): Promise<void> {
        if (!this.server) {
            return;
        }

        // Destroy all active client sockets immediately.
        for (const socket of this.activeConnections) {
            socket.destroy();
        }
        this.activeConnections.clear();

        return new Promise((resolve, reject) => {
            this.server!.close(err => {
                this.server = null;
                if (err) {
                    reject(err);
                } else {
                    this.emit('close');
                    resolve();
                }
            });
        });
    }

    get isListening(): boolean {
        return this.server?.listening ?? false;
    }

    // Send a JSON-RPC notification to a specific connected client.
    notify(socket: net.Socket, method: string, params: unknown[] = []): void {
        this.sendNotification(socket, { method, params });
    }

    // Broadcast a JSON-RPC notification to all currently connected clients.
    // Returns the number of clients the notification was attempted for.
    notifyAll(method: string, params: unknown[] = []): number {
        let sentCount = 0;
        for (const socket of this.activeConnections) {
            this.sendNotification(socket, { method, params });
            sentCount += 1;
        }
        return sentCount;
    }

    private onConnection(socket: net.Socket): void {
        this.activeConnections.add(socket);
        this.emit('connection', socket);

        let buffer = '';

        socket.setEncoding('utf8');

        socket.on('data', (chunk: string) => {
            buffer += chunk;
            const lines = buffer.split('\n');
            // Keep the last (possibly incomplete) line in the buffer.
            buffer = lines.pop() ?? '';

            for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed.length > 0) {
                    this.handleLine(trimmed, socket);
                }
            }
        });

        socket.on('error', err => {
            this.emit('clientError', err, socket);
            this.activeConnections.delete(socket);
        });

        socket.on('close', () => {
            this.activeConnections.delete(socket);
            this.emit('clientDisconnect', socket);
        });
    }

    private handleLine(line: string, socket: net.Socket): void {
        let request: RpcRequest;

        try {
            request = JSON.parse(line) as RpcRequest;
        } catch {
            this.sendResponse(socket, {
                id: null,
                error: {
                    code: RpcErrorCode.PARSE_ERROR,
                    message: 'Parse error: invalid JSON'
                }
            });
            return;
        }

        if (!this.isValidRequest(request)) {
            this.sendResponse(socket, {
                id: (request as Partial<RpcRequest>).id ?? null,
                error: {
                    code: RpcErrorCode.INVALID_REQUEST,
                    message: 'Invalid request: missing required fields'
                }
            });
            return;
        }

        // Coerce params to an array if it's a single value, for convenience.
        if (request.params && !Array.isArray(request.params)) {
            request.params = [request.params];
        }

        this.dispatchRequest(request, socket);
    }

    private dispatchRequest(request: RpcRequest, socket: net.Socket): void {
        const { id, method, params = [] } = request;
        const handlerEntry = this.handlers.get(method);

        if (!handlerEntry) {
            this.sendResponse(socket, {
                id,
                error: {
                    code: RpcErrorCode.METHOD_NOT_FOUND,
                    message: `Method not found: "${method}"`
                }
            });
            return;
        }
        const handler = handlerEntry.handler;
        if (handlerEntry.options?.wantsSocket) {
            params.unshift(socket);
        }

        const timeoutHandle = setTimeout(() => {
            this.sendResponse(socket, {
                id,
                error: {
                    code: RpcErrorCode.TIMEOUT,
                    message: `Method "${method}" timed out after ${this.methodTimeout}ms`
                }
            });
        }, this.methodTimeout);

        const callHandler = async (): Promise<void> => {
            try {
                const result = await Promise.resolve(handler(...params));
                clearTimeout(timeoutHandle);
                this.sendResponse(socket, { id, result });
            } catch (err: unknown) {
                clearTimeout(timeoutHandle);
                this.sendResponse(socket, {
                    id,
                    error: this.normalizeError(err)
                });
            }
        };

        callHandler().catch(err => this.emit('error', err));
    }

    private sendResponse(socket: net.Socket, response: RpcResponse): void {
        if (socket.destroyed || socket.writableEnded) return;
        try {
            socket.write(JSON.stringify(response) + '\n', 'utf8');
        } catch (err) {
            this.emit('error', err);
        }
    }

    private sendNotification(socket: net.Socket, notification: RpcNotification): void {
        if (socket.destroyed || socket.writableEnded) return;
        try {
            socket.write(JSON.stringify(notification) + '\n', 'utf8');
        } catch (err) {
            this.emit('error', err);
        }
    }

    private isValidRequest(req: unknown): req is RpcRequest {
        if (typeof req !== 'object' || req === null) {
            return false;
        }
        const r = req as Record<string, unknown>;
        const hasId =
            typeof r['id'] === 'string' || typeof r['id'] === 'number' || r['id'] === null;
        const hasMethod = typeof r['method'] === 'string' && r['method'].length > 0;
        return hasId && hasMethod;
    }

    private normalizeError(err: unknown): RpcError {
        if (err instanceof Error) {
            return {
                code: RpcErrorCode.SERVER_ERROR,
                message: err.message,
                data: err.stack
            };
        }
        return {
            code: RpcErrorCode.INTERNAL_ERROR,
            message: 'An unexpected error occurred',
            data: String(err)
        };
    }

    private async ensureSocketDirectory(): Promise<void> {
        const dir = path.dirname(this.socketPath);
        await fs.promises.mkdir(dir, { recursive: true });
    }

    private async removeSocketFile(): Promise<void> {
        try {
            await fs.promises.unlink(this.socketPath);
        } catch (err: unknown) {
            // Ignore "file not found" – anything else is a real error.
            if ((err as NodeJS.ErrnoException).code !== 'ENOENT') {
                throw err;
            }
        }
    }
}
