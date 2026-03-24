import * as FS from 'node:fs/promises';
import * as Path from 'node:path';

import {
    getOAuthProvider,
    getOAuthProviders,
    type OAuthCredentials,
    type OAuthProviderId
} from '@mariozechner/pi-ai/oauth';

import { createInterface, type Interface as ReadlineInterface } from 'node:readline';

export async function login(providerId?: OAuthProviderId): Promise<void> {
    if (providerId == null) {
        providerId = await selectProviderInteractively();
    }
    const provider = getOAuthProvider(providerId);
    if (!provider) {
        fail(`Unknown provider: ${providerId}`);
    }

    try {
        const credentials = await provider.login({
            onAuth: info => {
                console.log(`\nOpen this URL to continue logging in:\n    ${info.url}`);
                if (info.instructions) {
                    console.log(`${info.instructions}\n`);
                }
            },
            onPrompt: async p => {
                return await prompt(`${p.message}${p.placeholder ? ` (${p.placeholder})` : ''}:`);
            },
            onProgress: msg => console.log(msg)
        });
        await saveCredentials(providerId, credentials);
    } finally {
        destroyRL();
    }
}

async function selectProviderInteractively(): Promise<OAuthProviderId> {
    const providers = getOAuthProviders();
    console.log('Select a provider to log in:');
    providers.forEach((p, i) => {
        console.log(`    ${i + 1}: ${p.name}`);
    });
    const choice = await prompt('Enter the number of the provider: ');
    const index = parseInt(choice, 10) - 1;
    if (isNaN(index) || index < 0 || index >= providers.length) {
        throw new Error('Invalid choice');
    }
    return providers[index].id;
}

async function saveCredentials(
    providerId: OAuthProviderId,
    credentials: OAuthCredentials
): Promise<void> {
    // Load ~/.agentron/auth.json if it exists, otherwise start with an empty object
    let authData: Record<string, OAuthCredentials | string> = {};
    const homeDir = process.env.HOME;
    if (!homeDir) {
        throw new Error('HOME environment variable is not set.');
    }
    const authFile = Path.join(homeDir, '.agentron', 'auth.json');
    try {
        const content = await FS.readFile(authFile, 'utf-8');
        authData = JSON.parse(content);
        if (typeof authData !== 'object' || authData === null) {
            fail(`Invalid auth file encountered at: ${authFile}`);
        }
    } catch (err) {
        // Ignore errors (file not found, invalid JSON, etc.)
    }

    // Add the new credentials
    authData[providerId] = { type: 'oauth', ...credentials };

    // Save
    await FS.mkdir(Path.dirname(authFile), { recursive: true });
    await FS.writeFile(authFile, JSON.stringify(authData, null, 4), 'utf-8');
}

let _rl: ReadlineInterface | null = null;
function getRL(): ReadlineInterface {
    if (!_rl) {
        _rl = createInterface({ input: process.stdin, output: process.stdout });
        _rl.once('SIGINT', () => {
            process.exit(-1);
        });
    }
    return _rl;
}

function destroyRL(): void {
    if (_rl) {
        _rl.close();
        _rl = null;
    }
}

function prompt(question: string): Promise<string> {
    return new Promise(resolve => {
        getRL().question(question, answer => {
            resolve(answer);
        });
    });
}

function fail(message: string): never {
    console.error(`Error: ${message}`);
    process.exit(1);
}
