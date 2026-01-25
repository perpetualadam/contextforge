/**
 * ContextForge File Tools
 * 
 * Hybrid file operation wrappers that can use either:
 * - VS Code's native file APIs (faster for local operations)
 * - Backend API calls (for complex operations with validation)
 * 
 * @module tools/fileTools
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import axios from 'axios';

/**
 * Result of a view operation
 */
export interface ViewResult {
    success: boolean;
    content: string;
    totalLines: number;
    isTruncated: boolean;
    message?: string;
}

/**
 * Result of an edit operation
 */
export interface EditResult {
    success: boolean;
    message: string;
    changesMade: number;
    backupPath?: string;
}

/**
 * Result of a search operation
 */
export interface SearchResult {
    line: number;
    column: number;
    match: string;
    context: string;
}

/**
 * String replacement entry
 */
export interface StrReplacement {
    oldStr: string;
    newStr: string;
    startLine?: number;
    endLine?: number;
}

interface FileToolsConfig {
    apiUrl: string;
    preferLocal: boolean;
    maxFileSizeLocal: number;  // Max file size for local operations (bytes)
}

/**
 * Hybrid file tools provider
 */
export class FileTools {
    private _workspaceRoot: string;
    private _config: FileToolsConfig;

    constructor(config: { apiUrl: string }, workspaceRoot?: string) {
        this._workspaceRoot = workspaceRoot || 
            vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        this._config = {
            apiUrl: config.apiUrl,
            preferLocal: true,
            maxFileSizeLocal: 10 * 1024 * 1024  // 10MB
        };
    }

    /**
     * Resolve a path relative to workspace root
     */
    private resolvePath(filePath: string): string {
        if (path.isAbsolute(filePath)) {
            return filePath;
        }
        return path.join(this._workspaceRoot, filePath);
    }

    /**
     * View a file with optional line range
     * Uses VS Code API for local files, backend for complex operations
     * 
     * @param filePath Path to the file
     * @param range Optional line range [start, end] (1-based, inclusive)
     */
    async viewFile(filePath: string, range?: [number, number]): Promise<ViewResult> {
        const absolutePath = this.resolvePath(filePath);

        try {
            // Check if file exists
            if (!fs.existsSync(absolutePath)) {
                return {
                    success: false,
                    content: '',
                    totalLines: 0,
                    isTruncated: false,
                    message: `File not found: ${filePath}`
                };
            }

            // Check file size
            const stats = fs.statSync(absolutePath);
            
            // Use VS Code API for local files
            if (this._config.preferLocal && stats.size <= this._config.maxFileSizeLocal) {
                const uri = vscode.Uri.file(absolutePath);
                const document = await vscode.workspace.openTextDocument(uri);
                let content = document.getText();
                const totalLines = document.lineCount;
                let isTruncated = false;

                // Apply line range if specified
                if (range) {
                    const [start, end] = range;
                    const lines = content.split('\n');
                    const startIdx = Math.max(0, start - 1);
                    const endIdx = end === -1 ? lines.length : Math.min(lines.length, end);
                    content = lines.slice(startIdx, endIdx).join('\n');
                    isTruncated = endIdx < lines.length;
                }

                // Add line numbers
                const numberedLines = content.split('\n').map((line, i) => {
                    const lineNum = (range ? range[0] : 1) + i;
                    return `${String(lineNum).padStart(6)}\t${line}`;
                });

                return {
                    success: true,
                    content: numberedLines.join('\n'),
                    totalLines,
                    isTruncated
                };
            }

            // Use backend for large files
            const response = await axios.post(`${this._config.apiUrl}/view`, {
                path: filePath,
                view_range: range
            });
            
            return {
                success: true,
                content: response.data.content,
                totalLines: response.data.total_lines,
                isTruncated: response.data.is_truncated
            };
        } catch (error: any) {
            return {
                success: false,
                content: '',
                totalLines: 0,
                isTruncated: false,
                message: error.message
            };
        }
    }

