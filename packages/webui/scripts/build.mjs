import * as esbuild from 'esbuild';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as child_process from 'child_process';

const kOutputDir = 'dist';

function generateStyles() {
    return new Promise((resolve, reject) => {
        const process = child_process.spawn('python3', ['scripts/generate_styles.py'], {
            stdio: 'inherit'
        });
        process.on('close', code => {
            if (code === 0) {
                resolve();
            } else {
                reject(new Error(`generate_styles.py exited with code ${code}`));
            }
        });
    });
}

async function build() {
    if (fs.existsSync(kOutputDir)) {
        await fs.promises.rm(kOutputDir, { recursive: true });
    }
    await fs.promises.mkdir(kOutputDir, { recursive: true });

    const tasks = [
        fs.promises.copyFile('src/index.html', path.join(kOutputDir, 'index.html')),

        generateStyles(),

        esbuild.build({
            entryPoints: ['src/app.ts'],
            bundle: true,
            outfile: path.join(kOutputDir, 'agentron-webui.js')
        })
    ];
    await Promise.all(tasks);
    console.log('Build completed successfully.');
}

await build();
