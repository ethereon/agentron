import * as esbuild from 'esbuild';
import * as fs from 'node:fs';
import * as path from 'node:path';

const kProjectRoot = path.resolve(import.meta.dirname, '..');
const kOutputDir = path.join(kProjectRoot, 'dist', 'bundle');

async function build() {
    if (fs.existsSync(kOutputDir)) {
        await fs.promises.rm(kOutputDir, { recursive: true });
    }
    await fs.promises.mkdir(kOutputDir, { recursive: true });

    await esbuild.build({
        entryPoints: [path.join(kProjectRoot, 'src', 'main.ts')],
        bundle: true,
        outfile: path.join(kOutputDir, 'agentron-flux.js'),
        platform: 'node',
        format: 'esm',
        sourcemap: 'linked'
    });
    console.log('Flux successfully bundled.');
}

await build();
