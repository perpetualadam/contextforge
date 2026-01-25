/**
 * ContextForge Diagnostics Provider
 * 
 * Integrates with VS Code's built-in diagnostics system to expose
 * errors, warnings, hints, and info from:
 * - TypeScript/JavaScript language services
 * - ESLint, Pylint, etc.
 * - Any language server protocol (LSP) providers
 * 
 * @module tools/diagnostics
 */

import * as vscode from 'vscode';
import * as path from 'path';

/**
 * Individual diagnostic information
 */
export interface DiagnosticInfo {
    file: string;
    relativePath: string;
    line: number;
    column: number;
    endLine: number;
    endColumn: number;
    severity: 'error' | 'warning' | 'info' | 'hint';
    message: string;
    source?: string;
    code?: string | number;
}

/**
 * Summary of all diagnostics
 */
export interface DiagnosticSummary {
    totalErrors: number;
    totalWarnings: number;
    totalInfo: number;
    totalHints: number;
    diagnostics: DiagnosticInfo[];
    byFile: Map<string, DiagnosticInfo[]>;
    timestamp: string;
}

/**
 * Provides access to VS Code IDE diagnostics (errors, warnings, etc.)
 */
export class DiagnosticsProvider {
    private _onDidChange = new vscode.EventEmitter<DiagnosticSummary>();
    readonly onDidChange = this._onDidChange.event;
    
    private _disposables: vscode.Disposable[] = [];
    private _workspaceRoot: string;

    constructor(workspaceRoot?: string) {
        this._workspaceRoot = workspaceRoot || 
            vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    }

    /**
     * Convert VS Code DiagnosticSeverity to string
     */
    private severityToString(severity: vscode.DiagnosticSeverity): 'error' | 'warning' | 'info' | 'hint' {
        switch (severity) {
            case vscode.DiagnosticSeverity.Error:
                return 'error';
            case vscode.DiagnosticSeverity.Warning:
                return 'warning';
            case vscode.DiagnosticSeverity.Information:
                return 'info';
            case vscode.DiagnosticSeverity.Hint:
                return 'hint';
            default:
                return 'info';
        }
    }

    /**
     * Convert a VS Code Diagnostic to DiagnosticInfo
     */
    private convertDiagnostic(uri: vscode.Uri, diag: vscode.Diagnostic): DiagnosticInfo {
        const filePath = uri.fsPath;
        let relativePath = filePath;
        
        if (this._workspaceRoot && filePath.startsWith(this._workspaceRoot)) {
            relativePath = path.relative(this._workspaceRoot, filePath);
        }

        return {
            file: filePath,
            relativePath,
            line: diag.range.start.line + 1,  // Convert 0-based to 1-based
            column: diag.range.start.character + 1,
            endLine: diag.range.end.line + 1,
            endColumn: diag.range.end.character + 1,
            severity: this.severityToString(diag.severity),
            message: diag.message,
            source: diag.source,
            code: typeof diag.code === 'object' ? diag.code.value : diag.code
        };
    }

    /**
     * Get diagnostics for specific files
     * 
     * @param paths Array of file paths (relative or absolute)
     * @returns Array of DiagnosticInfo for the specified files
     */
    getDiagnostics(paths: string[]): DiagnosticInfo[] {
        const result: DiagnosticInfo[] = [];
        
        for (const filePath of paths) {
            // Resolve path
            let absolutePath = filePath;
            if (!path.isAbsolute(filePath) && this._workspaceRoot) {
                absolutePath = path.join(this._workspaceRoot, filePath);
            }
            
            const uri = vscode.Uri.file(absolutePath);
            const diagnostics = vscode.languages.getDiagnostics(uri);
            
            for (const diag of diagnostics) {
                result.push(this.convertDiagnostic(uri, diag));
            }
        }
        
        return result;
    }

    /**
     * Get all diagnostics in the workspace
     * 
     * @returns DiagnosticSummary with all diagnostics
     */
    getAllDiagnostics(): DiagnosticSummary {
        const allDiagnostics = vscode.languages.getDiagnostics();
        const result: DiagnosticInfo[] = [];
        const byFile = new Map<string, DiagnosticInfo[]>();
        
        let totalErrors = 0;
        let totalWarnings = 0;
        let totalInfo = 0;
        let totalHints = 0;
        
        for (const [uri, diagnostics] of allDiagnostics) {
            const fileDiagnostics: DiagnosticInfo[] = [];
            
            for (const diag of diagnostics) {
                const info = this.convertDiagnostic(uri, diag);
                result.push(info);
                fileDiagnostics.push(info);
                
                switch (info.severity) {
                    case 'error': totalErrors++; break;
                    case 'warning': totalWarnings++; break;
                    case 'info': totalInfo++; break;
                    case 'hint': totalHints++; break;
                }
            }
            
            if (fileDiagnostics.length > 0) {
                byFile.set(uri.fsPath, fileDiagnostics);
            }
        }

        return {
            totalErrors,
            totalWarnings,
            totalInfo,
            totalHints,
            diagnostics: result,
            byFile,
            timestamp: new Date().toISOString()
        };
    }

    /**
     * Get diagnostics filtered by severity
     *
     * @param severity Filter by severity level(s)
     * @param paths Optional file paths to filter
     * @returns Filtered diagnostics
     */
    getDiagnosticsBySeverity(
        severity: ('error' | 'warning' | 'info' | 'hint')[],
        paths?: string[]
    ): DiagnosticInfo[] {
        const allDiags = paths ? this.getDiagnostics(paths) : this.getAllDiagnostics().diagnostics;
        return allDiags.filter(d => severity.includes(d.severity));
    }

    /**
     * Get only errors
     */
    getErrors(paths?: string[]): DiagnosticInfo[] {
        return this.getDiagnosticsBySeverity(['error'], paths);
    }

    /**
     * Get errors and warnings
     */
    getErrorsAndWarnings(paths?: string[]): DiagnosticInfo[] {
        return this.getDiagnosticsBySeverity(['error', 'warning'], paths);
    }

    /**
     * Start watching for diagnostic changes
     *
     * @returns Disposable to stop watching
     */
    startWatching(): vscode.Disposable {
        const disposable = vscode.languages.onDidChangeDiagnostics(() => {
            const summary = this.getAllDiagnostics();
            this._onDidChange.fire(summary);
        });

        this._disposables.push(disposable);
        return disposable;
    }

    /**
     * Format diagnostics as a readable string
     */
    formatDiagnostics(diagnostics: DiagnosticInfo[]): string {
        if (diagnostics.length === 0) {
            return 'No diagnostics found.';
        }

        const lines: string[] = [];
        let currentFile = '';

        for (const diag of diagnostics) {
            if (diag.relativePath !== currentFile) {
                currentFile = diag.relativePath;
                lines.push(`\n${currentFile}:`);
            }

            const severity = diag.severity.toUpperCase().padEnd(7);
            const location = `${diag.line}:${diag.column}`;
            const source = diag.source ? ` [${diag.source}]` : '';
            const code = diag.code ? ` (${diag.code})` : '';

            lines.push(`  ${location} ${severity} ${diag.message}${source}${code}`);
        }

        return lines.join('\n');
    }

    /**
     * Dispose of resources
     */
    dispose(): void {
        for (const d of this._disposables) {
            d.dispose();
        }
        this._disposables = [];
        this._onDidChange.dispose();
    }
}