    /**
     * Search in a file with regex
     */
    async searchFile(
        filePath: string,
        pattern: string,
        caseSensitive: boolean = false
    ): Promise<SearchResult[]> {
        const absolutePath = this.resolvePath(filePath);
        const results: SearchResult[] = [];

        try {
            const uri = vscode.Uri.file(absolutePath);
            const document = await vscode.workspace.openTextDocument(uri);
            const text = document.getText();
            const lines = text.split('\n');

            const flags = caseSensitive ? 'g' : 'gi';
            const regex = new RegExp(pattern, flags);

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                let match;
                regex.lastIndex = 0;  // Reset regex state

                while ((match = regex.exec(line)) !== null) {
                    results.push({
                        line: i + 1,
                        column: match.index + 1,
                        match: match[0],
                        context: line.trim()
                    });
                    if (!regex.global) {
                        break;
                    }
                }
            }
        } catch (error: any) {
            console.error('Search error:', error);
        }

        return results;
    }

    /**
     * Apply string replacements to a file (uses backend for validation)
     */
    async strReplace(filePath: string, replacements: StrReplacement[]): Promise<EditResult> {
        try {
            const response = await axios.post(`${this._config.apiUrl}/files/str-replace`, {
                path: filePath,
                replacements: replacements.map(r => ({
                    old_str: r.oldStr,
                    new_str: r.newStr,
                    start_line: r.startLine,
                    end_line: r.endLine
                })),
                create_backup: true
            });

            return {
                success: response.data.status === 'success',
                message: response.data.message,
                changesMade: response.data.changes_made || 0,
                backupPath: response.data.backup_path
            };
        } catch (error: any) {
            return {
                success: false,
                message: error.response?.data?.detail || error.message,
                changesMade: 0
            };
        }
    }

    /**
     * Create a new file with content
     */
    async saveFile(filePath: string, content: string, overwrite: boolean = false): Promise<EditResult> {
        const absolutePath = this.resolvePath(filePath);

        try {
            if (fs.existsSync(absolutePath) && !overwrite) {
                return {
                    success: false,
                    message: `File already exists: ${filePath}. Use overwrite=true to replace.`,
                    changesMade: 0
                };
            }

            const dir = path.dirname(absolutePath);
            if (!fs.existsSync(dir)) {
                fs.mkdirSync(dir, { recursive: true });
            }

            fs.writeFileSync(absolutePath, content, 'utf-8');

            return {
                success: true,
                message: `File saved: ${filePath}`,
                changesMade: 1
            };
        } catch (error: any) {
            return {
                success: false,
                message: error.message,
                changesMade: 0
            };
        }
    }

    /**
     * Remove files safely (uses backend for validation and backup)
     */
    async removeFiles(filePaths: string[]): Promise<EditResult> {
        try {
            const response = await axios.post(`${this._config.apiUrl}/files/remove`, {
                paths: filePaths,
                create_backup: true
            });

            return {
                success: response.data.status === 'success',
                message: response.data.message,
                changesMade: response.data.files_removed || 0,
                backupPath: response.data.backup_path
            };
        } catch (error: any) {
            return {
                success: false,
                message: error.response?.data?.detail || error.message,
                changesMade: 0
            };
        }
    }

    /**
     * Open a file in VS Code editor
     */
    async openInEditor(filePath: string, line?: number, column?: number): Promise<void> {
        const absolutePath = this.resolvePath(filePath);
        const uri = vscode.Uri.file(absolutePath);
        const document = await vscode.workspace.openTextDocument(uri);
        const editor = await vscode.window.showTextDocument(document);

        if (line !== undefined) {
            const position = new vscode.Position(line - 1, (column || 1) - 1);
            editor.selection = new vscode.Selection(position, position);
            editor.revealRange(
                new vscode.Range(position, position),
                vscode.TextEditorRevealType.InCenter
            );
        }
    }
}
