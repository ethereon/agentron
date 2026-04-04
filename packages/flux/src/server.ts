import type * as net from 'node:net';

import { UnixRpcServer } from '@ethereon/ein/unix-rpc-server';

import type { AssistantMessage } from './types/messages.js';
import type { ToolSet } from './llm-request.js';
import type {
    NotificationKind,
    RequestKind,
    SessionStartRequest,
    TransmitRequest,
    ApiKeySource
} from './types/api.js';

import { PiBackend } from './pi/pi-backend.js';
import { isModel, isModelReasoningLevel } from './model.validation.js';
import { isToolSchema } from './tool-schema.validation.js';
import { isAgentMessage } from './agent-message.validation.js';
import { resolveApiKey } from './pi/pi-auth.js';

interface RpcServerParams {
    socketPath: string;
}

interface SessionState {
    sessionId: string;
    backend: PiBackend;
    tools: ToolSet;
    abortController?: AbortController;
}

export class RpcServer {
    private readonly sessions = new Map<string, SessionState>();
    private readonly server: UnixRpcServer;

    constructor(params: RpcServerParams) {
        const server = (this.server = new UnixRpcServer({
            socketPath: params.socketPath,
            methodTimeout: 600_000 // 10 minutes
        }));
        server.register<RequestKind>('session_start', this.startSession.bind(this));
        server.register<RequestKind>('transmit', this.handleTransmit.bind(this), {
            wantsSocket: true
        });

        // Output READY signal on stdout when server is ready to accept connections.
        server.on('listening', () => {
            console.log('READY');
        });
    }

    start(): Promise<void> {
        return this.server.start();
    }

    private async startSession(request: SessionStartRequest): Promise<void> {
        this.validateSessionStartRequest(request);
        const sessionId = request.session_id;
        const apiKey = await this.resolveApiKey(request.api_key);
        this.sessions.set(sessionId, {
            sessionId: sessionId,
            backend: new PiBackend({
                model: request.model,
                apiKey
            }),
            tools: {
                tools: request.tools
            }
        });
    }

    private async resolveApiKey(apiKeySource?: ApiKeySource | null): Promise<string | undefined> {
        if (apiKeySource == null) {
            return undefined;
        }
        if (typeof apiKeySource === 'string') {
            return apiKeySource;
        }
        if (apiKeySource.type === 'oauth') {
            return resolveApiKey(apiKeySource);
        }
        throw Error(`Invalid api key source specified.`);
    }

    private validateSessionStartRequest(request: SessionStartRequest): void {
        if (!isModel(request.model)) {
            throw new Error('Invalid model specification.');
        }
        if (!Array.isArray(request.tools)) {
            throw new Error('Tools must be an array.');
        }
        for (const tool of request.tools) {
            if (!isToolSchema(tool)) {
                const name = (tool as any)?.name ?? 'Unknown';
                throw new Error(`Invalid tool specification (${name}).`);
            }
        }
        const sessionId = request.session_id;
        if (typeof sessionId !== 'string') {
            throw new Error('Session ID must be a string.');
        }
        if (this.sessions.has(sessionId)) {
            throw new Error(`Session ID ${sessionId} already exists.`);
        }
    }

    private async handleTransmit(
        socket: net.Socket,
        request: TransmitRequest
    ): Promise<AssistantMessage | undefined> {
        const session = this.validateTransmitRequest(request);
        if (session.abortController) {
            throw new Error(`Session ${session.sessionId} is already engaged in a transmission.`);
        }
        session.abortController = new AbortController();
        try {
            const response = await session.backend.transmit({
                messages: request.messages,
                tools: session.tools,
                abortSignal: session.abortController.signal,
                sessionId: request.session_id,
                reasoning: request.reasoning ?? undefined,
                onStreamingMessage: msg => {
                    this.server.notify<NotificationKind>(socket, 'streaming_message', [msg]);
                }
            });
            return response;
        } finally {
            if (session.abortController) {
                session.abortController.abort();
                session.abortController = undefined;
            }
        }
    }

    private validateTransmitRequest(request: TransmitRequest): SessionState {
        const sessionId = request.session_id;
        if (typeof sessionId !== 'string') {
            throw new Error('Session ID must be a string.');
        }
        const session = this.sessions.get(sessionId);
        if (!session) {
            throw new Error(`Session ID ${sessionId} not found.`);
        }
        if (request.reasoning != null) {
            if (!isModelReasoningLevel(request.reasoning)) {
                throw new Error(`Invalid reasoning level: ${request.reasoning}`);
            }
        }
        if (!Array.isArray(request.messages)) {
            throw new Error('Messages must be an array.');
        }
        for (const message of request.messages) {
            if (!isAgentMessage(message)) {
                throw new Error(`Invalid message at index ${request.messages.indexOf(message)}.`);
            }
        }
        return session;
    }
}
