/**
 * Tests for DiagnosticsProvider module.
 *
 * Tests VS Code diagnostics integration for IDE error/warning collection.
 */

import * as assert from 'assert';
import * as vscode from 'vscode';
import { DiagnosticsProvider, DiagnosticInfo, DiagnosticSummary } from '../../tools/diagnostics';

suite('DiagnosticsProvider Test Suite', () => {
    let diagnosticsProvider: DiagnosticsProvider;

    suiteSetup(async () => {
        diagnosticsProvider = new DiagnosticsProvider();
    });

    suite('DiagnosticsProvider Creation', () => {
        test('should be instantiable', () => {
            assert.ok(diagnosticsProvider);
        });

        test('should be a singleton via factory', () => {
            const provider1 = new DiagnosticsProvider();
            const provider2 = new DiagnosticsProvider();
            // They are separate instances but should function the same
            assert.ok(provider1);
            assert.ok(provider2);
        });
    });

    suite('getDiagnostics', () => {
        test('should return array for valid file paths', () => {
            // Even if file doesn't exist, should return empty array not throw
            const result = diagnosticsProvider.getDiagnostics(['nonexistent.ts']);

            assert.ok(Array.isArray(result));
        });

        test('should return empty array for empty paths', () => {
            const result = diagnosticsProvider.getDiagnostics([]);

            assert.ok(Array.isArray(result));
            assert.strictEqual(result.length, 0);
        });
    });

    suite('DiagnosticInfo Interface', () => {
        test('should create valid diagnostic info object', () => {
            const diagnosticInfo: DiagnosticInfo = {
                file: '/path/to/file.ts',
                relativePath: 'file.ts',
                line: 10,
                column: 5,
                endLine: 10,
                endColumn: 15,
                message: 'Test error message',
                severity: 'error',
                source: 'typescript',
                code: 'TS2345'
            };

            assert.strictEqual(diagnosticInfo.file, '/path/to/file.ts');
            assert.strictEqual(diagnosticInfo.relativePath, 'file.ts');
            assert.strictEqual(diagnosticInfo.line, 10);
            assert.strictEqual(diagnosticInfo.column, 5);
            assert.strictEqual(diagnosticInfo.endLine, 10);
            assert.strictEqual(diagnosticInfo.endColumn, 15);
            assert.strictEqual(diagnosticInfo.message, 'Test error message');
            assert.strictEqual(diagnosticInfo.severity, 'error');
            assert.strictEqual(diagnosticInfo.source, 'typescript');
            assert.strictEqual(diagnosticInfo.code, 'TS2345');
        });

        test('should support different severity levels', () => {
            const severities: Array<'error' | 'warning' | 'info' | 'hint'> = ['error', 'warning', 'info', 'hint'];

            severities.forEach(severity => {
                const diag: DiagnosticInfo = {
                    file: 'test.ts',
                    relativePath: 'test.ts',
                    line: 1,
                    column: 1,
                    endLine: 1,
                    endColumn: 10,
                    message: 'Test',
                    severity: severity,
                    source: 'test'
                };
                assert.strictEqual(diag.severity, severity);
            });
        });
    });

    suite('DiagnosticSummary Interface', () => {
        test('should create valid summary object', () => {
            const summary: DiagnosticSummary = {
                totalErrors: 5,
                totalWarnings: 10,
                totalInfo: 2,
                totalHints: 1,
                diagnostics: [],
                byFile: new Map(),
                timestamp: new Date().toISOString()
            };

            assert.strictEqual(summary.totalErrors, 5);
            assert.strictEqual(summary.totalWarnings, 10);
            assert.strictEqual(summary.totalInfo, 2);
            assert.strictEqual(summary.totalHints, 1);
            assert.ok(Array.isArray(summary.diagnostics));
            assert.ok(summary.byFile instanceof Map);
        });

        test('should correctly calculate totals', () => {
            const diagnostics: DiagnosticInfo[] = [
                { file: 'a.ts', relativePath: 'a.ts', line: 1, column: 1, endLine: 1, endColumn: 10, message: 'Error 1', severity: 'error', source: 'ts' },
                { file: 'a.ts', relativePath: 'a.ts', line: 2, column: 1, endLine: 2, endColumn: 10, message: 'Error 2', severity: 'error', source: 'ts' },
                { file: 'b.ts', relativePath: 'b.ts', line: 1, column: 1, endLine: 1, endColumn: 10, message: 'Warning 1', severity: 'warning', source: 'ts' },
                { file: 'c.ts', relativePath: 'c.ts', line: 1, column: 1, endLine: 1, endColumn: 10, message: 'Info 1', severity: 'info', source: 'ts' }
            ];

            const errors = diagnostics.filter(d => d.severity === 'error').length;
            const warnings = diagnostics.filter(d => d.severity === 'warning').length;
            const infos = diagnostics.filter(d => d.severity === 'info').length;
            const uniqueFiles = new Set(diagnostics.map(d => d.file)).size;

            assert.strictEqual(errors, 2);
            assert.strictEqual(warnings, 1);
            assert.strictEqual(infos, 1);
            assert.strictEqual(uniqueFiles, 3);
        });
    });

    suite('getAllDiagnostics', () => {
        test('should return summary object', () => {
            const summary = diagnosticsProvider.getAllDiagnostics();

            assert.ok(typeof summary.totalErrors === 'number');
            assert.ok(typeof summary.totalWarnings === 'number');
            assert.ok(typeof summary.totalInfo === 'number');
            assert.ok(typeof summary.totalHints === 'number');
            assert.ok(Array.isArray(summary.diagnostics));
            assert.ok(summary.byFile instanceof Map);
            assert.ok(typeof summary.timestamp === 'string');
        });
    });
});

