import * as esbuild from 'esbuild';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as child_process from 'child_process';

const kProjectRoot = path.resolve(import.meta.dirname, '..');
const kOutputDir = path.join(kProjectRoot, 'dist');

async function generateStyles() {
    const { promise, resolve, reject } = Promise.withResolvers();

    const proc = child_process.spawn(
        'python3',
        [path.join(kProjectRoot, 'scripts', 'generate_styles.py')],
        {
            stdio: ['ignore', 'pipe', 'pipe']
        }
    );

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', data => {
        stdout += data.toString();
    });

    proc.stderr.on('data', data => {
        stderr += data.toString();
    });

    proc.on('close', code => {
        if (code === 0) {
            resolve();
        } else {
            reject(new Error(`generate_styles.py exited with code ${code}\n${stderr}\n${stdout}`));
        }
    });

    proc.on('error', err => {
        reject(err);
    });

    try {
        await promise;
        console.log('Styles generated successfully.');
    } catch (err) {
        // Log the error but don't treat as fatal.
        console.error(`Error generating styles:\n${err.message}`);
    }
}

async function build() {
    if (fs.existsSync(kOutputDir)) {
        await fs.promises.rm(kOutputDir, { recursive: true });
    }
    await fs.promises.mkdir(kOutputDir, { recursive: true });

    await generateStyles();

    // Copy the static assets dir to the output dir
    await fs.promises.cp(path.join(kProjectRoot, 'assets'), path.join(kOutputDir, 'assets'), {
        recursive: true
    });

    const tasks = [
        fs.promises.copyFile(
            path.join(kProjectRoot, 'src', 'index.html'),
            path.join(kOutputDir, 'index.html')
        ),

        esbuild.build({
            entryPoints: [path.join(kProjectRoot, 'src', 'app.ts')],
            bundle: true,
            outfile: path.join(kOutputDir, 'agentron-webui.js')
        })
    ];
    await Promise.all(tasks);
    console.log('Build completed successfully.');
}

await build();
