import { parseArgs } from 'node:util';
import { RpcServer } from './server.js';
import { log } from './logging.js';

interface Args {
    ipc: string;
}

function parseArgsOrExit(): Args {
    const args = process.argv.slice(2);
    const { values } = parseArgs({
        args,
        options: {
            ipc: {
                type: 'string',
                short: 'i'
            }
        },
        strict: true
    });

    if (!values.ipc) {
        console.error('Error: --ipc argument is required');
        process.exit(1);
    }

    return {
        ipc: values.ipc
    };
}

async function main() {
    const args = parseArgsOrExit();
    const server = new RpcServer({ socketPath: args.ipc });

    log.info(`Starting Agentron Flux Server on IPC socket: ${args.ipc}`);
    await server.start();
}

await main();
