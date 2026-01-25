/**
 * Tests for FileTools module.
 * 
 * Tests file viewing, searching, and editing operations.
 */

import * as assert from 'assert';
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { FileTools } from '../../tools/fileTools';

suite('FileTools Test Suite', () => {
    let fileTools: FileTools;
    let tempDir: string;
    let testFilePath: string;

    suiteSetup(async () => {
        // Create temp directory for tests
        tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'filetools-test-'));
        
        // Create test file
        testFilePath = path.join(tempDir, 'test.txt');
        fs.writeFileSync(testFilePath, `Line 1: Hello World
Line 2: This is a test file
Line 3: With multiple lines
Line 4: For testing purposes
Line 5: End of file`);

        // Initialize FileTools with temp dir as workspace
        fileTools = new FileTools(
            { apiUrl: 'http://localhost:8080' },
            tempDir
        );
    });

    suiteTeardown(() => {
        // Clean up temp directory
        if (tempDir && fs.existsSync(tempDir)) {
            fs.rmSync(tempDir, { recursive: true, force: true });
        }
    });

    suite('viewFile', () => {
        test('should view entire file', async () => {
            const result = await fileTools.viewFile('test.txt');
            
            assert.strictEqual(result.success, true);
            assert.strictEqual(result.totalLines, 5);
            assert.strictEqual(result.isTruncated, false);
            assert.ok(result.content.includes('Hello World'));
            assert.ok(result.content.includes('End of file'));
        });

        test('should view file with line range', async () => {
            const result = await fileTools.viewFile('test.txt', [2, 4]);
            
            assert.strictEqual(result.success, true);
            assert.ok(result.content.includes('This is a test file'));
            assert.ok(result.content.includes('For testing purposes'));
            assert.ok(!result.content.includes('Hello World'));
        });

        test('should return error for non-existent file', async () => {
            const result = await fileTools.viewFile('nonexistent.txt');
            
            assert.strictEqual(result.success, false);
            assert.ok(result.message?.includes('not found'));
        });

        test('should include line numbers', async () => {
            const result = await fileTools.viewFile('test.txt');
            
            assert.strictEqual(result.success, true);
            // Line numbers should be padded and followed by tab
            assert.ok(result.content.includes('\t'));
        });
    });

    suite('searchFile', () => {
        test('should find regex matches', async () => {
            const results = await fileTools.searchFile('test.txt', 'Line [0-9]+');
            
            assert.strictEqual(results.length, 5);
            assert.strictEqual(results[0].line, 1);
            assert.ok(results[0].match.startsWith('Line'));
        });

        test('should be case insensitive by default', async () => {
            const results = await fileTools.searchFile('test.txt', 'HELLO');
            
            assert.ok(results.length > 0);
            assert.strictEqual(results[0].match.toLowerCase(), 'hello');
        });

        test('should support case sensitive search', async () => {
            const results = await fileTools.searchFile('test.txt', 'HELLO', true);
            
            assert.strictEqual(results.length, 0);
        });

        test('should return empty array for no matches', async () => {
            const results = await fileTools.searchFile('test.txt', 'nonexistent_pattern');
            
            assert.strictEqual(results.length, 0);
        });

        test('should include match context', async () => {
            const results = await fileTools.searchFile('test.txt', 'test file');
            
            assert.ok(results.length > 0);
            assert.ok(results[0].context.includes('This is a test file'));
        });
    });

    suite('saveFile', () => {
        test('should create new file', async () => {
            const newFilePath = 'new_file.txt';
            const content = 'New file content';
            
            const result = await fileTools.saveFile(newFilePath, content);
            
            assert.strictEqual(result.success, true);
            assert.strictEqual(result.changesMade, 1);
            
            const absolutePath = path.join(tempDir, newFilePath);
            assert.ok(fs.existsSync(absolutePath));
            assert.strictEqual(fs.readFileSync(absolutePath, 'utf-8'), content);
            
            // Clean up
            fs.unlinkSync(absolutePath);
        });

        test('should not overwrite existing file by default', async () => {
            const result = await fileTools.saveFile('test.txt', 'new content');
            
            assert.strictEqual(result.success, false);
            assert.ok(result.message?.includes('already exists'));
        });

        test('should overwrite existing file when flag is set', async () => {
            const newContent = 'Overwritten content';
            const result = await fileTools.saveFile('test.txt', newContent, true);
            
            assert.strictEqual(result.success, true);
            
            const content = fs.readFileSync(testFilePath, 'utf-8');
            assert.strictEqual(content, newContent);
            
            // Restore original content
            fs.writeFileSync(testFilePath, `Line 1: Hello World
Line 2: This is a test file
Line 3: With multiple lines
Line 4: For testing purposes
Line 5: End of file`);
        });
    });
});

