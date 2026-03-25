import {
    getOAuthProvider,
    getOAuthProviders,
    type OAuthProviderId
} from '@mariozechner/pi-ai/oauth';

import { createInterface, type Interface as ReadlineInterface } from 'node:readline';
import { saveOAuthLoginData } from './auth.js';

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
        await saveOAuthLoginData(providerId, credentials);
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
