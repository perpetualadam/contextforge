/**
 * Test suite entry point.
 *
 * Discovers and runs all tests in the suite directory.
 */

import * as path from 'path';
import * as fs from 'fs';
import * as Mocha from 'mocha';

async function collectTestFiles(dir: string): Promise<string[]> {
    const entries = await fs.promises.readdir(dir, { withFileTypes: true });
    const files: string[] = [];

    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            files.push(...await collectTestFiles(fullPath));
        } else if (entry.isFile() && entry.name.endsWith('.test.js')) {
            files.push(fullPath);
        }
    }

    return files;
}

export async function run(): Promise<void> {
    // Create the mocha test
    const mocha = new Mocha({
        ui: 'tdd',
        color: true,
        timeout: 10000
    });

    const testsRoot = path.resolve(__dirname, '.');
    const files = await collectTestFiles(testsRoot);
    files.forEach((f: string) => mocha.addFile(f));

    return new Promise((resolve, reject) => {
        try {
            mocha.run((failures: number) => {
                if (failures > 0) {
                    reject(new Error(`${failures} tests failed.`));
                } else {
                    resolve();
                }
            });
        } catch (err) {
            console.error(err);
            reject(err);
        }
    });
}
