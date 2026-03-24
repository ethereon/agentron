import { parseArgs } from 'node:util';
import { log } from './logging.js';
import { RpcServer } from './server.js';
import { login } from './login.js';

function fail(message: string): never {
    console.error(`Error: ${message}`);
    process.exit(1);
}

function parseOptionArgs<TOptions extends Record<string, { type: 'string'; short?: string }>>(
    args: string[],
    options: TOptions
) {
    return parseArgs({
        args,
        options,
        allowPositionals: true,
        strict: true
    });
}

interface RpcArgs {
    ipc: string;
}

function parseRpcArgs(args: string[]): RpcArgs {
    const { values, positionals } = parseOptionArgs(args, {
        ipc: {
            type: 'string',
            short: 'i'
        }
    });

    if (positionals.length > 0) {
        fail(`unexpected arguments for rpc: ${positionals.join(' ')}`);
    }

    if (!values.ipc) {
        fail('--ipc argument is required for rpc');
    }

    return { ipc: values.ipc };
}

interface LoginArgs {
    provider?: string;
}

function parseLoginArgs(args: string[]): LoginArgs {
    const { values, positionals } = parseOptionArgs(args, {});

    if (Object.keys(values).length > 0) {
        fail('login does not accept options');
    }

    if (positionals.length > 1) {
        fail(`unexpected arguments for login: ${positionals.slice(1).join(' ')}`);
    }

    const [provider] = positionals;

    return { provider };
}

async function runRpc(socketPath: string) {
    const server = new RpcServer({ socketPath });
    log.info(`Starting Agentron Flux Server on IPC socket: ${socketPath}`);
    await server.start();
}

async function main() {
    const args = process.argv.slice(2);
    const [command, ...commandArgs] = args;
    if (!command) {
        fail('command is required');
    }
    switch (command) {
        case 'rpc':
            await runRpc(parseRpcArgs(commandArgs).ipc);
            break;

        case 'login':
            await login(parseLoginArgs(commandArgs).provider);
            break;

        default:
            fail(`Unknown command: ${command}`);
    }
}

await main();
