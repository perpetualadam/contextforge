import * as vscode from 'vscode';
import axios from 'axios';
import * as path from 'path';
import * as fs from 'fs';
import { execSync } from 'child_process';
import { ContextForgeChatProvider } from './chatPanel';
import { ContextForgePromptProvider } from './promptPanel';
import { GitIntegration, GitConfig, VCSProvider } from './gitIntegration';
import { AgentStatusProvider } from './agentPanel';
import { TaskPanelProvider } from './tools/taskPanel';
import { DiagnosticsProvider } from './tools/diagnostics';

interface ContextForgeConfig {
    apiUrl: string;
    /** Base URL of the ContextForge web UI (Publish hub, chat dashboard). */
    webUiUrl: string;
    autoIngest: boolean;
    maxResults: number;
    enableWebSearch: boolean;
    showLineNumbers: boolean;
    autoTerminalMode: boolean;
    autoTerminalTimeout: number;
    autoTerminalWhitelist: string[];
    chatHistoryEnabled: boolean;
    chatMaxHistory: number;
    fileAttachmentsEnabled: boolean;
    maxFileSize: number;
    allowedFileTypes: string[];
    gitEnabled: boolean;
    githubToken: string;
    gitlabToken: string;
    gitlabUrl: string;
    bitbucketToken: string;
    bitbucketUsername: string;
    vcsProvider: string;
    autoCommitMessages: boolean;
    defaultBranch: string;
    incrementalIndexing: boolean;
    privacyMode: boolean;
    enableInlineCompletion: boolean;
    enableAutoLint: boolean;
    [key: string]: any;
}

function toGitConfig(c: ContextForgeConfig): GitConfig {
    const vp = c.vcsProvider;
    const vcsProvider: VCSProvider =
        vp === 'gitlab' || vp === 'bitbucket' ? vp : 'github';
    return {
        gitEnabled: c.gitEnabled,
        githubToken: c.githubToken,
        gitlabToken: c.gitlabToken,
        gitlabUrl: c.gitlabUrl,
        bitbucketToken: c.bitbucketToken,
        bitbucketUsername: c.bitbucketUsername,
        autoCommitMessages: c.autoCommitMessages,
        defaultBranch: c.defaultBranch,
        vcsProvider,
    };
}

interface EditorContextPayload {
    current_file: string | undefined;
    current_selection: string | undefined;
    cursor_line: number | undefined;
    open_files: string[];
    git_diff: string | undefined;
    recent_files: string[];
}

interface AutoTerminalResult {
    command: string;
    exit_code: number;
    stdout: string;
    stderr: string;
    execution_time: number;
    matched_whitelist: boolean;
}

interface QueryResponse {
    question: string;
    answer: string;
    contexts: Array<{
        text: string;
        score: number;
        meta: {
            file_path?: string;
            start_line?: number;
            end_line?: number;
            chunk_type?: string;
        };
    }>;
    web_results: Array<{
        title: string;
        url: string;
        snippet: string;
    }>;
    auto_terminal_results?: AutoTerminalResult[];
    meta: {
        backend: string;
        total_latency_ms: number;
        num_contexts: number;
        num_web_results: number;
        auto_commands_executed?: number;
    };
}

interface IngestResponse {
    status: string;
    message: string;
    stats: {
        files_processed: number;
        chunks_created: number;
        chunks_indexed: number;
    };
}

class ContextForgeProvider implements vscode.TreeDataProvider<ContextItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<ContextItem | undefined | null | void> = new vscode.EventEmitter<ContextItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<ContextItem | undefined | null | void> = this._onDidChangeTreeData.event;

    private indexStats: any = null;

    constructor(private config: ContextForgeConfig) {}

    refresh(): void {
        this.loadIndexStats();
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: ContextItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: ContextItem): Thenable<ContextItem[]> {
        if (!element) {
            return Promise.resolve(this.getRootItems());
        }
        return Promise.resolve([]);
    }

    private async loadIndexStats() {
        try {
            const response = await axios.get(`${this.config.apiUrl}/index/stats`);
            this.indexStats = response.data;
        } catch (error) {
            console.error('Failed to load index stats:', error);
            this.indexStats = null;
        }
    }

    private getRootItems(): ContextItem[] {
        const items: ContextItem[] = [];

        if (this.indexStats) {
            items.push(new ContextItem(
                `Indexed Vectors: ${this.indexStats.total_vectors || 0}`,
                vscode.TreeItemCollapsibleState.None,
                'info'
            ));
            items.push(new ContextItem(
                `Embedding Model: ${this.indexStats.embedding_model || 'Unknown'}`,
                vscode.TreeItemCollapsibleState.None,
                'info'
            ));
            items.push(new ContextItem(
                `Backend: ${this.indexStats.backend || 'Unknown'}`,
                vscode.TreeItemCollapsibleState.None,
                'info'
            ));
        } else {
            items.push(new ContextItem(
                'Index not available',
                vscode.TreeItemCollapsibleState.None,
                'error'
            ));
        }

        return items;
    }
}

class ContextItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly type: 'info' | 'error' | 'warning'
    ) {
        super(label, collapsibleState);
        this.tooltip = this.label;
        this.contextValue = type;
    }
}

class ContextForgeWebviewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'contextforge.indexView';

    private _view?: vscode.WebviewView;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private config: ContextForgeConfig
    ) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                this._extensionUri
            ]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        webviewView.webview.onDidReceiveMessage(data => {
            switch (data.type) {
                case 'openFile':
                    this.openFile(data.filePath, data.startLine, data.endLine);
                    break;
                case 'copyText':
                    vscode.env.clipboard.writeText(data.text);
                    vscode.window.showInformationMessage('Copied to clipboard');
                    break;
            }
        });
    }

    public showResults(response: QueryResponse) {
        if (this._view) {
            this._view.show?.(true);
            this._view.webview.postMessage({
                type: 'showResults',
                data: response
            });
        }
    }

    private async openFile(filePath: string, startLine?: number, endLine?: number) {
        try {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders) {
                vscode.window.showErrorMessage('No workspace folder open');
                return;
            }

            const fullPath = path.join(workspaceFolders[0].uri.fsPath, filePath);
            const document = await vscode.workspace.openTextDocument(fullPath);
            const editor = await vscode.window.showTextDocument(document);

            if (startLine !== undefined) {
                const line = Math.max(0, startLine - 1);
                const endLineNum = endLine ? Math.max(0, endLine - 1) : line;
                const range = new vscode.Range(line, 0, endLineNum, 0);
                editor.selection = new vscode.Selection(range.start, range.end);
                editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to open file: ${error}`);
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ContextForge Results</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
            padding: 10px;
            margin: 0;
        }
        .result-container {
            margin-bottom: 20px;
        }
        .question {
            font-weight: bold;
            margin-bottom: 10px;
            color: var(--vscode-textLink-foreground);
        }
        .answer {
            margin-bottom: 15px;
            line-height: 1.5;
            white-space: pre-wrap;
        }
        .contexts {
            margin-bottom: 15px;
        }
        .context-item {
            border: 1px solid var(--vscode-panel-border);
            border-radius: 4px;
            margin-bottom: 10px;
            padding: 10px;
            background-color: var(--vscode-editor-background);
        }
        .context-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            font-size: 0.9em;
            color: var(--vscode-descriptionForeground);
        }
        .context-file {
            cursor: pointer;
            color: var(--vscode-textLink-foreground);
            text-decoration: underline;
        }
        .context-file:hover {
            color: var(--vscode-textLink-activeForeground);
        }
        .context-score {
            font-weight: bold;
        }
        .context-text {
            font-family: var(--vscode-editor-font-family);
            font-size: 0.9em;
            background-color: var(--vscode-textCodeBlock-background);
            padding: 8px;
            border-radius: 3px;
            overflow-x: auto;
            white-space: pre-wrap;
        }
        .web-results {
            margin-bottom: 15px;
        }
        .web-result {
            border: 1px solid var(--vscode-panel-border);
            border-radius: 4px;
            margin-bottom: 8px;
            padding: 8px;
        }
        .web-title {
            font-weight: bold;
            color: var(--vscode-textLink-foreground);
            margin-bottom: 4px;
        }
        .web-url {
            font-size: 0.8em;
            color: var(--vscode-descriptionForeground);
            margin-bottom: 4px;
        }
        .web-snippet {
            font-size: 0.9em;
        }
        .meta-info {
            font-size: 0.8em;
            color: var(--vscode-descriptionForeground);
            border-top: 1px solid var(--vscode-panel-border);
            padding-top: 10px;
        }
        .copy-button {
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 4px 8px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 0.8em;
        }
        .copy-button:hover {
            background-color: var(--vscode-button-hoverBackground);
        }
        .empty-state {
            text-align: center;
            color: var(--vscode-descriptionForeground);
            margin-top: 50px;
        }
        .section-title {
            font-weight: bold;
            margin-bottom: 10px;
            color: var(--vscode-textLink-foreground);
        }
        .auto-terminal-results {
            margin: 15px 0;
            border: 1px solid var(--vscode-panel-border);
            border-radius: 5px;
            padding: 10px;
            background-color: var(--vscode-editor-background);
        }
        .auto-terminal-item {
            margin-bottom: 10px;
            padding: 8px;
            border-left: 3px solid var(--vscode-textLink-foreground);
            background-color: var(--vscode-input-background);
        }
        .auto-terminal-command {
            font-family: monospace;
            font-weight: bold;
            color: var(--vscode-terminal-ansiGreen);
            margin-bottom: 5px;
        }
        .auto-terminal-output {
            font-family: monospace;
            font-size: 0.9em;
            white-space: pre-wrap;
            background-color: var(--vscode-terminal-background);
            color: var(--vscode-terminal-foreground);
            padding: 5px;
            border-radius: 3px;
            margin: 5px 0;
        }
        .auto-terminal-error {
            color: var(--vscode-terminal-ansiRed);
        }
        .auto-terminal-success {
            border-left-color: var(--vscode-terminal-ansiGreen);
        }
        .auto-terminal-failed {
            border-left-color: var(--vscode-terminal-ansiRed);
        }
        .auto-terminal-meta {
            font-size: 0.8em;
            color: var(--vscode-descriptionForeground);
        }
    </style>
</head>
<body>
    <div id="content">
        <div class="empty-state">
            <p>Ask ContextForge a question to see results here.</p>
            <p>Use Ctrl+Shift+C (Cmd+Shift+C on Mac) to open the query dialog.</p>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();

        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.type) {
                case 'showResults':
                    showResults(message.data);
                    break;
            }
        });

        function showResults(response) {
            const content = document.getElementById('content');
            content.innerHTML = \`
                <div class="result-container">
                    <div class="question">Q: \${escapeHtml(response.question)}</div>
                    <div class="answer">\${escapeHtml(response.answer)}</div>
                    
                    \${response.contexts && response.contexts.length > 0 ? \`
                        <div class="contexts">
                            <div class="section-title">📄 Code Contexts (\${response.contexts.length})</div>
                            \${response.contexts.map((context, index) => \`
                                <div class="context-item">
                                    <div class="context-header">
                                        <span class="context-file" onclick="openFile('\${context.meta.file_path}', \${context.meta.start_line}, \${context.meta.end_line})">
                                            \${context.meta.file_path || 'Unknown file'}
                                            \${context.meta.start_line ? \` (lines \${context.meta.start_line}-\${context.meta.end_line || context.meta.start_line})\` : ''}
                                        </span>
                                        <span class="context-score">Score: \${context.score.toFixed(3)}</span>
                                    </div>
                                    <div class="context-text">\${escapeHtml(context.text)}</div>
                                    <button class="copy-button" onclick="copyText('\${escapeHtml(context.text)}')">Copy</button>
                                </div>
                            \`).join('')}
                        </div>
                    \` : ''}
                    
                    \${response.web_results && response.web_results.length > 0 ? \`
                        <div class="web-results">
                            <div class="section-title">🌐 Web Results (\${response.web_results.length})</div>
                            \${response.web_results.map(result => \`
                                <div class="web-result">
                                    <div class="web-title">\${escapeHtml(result.title)}</div>
                                    <div class="web-url">\${escapeHtml(result.url)}</div>
                                    <div class="web-snippet">\${escapeHtml(result.snippet)}</div>
                                </div>
                            \`).join('')}
                        </div>
                    \` : ''}

                    \${response.auto_terminal_results && response.auto_terminal_results.length > 0 ? \`
                        <div class="auto-terminal-results">
                            <div class="section-title">⚡ Auto-Executed Commands (\${response.auto_terminal_results.length})</div>
                            \${response.auto_terminal_results.map(result => \`
                                <div class="auto-terminal-item \${result.exit_code === 0 ? 'auto-terminal-success' : 'auto-terminal-failed'}">
                                    <div class="auto-terminal-command">$ \${escapeHtml(result.command)}</div>
                                    \${result.stdout ? \`<div class="auto-terminal-output">\${escapeHtml(result.stdout)}</div>\` : ''}
                                    \${result.stderr ? \`<div class="auto-terminal-output auto-terminal-error">\${escapeHtml(result.stderr)}</div>\` : ''}
                                    <div class="auto-terminal-meta">
                                        Exit Code: \${result.exit_code} |
                                        Execution Time: \${result.execution_time.toFixed(2)}s |
                                        Whitelist Match: \${result.matched_whitelist ? '✅' : '❌'}
                                    </div>
                                </div>
                            \`).join('')}
                        </div>
                    \` : ''}
                    
                    <div class="meta-info">
                        Backend: \${response.meta.backend} |
                        Latency: \${response.meta.total_latency_ms}ms |
                        Contexts: \${response.meta.num_contexts} |
                        Web Results: \${response.meta.num_web_results}
                        \${response.meta.auto_commands_executed ? \` | Auto Commands: \${response.meta.auto_commands_executed}\` : ''}
                    </div>
                </div>
            \`;
        }

        function openFile(filePath, startLine, endLine) {
            vscode.postMessage({
                type: 'openFile',
                filePath: filePath,
                startLine: startLine,
                endLine: endLine
            });
        }

        function copyText(text) {
            vscode.postMessage({
                type: 'copyText',
                text: text
            });
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>`;
    }
}

export function activate(context: vscode.ExtensionContext) {
    console.log('ContextForge extension is now active');

    // Set context for when extension is enabled
    vscode.commands.executeCommand('setContext', 'contextforge.enabled', true);

    // Get configuration
    const getConfig = (): ContextForgeConfig => {
        const config = vscode.workspace.getConfiguration('contextforge');
        return {
            apiUrl: config.get('apiUrl', 'http://localhost:8080'),
            webUiUrl: config.get('webUiUrl', 'http://localhost:3000'),
            autoIngest: config.get('autoIngest', false),
            maxResults: config.get('maxResults', 10),
            enableWebSearch: config.get('enableWebSearch', true),
            showLineNumbers: config.get('showLineNumbers', true),
            autoTerminalMode: config.get('autoTerminalMode', false),
            autoTerminalTimeout: config.get('autoTerminalTimeout', 30),
            autoTerminalWhitelist: config.get('autoTerminalWhitelist', [
                'git status',
                'git log --oneline -10',
                'npm test',
                'npm run test',
                'python -m pytest',
                'pytest',
                'ls',
                'ls -la',
                'pwd',
                'whoami',
                'node --version',
                'python --version',
                'npm --version'
            ]),
            chatHistoryEnabled: config.get('chatHistoryEnabled', true),
            chatMaxHistory: config.get('chatMaxHistory', 50),
            fileAttachmentsEnabled: config.get('fileAttachmentsEnabled', true),
            maxFileSize: config.get('maxFileSize', 10 * 1024 * 1024),
            allowedFileTypes: config.get('allowedFileTypes', ['image/*', 'application/pdf', 'text/*']),
            gitEnabled: config.get('gitEnabled', true),
            vcsProvider: config.get('vcsProvider', ''),
            githubToken: config.get('githubToken', ''),
            gitlabToken: config.get('gitlabToken', ''),
            gitlabUrl: config.get('gitlabUrl', 'https://gitlab.com'),
            bitbucketToken: config.get('bitbucketToken', ''),
            bitbucketUsername: config.get('bitbucketUsername', ''),
            autoCommitMessages: config.get('autoCommitMessages', true),
            defaultBranch: config.get('defaultBranch', 'main'),
            incrementalIndexing: config.get('incrementalIndexing', true),
            privacyMode: config.get('privacyMode', false),
            enableInlineCompletion: config.get('enableInlineCompletion', true),
            enableAutoLint: config.get('enableAutoLint', true),
        };
    };

    let config = getConfig();

    // Update config when settings change
    vscode.workspace.onDidChangeConfiguration(e => {
        if (e.affectsConfiguration('contextforge')) {
            config = getConfig();
            provider.refresh();
            updateStatusBar();
        }
    });

    // Create provider for refresh functionality
    const provider = new ContextForgeProvider(config);

    // Create webview provider for index view
    const webviewProvider = new ContextForgeWebviewProvider(context.extensionUri, config);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(ContextForgeWebviewProvider.viewType, webviewProvider)
    );

    // Create chat provider
    const chatProvider = new ContextForgeChatProvider(context.extensionUri, config);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(ContextForgeChatProvider.viewType, chatProvider)
    );

    // Create prompt provider
    const promptProvider = new ContextForgePromptProvider(context.extensionUri);
    promptProvider.setConfig(config);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(ContextForgePromptProvider.viewType, promptProvider)
    );

    // Create agent status provider
    const agentProvider = new AgentStatusProvider(context.extensionUri, config);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(AgentStatusProvider.viewType, agentProvider)
    );

    // Create task panel provider
    const taskPanelProvider = new TaskPanelProvider(context.extensionUri, { apiUrl: config.apiUrl });
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(TaskPanelProvider.viewType, taskPanelProvider)
    );

    // Create status bar item for auto-terminal mode
    const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'contextforge.toggleAutoTerminal';

    const updateStatusBar = () => {
        const currentConfig = getConfig();
        if (currentConfig.autoTerminalMode) {
            statusBarItem.text = "$(zap) Auto";
            statusBarItem.tooltip = "Auto Terminal Mode: ENABLED (Click to disable)\nWARNING: Commands will be executed automatically!";
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        } else {
            statusBarItem.text = "$(terminal) Manual";
            statusBarItem.tooltip = "Auto Terminal Mode: DISABLED (Click to enable)\nCommands require manual confirmation";
            statusBarItem.backgroundColor = undefined;
        }
        statusBarItem.show();
    };

    updateStatusBar();
    context.subscriptions.push(statusBarItem);

    // Register commands
    const askCommand = vscode.commands.registerCommand('contextforge.ask', async () => {
        const question = await vscode.window.showInputBox({
            prompt: 'Ask ContextForge a question about your codebase',
            placeHolder: 'e.g., How does authentication work in this project?'
        });

        if (question) {
            await queryContextForge(question, config, webviewProvider);
        }
    });

    const ingestCommand = vscode.commands.registerCommand('contextforge.ingestWorkspace', async () => {
        await ingestWorkspace(config, provider);
    });

    const openIndexPanelCommand = vscode.commands.registerCommand('contextforge.openIndexPanel', () => {
        vscode.commands.executeCommand('contextforge.indexView.focus');
    });

    const clearIndexCommand = vscode.commands.registerCommand('contextforge.clearIndex', async () => {
        const result = await vscode.window.showWarningMessage(
            'Are you sure you want to clear the entire index?',
            'Yes', 'No'
        );

        if (result === 'Yes') {
            await clearIndex(config, provider);
        }
    });

    const showSettingsCommand = vscode.commands.registerCommand('contextforge.showSettings', () => {
        vscode.commands.executeCommand('workbench.action.openSettings', 'contextforge');
    });

    const executeTerminalCommand = vscode.commands.registerCommand('contextforge.executeTerminal', async () => {
        const command = await vscode.window.showInputBox({
            prompt: 'Enter terminal command to execute',
            placeHolder: 'e.g., npm install, python -m pytest, git status'
        });

        if (command) {
            await executeCommand(command, config, webviewProvider);
        }
    });

    const suggestTerminalCommand = vscode.commands.registerCommand('contextforge.suggestTerminal', async () => {
        const task = await vscode.window.showInputBox({
            prompt: 'Describe what you want to accomplish',
            placeHolder: 'e.g., install dependencies, run tests, build project'
        });

        if (task) {
            await suggestCommand(task, config, webviewProvider);
        }
    });

    const showTerminalProcesses = vscode.commands.registerCommand('contextforge.showTerminalProcesses', async () => {
        await showActiveProcesses(config);
    });

    const toggleAutoTerminalCommand = vscode.commands.registerCommand('contextforge.toggleAutoTerminal', async () => {
        await toggleAutoTerminalMode(config, updateStatusBar);
    });

    // Chat commands
    const openChatCommand = vscode.commands.registerCommand('contextforge.openChat', () => {
        chatProvider.openChat();
    });

    const openPublishHubCommand = vscode.commands.registerCommand('contextforge.openPublishHub', () => {
        const c = getConfig();
        const base = (c.webUiUrl || 'http://localhost:3000').replace(/\/$/, '');
        vscode.env.openExternal(vscode.Uri.parse(`${base}/publish`));
    });

    const openPromptGeneratorCommand = vscode.commands.registerCommand('contextforge.openPromptGenerator', () => {
        vscode.commands.executeCommand('contextforge.promptView.focus');
    });

    const clearChatHistoryCommand = vscode.commands.registerCommand('contextforge.clearChatHistory', async () => {
        const result = await vscode.window.showWarningMessage(
            'Are you sure you want to clear all chat history?',
            'Yes', 'No'
        );

        if (result === 'Yes') {
            vscode.commands.executeCommand('workbench.action.reloadWindow');
        }
    });

    // Git Integration
    let gitIntegration: GitIntegration | null = null;

    if (config.gitEnabled && vscode.workspace.workspaceFolders) {
        const workspaceRoot = vscode.workspace.workspaceFolders[0].uri.fsPath;
        gitIntegration = new GitIntegration(workspaceRoot, toGitConfig(config), config.apiUrl);
    }

    // Git Commands
    const gitStatusCommand = vscode.commands.registerCommand('contextforge.gitStatus', async () => {
        if (!gitIntegration) {
            vscode.window.showErrorMessage('Git integration is not enabled or no workspace folder found');
            return;
        }

        try {
            const isRepo = await gitIntegration.isGitRepository();
            if (!isRepo) {
                vscode.window.showErrorMessage('Current workspace is not a Git repository');
                return;
            }

            const status = await gitIntegration.getStatus();
            const currentBranch = await gitIntegration.getCurrentBranch();

            let statusMessage = `Branch: ${currentBranch}\n`;

            if (status.files.length === 0) {
                statusMessage += 'Working tree clean';
            } else {
                statusMessage += `\nModified: ${status.modified.length}`;
                statusMessage += `\nStaged: ${status.staged.length}`;
                statusMessage += `\nUntracked: ${status.not_added.length}`;
                statusMessage += `\nDeleted: ${status.deleted.length}`;
            }

            vscode.window.showInformationMessage(statusMessage, 'Open Git Panel').then(selection => {
                if (selection === 'Open Git Panel') {
                    vscode.commands.executeCommand('workbench.view.scm');
                }
            });

        } catch (error) {
            vscode.window.showErrorMessage(`Git status failed: ${error}`);
        }
    });

    const gitCommitCommand = vscode.commands.registerCommand('contextforge.gitCommit', async () => {
        if (!gitIntegration) {
            vscode.window.showErrorMessage('Git integration is not enabled or no workspace folder found');
            return;
        }

        try {
            const isRepo = await gitIntegration.isGitRepository();
            if (!isRepo) {
                vscode.window.showErrorMessage('Current workspace is not a Git repository');
                return;
            }

            // Check if there are staged changes
            const status = await gitIntegration.getStatus();
            if (status.staged.length === 0) {
                const addAll = await vscode.window.showQuickPick(['Yes', 'No'], {
                    placeHolder: 'No staged changes found. Add all changes?'
                });

                if (addAll !== 'Yes') {
                    return;
                }
            }

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'Generating commit message...',
                cancellable: false
            }, async () => {
                await gitIntegration!.commit(undefined, status.staged.length === 0);
            });

        } catch (error) {
            vscode.window.showErrorMessage(`Git commit failed: ${error}`);
        }
    });

    const gitPushCommand = vscode.commands.registerCommand('contextforge.gitPush', async () => {
        if (!gitIntegration) {
            vscode.window.showErrorMessage('Git integration is not enabled or no workspace folder found');
            return;
        }

        try {
            const isRepo = await gitIntegration.isGitRepository();
            if (!isRepo) {
                vscode.window.showErrorMessage('Current workspace is not a Git repository');
                return;
            }

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'Pushing to remote...',
                cancellable: false
            }, async () => {
                await gitIntegration!.push();
            });

            vscode.window.showInformationMessage('Successfully pushed to remote');

        } catch (error) {
            vscode.window.showErrorMessage(`Git push failed: ${error}`);
        }
    });

    const gitPullCommand = vscode.commands.registerCommand('contextforge.gitPull', async () => {
        if (!gitIntegration) {
            vscode.window.showErrorMessage('Git integration is not enabled or no workspace folder found');
            return;
        }

        try {
            const isRepo = await gitIntegration.isGitRepository();
            if (!isRepo) {
                vscode.window.showErrorMessage('Current workspace is not a Git repository');
                return;
            }

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'Pulling from remote...',
                cancellable: false
            }, async () => {
                await gitIntegration!.pull();
            });

            vscode.window.showInformationMessage('Successfully pulled from remote');

        } catch (error) {
            vscode.window.showErrorMessage(`Git pull failed: ${error}`);
        }
    });

    // Update config for providers when settings change
    vscode.workspace.onDidChangeConfiguration(e => {
        if (e.affectsConfiguration('contextforge')) {
            const newConfig = getConfig();
            chatProvider.updateConfig(newConfig);
            agentProvider.updateConfig(newConfig);
            taskPanelProvider.updateConfig({ apiUrl: newConfig.apiUrl });

            // Update Git integration config
            if (gitIntegration && newConfig.gitEnabled) {
                gitIntegration = new GitIntegration(
                    vscode.workspace.workspaceFolders![0].uri.fsPath,
                    toGitConfig(newConfig),
                    newConfig.apiUrl
                );
            }
        }
    });

    // Branch Management Command
    const gitBranchCommand = vscode.commands.registerCommand('contextforge.gitBranch', async () => {
        if (!gitIntegration) {
            vscode.window.showErrorMessage('Git integration is not enabled or no workspace folder found');
            return;
        }

        try {
            const isRepo = await gitIntegration.isGitRepository();
            if (!isRepo) {
                vscode.window.showErrorMessage('Current workspace is not a Git repository');
                return;
            }

            const action = await vscode.window.showQuickPick([
                'Create new branch',
                'Switch branch',
                'Delete branch',
                'View all branches'
            ], { placeHolder: 'Select branch action' });

            if (!action) {
                return;
            }

            const branches = await gitIntegration.getBranches();
            const currentBranch = branches.current;

            switch (action) {
                case 'Create new branch':
                    const newBranchName = await vscode.window.showInputBox({
                        prompt: 'Enter new branch name',
                        placeHolder: 'feature/new-feature'
                    });
                    if (newBranchName) {
                        await gitIntegration.createBranch(newBranchName);
                        vscode.window.showInformationMessage(`Created and switched to branch: ${newBranchName}`);
                    }
                    break;

                case 'Switch branch':
                    const branchNames = Object.keys(branches.branches).filter(name => name !== currentBranch);
                    const selectedBranch = await vscode.window.showQuickPick(branchNames, {
                        placeHolder: 'Select branch to switch to'
                    });
                    if (selectedBranch) {
                        await gitIntegration.switchBranch(selectedBranch);
                        vscode.window.showInformationMessage(`Switched to branch: ${selectedBranch}`);
                    }
                    break;

                case 'Delete branch':
                    const deletableBranches = Object.keys(branches.branches).filter(name => name !== currentBranch);
                    const branchToDelete = await vscode.window.showQuickPick(deletableBranches, {
                        placeHolder: 'Select branch to delete'
                    });
                    if (branchToDelete) {
                        const confirm = await vscode.window.showWarningMessage(
                            `Delete branch "${branchToDelete}"?`,
                            'Delete', 'Cancel'
                        );
                        if (confirm === 'Delete') {
                            await gitIntegration.deleteBranch(branchToDelete);
                            vscode.window.showInformationMessage(`Deleted branch: ${branchToDelete}`);
                        }
                    }
                    break;

                case 'View all branches':
                    const branchList = Object.entries(branches.branches)
                        .map(([name, info]) => `${name === currentBranch ? '* ' : '  '}${name}`)
                        .join('\n');
                    vscode.window.showInformationMessage(`Branches:\n${branchList}`);
                    break;
            }

        } catch (error) {
            vscode.window.showErrorMessage(`Branch operation failed: ${error}`);
        }
    });

    // GitHub PR Command
    const githubPRCommand = vscode.commands.registerCommand('contextforge.githubPR', async () => {
        if (!gitIntegration) {
            vscode.window.showErrorMessage('Git integration is not enabled or no workspace folder found');
            return;
        }

        try {
            const isRepo = await gitIntegration.isGitRepository();
            if (!isRepo) {
                vscode.window.showErrorMessage('Current workspace is not a Git repository');
                return;
            }

            if (!config.githubToken) {
                vscode.window.showErrorMessage('GitHub token not configured. Please set contextforge.githubToken in settings.');
                return;
            }

            const title = await vscode.window.showInputBox({
                prompt: 'Enter PR title',
                placeHolder: 'feat: add new feature'
            });

            if (!title) {
                return;
            }

            const body = await vscode.window.showInputBox({
                prompt: 'Enter PR description (optional)',
                placeHolder: 'Describe your changes...'
            });

            const baseBranch = await vscode.window.showInputBox({
                prompt: 'Enter base branch',
                value: config.defaultBranch,
                placeHolder: 'main'
            });

            if (!baseBranch) {
                return;
            }

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'Creating pull request...',
                cancellable: false
            }, async () => {
                await gitIntegration!.createPullRequest(title, body || '', baseBranch);
            });

        } catch (error) {
            vscode.window.showErrorMessage(`Failed to create PR: ${error}`);
        }
    });

    // GitHub Issues Command
    const githubIssuesCommand = vscode.commands.registerCommand('contextforge.githubIssues', async () => {
        if (!gitIntegration) {
            vscode.window.showErrorMessage('Git integration is not enabled or no workspace folder found');
            return;
        }

        try {
            if (!config.githubToken) {
                vscode.window.showErrorMessage('GitHub token not configured. Please set contextforge.githubToken in settings.');
                return;
            }

            const issues = await gitIntegration.getIssues();

            if (issues.length === 0) {
                vscode.window.showInformationMessage('No open issues found');
                return;
            }

            const issueItems = issues.map(issue => ({
                label: `#${issue.number}: ${issue.title}`,
                description: issue.user.login,
                detail: issue.body?.substring(0, 100) + (issue.body?.length > 100 ? '...' : ''),
                issue: issue
            }));

            const selectedIssue = await vscode.window.showQuickPick(issueItems, {
                placeHolder: 'Select an issue to view'
            });

            if (selectedIssue) {
                vscode.env.openExternal(vscode.Uri.parse(selectedIssue.issue.html_url));
            }

        } catch (error) {
            vscode.window.showErrorMessage(`Failed to fetch issues: ${error}`);
        }
    });

    // Orchestration commands
    const runOrchestrationCommand = vscode.commands.registerCommand('contextforge.runOrchestration', async () => {
        await runOrchestration(config, webviewProvider);
    });

    const checkLLMStatusCommand = vscode.commands.registerCommand('contextforge.checkLLMStatus', async () => {
        await checkLLMStatus(config);
    });

    // ── Feature #19: Privacy mode toggle ──
    const privacyStatusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 99);
    privacyStatusBar.command = 'contextforge.togglePrivacy';
    const updatePrivacyBar = () => {
        const c = getConfig();
        privacyStatusBar.text = c.privacyMode ? '$(shield) Private' : '$(globe) Cloud';
        privacyStatusBar.tooltip = c.privacyMode
            ? 'Privacy Mode ON: code stays local'
            : 'Privacy Mode OFF: code may be sent to cloud LLMs';
        privacyStatusBar.show();
    };
    updatePrivacyBar();
    context.subscriptions.push(privacyStatusBar);

    const togglePrivacyCommand = vscode.commands.registerCommand('contextforge.togglePrivacy', async () => {
        const current = getConfig().privacyMode;
        await vscode.workspace.getConfiguration('contextforge').update('privacyMode', !current, vscode.ConfigurationTarget.Global);
        updatePrivacyBar();
        vscode.window.showInformationMessage(`Privacy mode ${!current ? 'ENABLED' : 'DISABLED'}`);
    });

    // ── Feature #7: Project rules (.contextforge-rules) ──
    let projectRules: string | undefined;
    const loadProjectRules = () => {
        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!ws) { return; }
        const candidates = ['.contextforge-rules', '.contextforge/rules.md', '.contextforge/rules.txt'];
        for (const c of candidates) {
            const p = path.join(ws, c);
            try {
                if (fs.existsSync(p)) {
                    projectRules = fs.readFileSync(p, 'utf-8');
                    return;
                }
            } catch {}
        }
        projectRules = undefined;
    };
    loadProjectRules();
    const rulesWatcher = vscode.workspace.createFileSystemWatcher('**/.contextforge*');
    rulesWatcher.onDidChange(loadProjectRules);
    rulesWatcher.onDidCreate(loadProjectRules);
    rulesWatcher.onDidDelete(() => { projectRules = undefined; });
    context.subscriptions.push(rulesWatcher);

    // ── Feature #12: Undo/redo of AI changes ──
    interface AICheckpoint {
        uri: string;
        content: string;
        timestamp: number;
        label: string;
    }
    const aiCheckpoints: AICheckpoint[] = [];
    const MAX_CHECKPOINTS = 50;

    const saveCheckpoint = (uri: vscode.Uri, label: string) => {
        try {
            const content = fs.readFileSync(uri.fsPath, 'utf-8');
            aiCheckpoints.push({ uri: uri.fsPath, content, timestamp: Date.now(), label });
            if (aiCheckpoints.length > MAX_CHECKPOINTS) { aiCheckpoints.shift(); }
        } catch {}
    };

    const undoAICommand = vscode.commands.registerCommand('contextforge.undoAIChange', async () => {
        if (aiCheckpoints.length === 0) {
            vscode.window.showInformationMessage('No AI checkpoints to undo');
            return;
        }
        const items = aiCheckpoints.map((cp, i) => ({
            label: cp.label,
            description: path.basename(cp.uri) + ' - ' + new Date(cp.timestamp).toLocaleTimeString(),
            index: i
        })).reverse();
        const pick = await vscode.window.showQuickPick(items, { placeHolder: 'Select checkpoint to restore' });
        if (pick) {
            const cp = aiCheckpoints[pick.index];
            fs.writeFileSync(cp.uri, cp.content, 'utf-8');
            const doc = await vscode.workspace.openTextDocument(cp.uri);
            await vscode.window.showTextDocument(doc);
            aiCheckpoints.splice(pick.index);
            vscode.window.showInformationMessage(`Restored: ${cp.label}`);
        }
    });

    // ── Feature #11: Auto linting after AI edits ──
    const diagnosticsProvider = new DiagnosticsProvider();
    context.subscriptions.push({ dispose: () => diagnosticsProvider.dispose() });

    const autoLintAfterEdit = async (filePath: string) => {
        if (!getConfig().enableAutoLint) { return; }
        await new Promise(r => setTimeout(r, 1500));
        const errors = diagnosticsProvider.getErrors([filePath]);
        if (errors.length > 0) {
            const fix = await vscode.window.showWarningMessage(
                `${errors.length} error(s) detected after AI edit. Ask AI to fix?`,
                'Auto-fix', 'Ignore'
            );
            if (fix === 'Auto-fix') {
                const errorText = diagnosticsProvider.formatDiagnostics(errors);
                chatProvider.sendMessage(`Fix the following lint errors in ${path.basename(filePath)}:\n${errorText}`);
            }
        }
    };

    // ── Feature #4: Diff preview before applying ──
    const showDiffPreview = async (originalUri: vscode.Uri, newContent: string, title: string): Promise<boolean> => {
        const scheme = 'contextforge-preview';
        const provider = new (class implements vscode.TextDocumentContentProvider {
            private _content = newContent;
            provideTextDocumentContent(): string { return this._content; }
        })();
        const reg = vscode.workspace.registerTextDocumentContentProvider(scheme, provider);
        const previewUri = vscode.Uri.parse(`${scheme}:${originalUri.path}?preview`);
        await vscode.commands.executeCommand('vscode.diff', originalUri, previewUri, title);
        const choice = await vscode.window.showInformationMessage('Apply this change?', 'Apply', 'Reject');
        reg.dispose();
        return choice === 'Apply';
    };

    // ── Feature #10: Smart apply ──
    const smartApplyCommand = vscode.commands.registerCommand('contextforge.smartApply', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) { vscode.window.showWarningMessage('No active editor'); return; }

        const code = await vscode.env.clipboard.readText();
        if (!code.trim()) { vscode.window.showWarningMessage('Clipboard is empty'); return; }

        try {
            const resp = await axios.post(`${getConfig().apiUrl}/smart-apply`, {
                file_path: editor.document.uri.fsPath,
                file_content: editor.document.getText(),
                code_block: code,
                language: editor.document.languageId,
            });
            const result = resp.data;
            if (result.start_line !== undefined) {
                saveCheckpoint(editor.document.uri, 'Before smart apply');
                const startLine = Math.max(0, result.start_line - 1);
                const endLine = result.end_line ? result.end_line : startLine;
                const range = new vscode.Range(startLine, 0, endLine, editor.document.lineAt(Math.min(endLine, editor.document.lineCount - 1)).text.length);
                const applied = await showDiffPreview(editor.document.uri, result.new_content, 'Smart Apply Preview');
                if (applied) {
                    await editor.edit(eb => { eb.replace(range, result.replacement); });
                    autoLintAfterEdit(editor.document.uri.fsPath);
                }
            }
        } catch (e: any) {
            vscode.window.showErrorMessage(`Smart apply failed: ${e.message}`);
        }
    });

    // ── Feature #1: Inline code completion (Tab) ──
    const completionProvider = vscode.languages.registerInlineCompletionItemProvider(
        { pattern: '**' },
        {
            async provideInlineCompletionItems(document, position, context, token) {
                if (!getConfig().enableInlineCompletion) { return []; }
                if (getConfig().privacyMode) {
                    // In privacy mode, only use local model
                }

                const prefix = document.getText(new vscode.Range(
                    Math.max(0, position.line - 50), 0, position.line, position.character
                ));
                const suffix = document.getText(new vscode.Range(
                    position.line, position.character,
                    Math.min(document.lineCount - 1, position.line + 20),
                    document.lineAt(Math.min(document.lineCount - 1, position.line + 20)).text.length
                ));

                try {
                    const resp = await axios.post(`${getConfig().apiUrl}/completion`, {
                        prefix,
                        suffix,
                        language: document.languageId,
                        file_path: document.uri.fsPath,
                        max_tokens: 128,
                        privacy_mode: getConfig().privacyMode,
                    }, { timeout: 5000 });

                    if (token.isCancellationRequested) { return []; }
                    const text = resp.data?.completion;
                    if (!text) { return []; }

                    return [new vscode.InlineCompletionItem(
                        text,
                        new vscode.Range(position, position)
                    )];
                } catch {
                    return [];
                }
            }
        }
    );

    // ── Feature #2: Inline editing (Ctrl+K) ──
    const inlineEditCommand = vscode.commands.registerCommand('contextforge.inlineEdit', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) { return; }

        const selection = editor.selection;
        const selectedText = editor.document.getText(selection);
        if (!selectedText.trim()) {
            vscode.window.showWarningMessage('Select code first, then use Ctrl+K');
            return;
        }

        const instruction = await vscode.window.showInputBox({
            prompt: 'What should ContextForge do with this code?',
            placeHolder: 'e.g., add error handling, optimize, convert to async',
        });
        if (!instruction) { return; }

        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'ContextForge: Editing inline...',
        }, async () => {
            try {
                const resp = await axios.post(`${getConfig().apiUrl}/inline-edit`, {
                    code: selectedText,
                    instruction,
                    language: editor.document.languageId,
                    file_path: editor.document.uri.fsPath,
                    context_before: editor.document.getText(new vscode.Range(
                        Math.max(0, selection.start.line - 10), 0, selection.start.line, 0
                    )),
                    context_after: editor.document.getText(new vscode.Range(
                        selection.end.line, selection.end.character,
                        Math.min(editor.document.lineCount - 1, selection.end.line + 10),
                        editor.document.lineAt(Math.min(editor.document.lineCount - 1, selection.end.line + 10)).text.length
                    )),
                    project_rules: projectRules,
                    privacy_mode: getConfig().privacyMode,
                });
                const newCode = resp.data?.edited_code;
                if (!newCode) { return; }

                saveCheckpoint(editor.document.uri, 'Before inline edit');
                const applied = await showDiffPreview(editor.document.uri,
                    editor.document.getText().substring(0, editor.document.offsetAt(selection.start)) +
                    newCode +
                    editor.document.getText().substring(editor.document.offsetAt(selection.end)),
                    `Inline Edit: ${instruction}`
                );
                if (applied) {
                    await editor.edit(eb => { eb.replace(selection, newCode); });
                    autoLintAfterEdit(editor.document.uri.fsPath);
                }
            } catch (e: any) {
                vscode.window.showErrorMessage(`Inline edit failed: ${e.message}`);
            }
        });
    });

    // ── Feature #3: Multi-file agent mode ──
    const agentModeCommand = vscode.commands.registerCommand('contextforge.agentMode', async () => {
        const task = await vscode.window.showInputBox({
            prompt: 'Describe the task for the AI agent',
            placeHolder: 'e.g., refactor the auth module to use JWT, add tests',
        });
        if (!task) { return; }

        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceRoot) { vscode.window.showErrorMessage('No workspace open'); return; }

        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'ContextForge Agent: Working...',
            cancellable: true,
        }, async (progress, token) => {
            try {
                progress.report({ message: 'Planning changes...' });
                const resp = await axios.post(`${getConfig().apiUrl}/agent/execute`, {
                    task,
                    repo_path: workspaceRoot,
                    mode: 'auto',
                    project_rules: projectRules,
                    privacy_mode: getConfig().privacyMode,
                    dry_run: true,
                }, { timeout: 120000 });

                if (token.isCancellationRequested) { return; }

                const result = resp.data;
                const fileChanges: Array<{ path: string; diff: string; newContent: string }> = result.changes || [];

                if (fileChanges.length === 0) {
                    vscode.window.showInformationMessage('Agent found no changes needed');
                    return;
                }

                progress.report({ message: `Reviewing ${fileChanges.length} file(s)...` });

                const accept = await vscode.window.showInformationMessage(
                    `Agent wants to modify ${fileChanges.length} file(s). Review changes?`,
                    'Review & Apply', 'Cancel'
                );
                if (accept !== 'Review & Apply') { return; }

                for (const change of fileChanges) {
                    if (token.isCancellationRequested) { break; }
                    const fullPath = path.isAbsolute(change.path) ? change.path : path.join(workspaceRoot, change.path);
                    const uri = vscode.Uri.file(fullPath);
                    try {
                        saveCheckpoint(uri, `Before agent: ${task.substring(0, 30)}`);
                    } catch {}

                    const applied = await showDiffPreview(uri, change.newContent, `Agent: ${path.basename(change.path)}`);
                    if (applied) {
                        fs.writeFileSync(fullPath, change.newContent, 'utf-8');
                        autoLintAfterEdit(fullPath);
                    }
                }

                vscode.window.showInformationMessage(`Agent completed: ${task.substring(0, 50)}`);
            } catch (e: any) {
                vscode.window.showErrorMessage(`Agent mode failed: ${e.message}`);
            }
        });
    });

    // ── Feature #14: Symbol-level navigation ──
    const symbolDefinitionProvider = vscode.languages.registerDefinitionProvider(
        { pattern: '**' },
        {
            async provideDefinition(document, position, token) {
                const wordRange = document.getWordRangeAtPosition(position);
                if (!wordRange) { return null; }
                const symbol = document.getText(wordRange);

                try {
                    const resp = await axios.post(`${getConfig().apiUrl}/symbols/lookup`, {
                        symbol,
                        file_path: document.uri.fsPath,
                        line: position.line + 1,
                        kind: 'definition',
                    }, { timeout: 5000 });
                    const loc = resp.data?.location;
                    if (loc?.file_path) {
                        const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
                        const fullPath = path.isAbsolute(loc.file_path) ? loc.file_path : path.join(ws, loc.file_path);
                        return new vscode.Location(
                            vscode.Uri.file(fullPath),
                            new vscode.Position(Math.max(0, (loc.line || 1) - 1), 0)
                        );
                    }
                } catch {}
                return null;
            }
        }
    );

    const symbolReferenceProvider = vscode.languages.registerReferenceProvider(
        { pattern: '**' },
        {
            async provideReferences(document, position, _refContext, token) {
                const wordRange = document.getWordRangeAtPosition(position);
                if (!wordRange) { return []; }
                const symbol = document.getText(wordRange);

                try {
                    const resp = await axios.post(`${getConfig().apiUrl}/symbols/lookup`, {
                        symbol,
                        file_path: document.uri.fsPath,
                        line: position.line + 1,
                        kind: 'references',
                    }, { timeout: 5000 });
                    const refs = resp.data?.references || [];
                    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
                    return refs.map((ref: any) => {
                        const fullPath = path.isAbsolute(ref.file_path) ? ref.file_path : path.join(ws, ref.file_path);
                        return new vscode.Location(
                            vscode.Uri.file(fullPath),
                            new vscode.Position(Math.max(0, (ref.line || 1) - 1), 0)
                        );
                    });
                } catch {}
                return [];
            }
        }
    );

    // ── Feature #15: Multi-cursor editing from AI ──
    const multiCursorEditCommand = vscode.commands.registerCommand('contextforge.multiCursorEdit', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) { return; }

        const instruction = await vscode.window.showInputBox({
            prompt: 'Describe multi-cursor edit',
            placeHolder: 'e.g., rename all occurrences of "foo" to "bar", add logging to all functions',
        });
        if (!instruction) { return; }

        try {
            const resp = await axios.post(`${getConfig().apiUrl}/multi-cursor-edit`, {
                file_content: editor.document.getText(),
                instruction,
                language: editor.document.languageId,
                file_path: editor.document.uri.fsPath,
            });
            const edits: Array<{ start_line: number; start_col: number; end_line: number; end_col: number; new_text: string }> = resp.data?.edits || [];
            if (edits.length === 0) { vscode.window.showInformationMessage('No edits suggested'); return; }

            saveCheckpoint(editor.document.uri, `Before multi-cursor: ${instruction.substring(0, 30)}`);
            await editor.edit(eb => {
                for (const edit of edits) {
                    const range = new vscode.Range(
                        Math.max(0, edit.start_line - 1), edit.start_col,
                        Math.max(0, edit.end_line - 1), edit.end_col
                    );
                    eb.replace(range, edit.new_text);
                }
            });
            vscode.window.showInformationMessage(`Applied ${edits.length} edit(s)`);
            autoLintAfterEdit(editor.document.uri.fsPath);
        } catch (e: any) {
            vscode.window.showErrorMessage(`Multi-cursor edit failed: ${e.message}`);
        }
    });

    // ── Feature #8: Documentation indexing ──
    const indexDocsCommand = vscode.commands.registerCommand('contextforge.indexDocs', async () => {
        const url = await vscode.window.showInputBox({
            prompt: 'Enter documentation URL to index',
            placeHolder: 'https://docs.example.com/api-reference',
        });
        if (!url) { return; }

        const label = await vscode.window.showInputBox({
            prompt: 'Label for this documentation (used with @docs)',
            placeHolder: 'e.g., react-docs, fastapi',
        });

        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'Indexing documentation...',
        }, async () => {
            try {
                const resp = await axios.post(`${getConfig().apiUrl}/docs/index`, {
                    url, label: label || url, recursive: true,
                });
                vscode.window.showInformationMessage(`Indexed ${resp.data.pages_indexed || 0} pages from ${url}`);
            } catch (e: any) {
                vscode.window.showErrorMessage(`Doc indexing failed: ${e.message}`);
            }
        });
    });

    // ── Feature #20: Composer (long-running agent) ──
    const composerCommand = vscode.commands.registerCommand('contextforge.composer', async () => {
        const task = await vscode.window.showInputBox({
            prompt: 'Describe a complex, multi-step task for the Composer agent',
            placeHolder: 'e.g., Add user authentication with JWT, create login/register endpoints, add middleware',
        });
        if (!task) { return; }

        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (!workspaceRoot) { vscode.window.showErrorMessage('No workspace open'); return; }

        try {
            const resp = await axios.post(`${getConfig().apiUrl}/composer/start`, {
                task,
                repo_path: workspaceRoot,
                project_rules: projectRules,
                privacy_mode: getConfig().privacyMode,
            });
            const sessionId = resp.data?.session_id;
            if (!sessionId) { return; }

            vscode.window.showInformationMessage(`Composer started (session: ${sessionId}). Check Agent Status panel for progress.`);

            // Poll for status updates
            const pollInterval = setInterval(async () => {
                try {
                    const status = await axios.get(`${getConfig().apiUrl}/composer/status/${sessionId}`);
                    if (status.data.state === 'completed' || status.data.state === 'failed') {
                        clearInterval(pollInterval);
                        if (status.data.state === 'completed') {
                            const changes = status.data.changes || [];
                            if (changes.length > 0) {
                                const apply = await vscode.window.showInformationMessage(
                                    `Composer completed! ${changes.length} file(s) modified.`,
                                    'Review Changes', 'Dismiss'
                                );
                                if (apply === 'Review Changes') {
                                    for (const change of changes) {
                                        const fullPath = path.isAbsolute(change.path) ? change.path : path.join(workspaceRoot, change.path);
                                        const uri = vscode.Uri.file(fullPath);
                                        saveCheckpoint(uri, `Before composer: ${task.substring(0, 30)}`);
                                        const accepted = await showDiffPreview(uri, change.newContent, `Composer: ${path.basename(change.path)}`);
                                        if (accepted) {
                                            fs.writeFileSync(fullPath, change.newContent, 'utf-8');
                                        }
                                    }
                                }
                            } else {
                                vscode.window.showInformationMessage('Composer completed with no file changes.');
                            }
                        } else {
                            vscode.window.showErrorMessage(`Composer failed: ${status.data.error || 'Unknown error'}`);
                        }
                    }
                } catch {}
            }, 3000);

            setTimeout(() => clearInterval(pollInterval), 600000);
        } catch (e: any) {
            vscode.window.showErrorMessage(`Composer failed: ${e.message}`);
        }
    });

    context.subscriptions.push(
        askCommand,
        ingestCommand,
        openIndexPanelCommand,
        clearIndexCommand,
        showSettingsCommand,
        executeTerminalCommand,
        suggestTerminalCommand,
        showTerminalProcesses,
        toggleAutoTerminalCommand,
        openChatCommand,
        openPublishHubCommand,
        openPromptGeneratorCommand,
        clearChatHistoryCommand,
        gitStatusCommand,
        gitCommitCommand,
        gitPushCommand,
        gitPullCommand,
        gitBranchCommand,
        githubPRCommand,
        githubIssuesCommand,
        runOrchestrationCommand,
        checkLLMStatusCommand,
        togglePrivacyCommand,
        undoAICommand,
        smartApplyCommand,
        completionProvider,
        inlineEditCommand,
        agentModeCommand,
        symbolDefinitionProvider,
        symbolReferenceProvider,
        multiCursorEditCommand,
        indexDocsCommand,
        composerCommand,
    );

    // File-save incremental re-indexing
    let reindexTimers: Map<string, NodeJS.Timeout> = new Map();
    const fileSaveWatcher = vscode.workspace.onDidSaveTextDocument(async (document) => {
        const currentConfig = getConfig();
        if (!currentConfig.incrementalIndexing) {
            return;
        }
        const filePath = document.uri.fsPath;
        // Debounce: don't re-index the same file within 2 seconds
        if (reindexTimers.has(filePath)) {
            clearTimeout(reindexTimers.get(filePath)!);
        }
        reindexTimers.set(filePath, setTimeout(async () => {
            reindexTimers.delete(filePath);
            try {
                await axios.post(`${currentConfig.apiUrl}/ingest/file`, {
                    path: filePath,
                    content: document.getText(),
                });
            } catch (err) {
                console.error(`Incremental re-index failed for ${filePath}:`, err);
            }
        }, 2000));
    });
    context.subscriptions.push(fileSaveWatcher);

    // Auto-ingest on startup if enabled
    if (config.autoIngest) {
        setTimeout(() => {
            ingestWorkspace(config, provider);
        }, 2000);
    }

    // Initial refresh
    provider.refresh();
}

function gatherEditorContext(): EditorContextPayload {
    const editor = vscode.window.activeTextEditor;
    let gitDiff: string | undefined;
    try {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (workspaceRoot) {
            gitDiff = execSync('git diff --cached --no-color 2>/dev/null || git diff --no-color 2>/dev/null', {
                cwd: workspaceRoot,
                encoding: 'utf-8',
                timeout: 3000,
                maxBuffer: 100_000,
            }).trim() || undefined;
        }
    } catch {
        gitDiff = undefined;
    }
    return {
        current_file: editor?.document.uri.fsPath,
        current_selection: editor?.document.getText(editor.selection) || undefined,
        cursor_line: editor?.selection.active.line,
        open_files: vscode.window.tabGroups.all
            .flatMap(g => g.tabs)
            .map(t => (t.input as any)?.uri?.fsPath)
            .filter(Boolean) as string[],
        git_diff: gitDiff,
        recent_files: [],
    };
}

async function queryContextForge(question: string, config: ContextForgeConfig, webviewProvider: ContextForgeWebviewProvider) {
    const progress = vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Querying ContextForge...",
        cancellable: false
    }, async (progress) => {
        try {
            progress.report({ increment: 0, message: "Sending query..." });

            const editorContext = gatherEditorContext();

            const response = await axios.post(`${config.apiUrl}/query`, {
                query: question,
                max_tokens: 512,
                enable_web_search: config.enableWebSearch,
                top_k: config.maxResults,
                editor_context: editorContext,
                auto_terminal_mode: config.autoTerminalMode,
                auto_terminal_timeout: config.autoTerminalTimeout,
                auto_terminal_whitelist: config.autoTerminalWhitelist
            });

            progress.report({ increment: 100, message: "Complete" });

            const queryResponse: QueryResponse = response.data;

            // Show notification if auto-commands were executed
            if (queryResponse.auto_terminal_results && queryResponse.auto_terminal_results.length > 0) {
                const executedCommands = queryResponse.auto_terminal_results.length;
                const successfulCommands = queryResponse.auto_terminal_results.filter(r => r.exit_code === 0).length;

                if (successfulCommands === executedCommands) {
                    vscode.window.showInformationMessage(
                        `⚡ Auto-executed ${executedCommands} command(s) successfully`,
                        'View Results'
                    ).then(selection => {
                        if (selection === 'View Results') {
                            webviewProvider.showResults(queryResponse);
                        }
                    });
                } else {
                    vscode.window.showWarningMessage(
                        `⚡ Auto-executed ${executedCommands} command(s): ${successfulCommands} succeeded, ${executedCommands - successfulCommands} failed`,
                        'View Results'
                    ).then(selection => {
                        if (selection === 'View Results') {
                            webviewProvider.showResults(queryResponse);
                        }
                    });
                }
            }

            webviewProvider.showResults(queryResponse);

        } catch (error: any) {
            vscode.window.showErrorMessage(`Query failed: ${error.message}`);
            console.error('Query error:', error);
        }
    });
}

async function ingestWorkspace(config: ContextForgeConfig, provider: ContextForgeProvider) {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
    }

    const workspacePath = workspaceFolders[0].uri.fsPath;

    const progress = vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Ingesting workspace...",
        cancellable: false
    }, async (progress) => {
        try {
            progress.report({ increment: 0, message: "Starting ingestion..." });

            const response = await axios.post(`${config.apiUrl}/ingest`, {
                path: workspacePath,
                recursive: true
            });

            progress.report({ increment: 100, message: "Complete" });

            const ingestResponse: IngestResponse = response.data;
            vscode.window.showInformationMessage(
                `Workspace ingested successfully! ` +
                `Files: ${ingestResponse.stats.files_processed}, ` +
                `Chunks: ${ingestResponse.stats.chunks_indexed}`
            );

            provider.refresh();

        } catch (error: any) {
            vscode.window.showErrorMessage(`Ingestion failed: ${error.message}`);
            console.error('Ingestion error:', error);
        }
    });
}

async function clearIndex(config: ContextForgeConfig, provider: ContextForgeProvider) {
    try {
        await axios.delete(`${config.apiUrl}/index/clear`);
        vscode.window.showInformationMessage('Index cleared successfully');
        provider.refresh();
    } catch (error: any) {
        vscode.window.showErrorMessage(`Failed to clear index: ${error.message}`);
        console.error('Clear index error:', error);
    }
}

async function executeCommand(command: string, config: ContextForgeConfig, webviewProvider: ContextForgeWebviewProvider) {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    const workingDirectory = workspaceFolders ? workspaceFolders[0].uri.fsPath : undefined;

    const progress = vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Executing command...",
        cancellable: true
    }, async (progress, token) => {
        try {
            progress.report({ increment: 0, message: `Running: ${command}` });

            const response = await axios.post(`${config.apiUrl}/terminal/execute`, {
                command: command,
                working_directory: workingDirectory,
                timeout: 60,
                stream: false
            });

            progress.report({ increment: 100, message: "Complete" });

            const result = response.data;

            // Show result in webview
            const terminalResult = {
                question: `Terminal Command: ${command}`,
                answer: `Exit Code: ${result.exit_code}\n\nOutput:\n${result.stdout}\n\nErrors:\n${result.stderr}`,
                contexts: [],
                web_results: [],
                meta: {
                    backend: 'terminal',
                    total_latency_ms: result.execution_time * 1000,
                    num_contexts: 0,
                    num_web_results: 0
                }
            };

            webviewProvider.showResults(terminalResult);

            if (result.exit_code === 0) {
                vscode.window.showInformationMessage(`Command executed successfully in ${result.execution_time.toFixed(2)}s`);
            } else {
                vscode.window.showWarningMessage(`Command failed with exit code ${result.exit_code}`);
            }

        } catch (error: any) {
            if (error.response?.status === 422) {
                vscode.window.showErrorMessage(`Invalid command: ${error.response.data.detail}`);
            } else if (error.response?.status === 408) {
                vscode.window.showErrorMessage('Command timed out');
            } else {
                vscode.window.showErrorMessage(`Command execution failed: ${error.message}`);
            }
            console.error('Command execution error:', error);
        }
    });
}

async function suggestCommand(task: string, config: ContextForgeConfig, webviewProvider: ContextForgeWebviewProvider) {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    const workingDirectory = workspaceFolders ? workspaceFolders[0].uri.fsPath : undefined;

    const progress = vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Generating command suggestions...",
        cancellable: false
    }, async (progress) => {
        try {
            progress.report({ increment: 0, message: "Analyzing task..." });

            const response = await axios.post(`${config.apiUrl}/terminal/suggest`, {
                task_description: task,
                working_directory: workingDirectory
            });

            progress.report({ increment: 100, message: "Complete" });

            const result = response.data;

            // Format suggestions for display
            let suggestionsText = `Suggested commands for: "${task}"\n\n`;
            result.suggestions.forEach((suggestion: any, index: number) => {
                suggestionsText += `${index + 1}. ${suggestion.command}\n   ${suggestion.description}\n\n`;
            });

            // Show result in webview
            const suggestionResult = {
                question: `Command Suggestions: ${task}`,
                answer: suggestionsText,
                contexts: [],
                web_results: [],
                meta: {
                    backend: result.llm_backend,
                    total_latency_ms: 0,
                    num_contexts: 0,
                    num_web_results: 0
                }
            };

            webviewProvider.showResults(suggestionResult);

            // Show quick pick for command selection
            const items = result.suggestions.map((suggestion: any) => ({
                label: suggestion.command,
                description: suggestion.description,
                command: suggestion.command
            }));

            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: 'Select a command to execute (or press Escape to cancel)'
            }) as { label: string; description: string; command: string } | undefined;

            if (selected) {
                const execute = await vscode.window.showInformationMessage(
                    `Execute: ${selected.command}?`,
                    'Execute', 'Cancel'
                );

                if (execute === 'Execute') {
                    await executeCommand(selected.command, config, webviewProvider);
                }
            }

        } catch (error: any) {
            vscode.window.showErrorMessage(`Command suggestion failed: ${error.message}`);
            console.error('Command suggestion error:', error);
        }
    });
}

async function showActiveProcesses(config: ContextForgeConfig) {
    try {
        const response = await axios.get(`${config.apiUrl}/terminal/processes`);
        const processes = response.data;

        if (processes.length === 0) {
            vscode.window.showInformationMessage('No active terminal processes');
            return;
        }

        const items = processes.map((process: any) => ({
            label: `PID ${process.process_id}: ${process.command}`,
            description: `Status: ${process.status} | Started: ${new Date(process.start_time).toLocaleTimeString()}`,
            processId: process.process_id
        }));

        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: 'Select a process to kill (or press Escape to cancel)'
        }) as { label: string; description: string; processId: string } | undefined;

        if (selected) {
            const confirm = await vscode.window.showWarningMessage(
                `Kill process ${selected.processId}?`,
                'Kill', 'Cancel'
            );

            if (confirm === 'Kill') {
                await axios.delete(`${config.apiUrl}/terminal/processes/${selected.processId}`);
                vscode.window.showInformationMessage(`Process ${selected.processId} killed`);
            }
        }

    } catch (error: any) {
        vscode.window.showErrorMessage(`Failed to get processes: ${error.message}`);
        console.error('Get processes error:', error);
    }
}

async function toggleAutoTerminalMode(config: ContextForgeConfig, updateStatusBar: () => void) {
    const currentMode = config.autoTerminalMode;

    if (!currentMode) {
        // Enabling auto mode - show security warning
        const warningMessage = `⚠️ SECURITY WARNING ⚠️

Auto Terminal Mode will automatically execute terminal commands suggested by the AI without user confirmation.

This feature:
• Only executes commands from your whitelist
• Has a ${config.autoTerminalTimeout}s timeout per command
• Shows notifications when commands are executed

Current whitelist (${config.autoTerminalWhitelist.length} commands):
${config.autoTerminalWhitelist.slice(0, 5).map(cmd => `• ${cmd}`).join('\n')}${config.autoTerminalWhitelist.length > 5 ? '\n• ...' : ''}

Do you want to enable Auto Terminal Mode?`;

        const choice = await vscode.window.showWarningMessage(
            warningMessage,
            { modal: true },
            'Enable Auto Mode',
            'Cancel'
        );

        if (choice !== 'Enable Auto Mode') {
            return;
        }
    }

    // Toggle the setting
    const newMode = !currentMode;
    await vscode.workspace.getConfiguration('contextforge').update(
        'autoTerminalMode',
        newMode,
        vscode.ConfigurationTarget.Global
    );

    // Show confirmation
    if (newMode) {
        vscode.window.showInformationMessage(
            '⚡ Auto Terminal Mode ENABLED - Commands will be executed automatically!',
            'View Settings'
        ).then(selection => {
            if (selection === 'View Settings') {
                vscode.commands.executeCommand('workbench.action.openSettings', 'contextforge.autoTerminal');
            }
        });
    } else {
        vscode.window.showInformationMessage('🛡️ Auto Terminal Mode DISABLED - Manual confirmation required');
    }

    updateStatusBar();
}

async function runOrchestration(config: ContextForgeConfig, webviewProvider: ContextForgeWebviewProvider) {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
    }

    const repoPath = workspaceFolders[0].uri.fsPath;

    // Select analysis mode
    const modeSelection = await vscode.window.showQuickPick([
        { label: '$(radio-tower) Auto', description: 'Auto-detect cloud/local LLM', value: 'auto' },
        { label: '$(cloud) Online', description: 'Force cloud LLM', value: 'online' },
        { label: '$(server) Offline', description: 'Force local LLM (Ollama/LM Studio)', value: 'offline' }
    ], { placeHolder: 'Select LLM mode' });

    if (!modeSelection) {
        return;
    }

    // Select analysis task
    const taskSelection = await vscode.window.showQuickPick([
        { label: '$(beaker) Full Analysis', description: 'Complete architecture + code review', value: 'full_analysis' },
        { label: '$(organization) Architecture', description: 'Architecture analysis only', value: 'architecture' },
        { label: '$(checklist) Code Review', description: 'Code review only', value: 'code_review' }
    ], { placeHolder: 'Select analysis type' });

    if (!taskSelection) {
        return;
    }

    const progress = vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Running ContextForge Analysis...",
        cancellable: false
    }, async (progress) => {
        try {
            progress.report({ increment: 0, message: `Mode: ${modeSelection.value}, Task: ${taskSelection.value}` });

            const response = await axios.post(`${config.apiUrl}/orchestrate`, {
                repo_path: repoPath,
                mode: modeSelection.value,
                task: taskSelection.value,
                output_format: 'markdown'
            });

            const result = response.data;
            progress.report({ increment: 100, message: 'Complete!' });

            // Show result in webview
            const orchestrationResult = {
                question: `Analysis: ${taskSelection.label} (${modeSelection.label})`,
                answer: formatOrchestrationResult(result),
                contexts: [],
                web_results: [],
                meta: {
                    backend: result.offline_mode ? 'local' : 'cloud',
                    total_latency_ms: result.duration_ms,
                    num_contexts: 0,
                    num_web_results: 0
                }
            };

            webviewProvider.showResults(orchestrationResult);

            // Show success notification
            const modeIcon = result.offline_mode ? '🖥️ Local' : '☁️ Cloud';
            vscode.window.showInformationMessage(
                `✅ Analysis complete! ${modeIcon} LLM | ${result.duration_ms}ms`,
                'Open Context File'
            ).then(selection => {
                if (selection === 'Open Context File' && result.context_file) {
                    vscode.workspace.openTextDocument(result.context_file).then(doc => {
                        vscode.window.showTextDocument(doc);
                    });
                }
            });

        } catch (error) {
            vscode.window.showErrorMessage(`Orchestration failed: ${error}`);
        }
    });
}

function formatOrchestrationResult(result: any): string {
    let output = `# ContextForge Analysis Results\n\n`;
    output += `**Status:** ${result.success ? '✅ Success' : '❌ Failed'}\n`;
    output += `**Mode:** ${result.offline_mode ? '🖥️ Local LLM' : '☁️ Cloud LLM'}\n`;
    output += `**Duration:** ${result.duration_ms}ms\n`;
    output += `**Agents Used:** ${result.agents_used?.join(', ') || 'None'}\n\n`;

    if (result.analysis?.scan) {
        output += `## Repository Scan\n`;
        output += `- Files: ${result.analysis.scan.files}\n`;
        output += `- Languages: ${result.analysis.scan.languages?.join(', ')}\n\n`;
    }

    if (result.analysis?.architecture) {
        output += `## Architecture Analysis\n`;
        output += `${result.analysis.architecture.summary || 'N/A'}\n\n`;
    }

    if (result.analysis?.review) {
        output += `## Code Review\n`;
        output += `${result.analysis.review.findings || 'N/A'}\n\n`;
    }

    if (result.context_file) {
        output += `---\n📄 Context file saved to: \`${result.context_file}\`\n`;
    }

    if (result.errors?.length > 0) {
        output += `\n## Errors\n`;
        result.errors.forEach((err: string) => {
            output += `- ⚠️ ${err}\n`;
        });
    }

    return output;
}

async function checkLLMStatus(config: ContextForgeConfig) {
    try {
        const response = await axios.get(`${config.apiUrl}/orchestrate/status`);
        const status = response.data;

        const items = [
            `$(globe) Internet: ${status.internet_available ? '✅ Available' : '❌ Unavailable'}`,
            `$(server) Current Mode: ${status.current_mode}`,
            `$(cloud) Cloud LLM: ${status.backends?.cloud ? '✅' : '❌'}`,
            `$(terminal) Ollama: ${status.backends?.ollama ? '✅ Running' : '❌ Not Running'}`,
            `$(terminal) LM Studio: ${status.backends?.lm_studio ? '✅ Running' : '❌ Not Running'}`
        ];

        vscode.window.showQuickPick(items, {
            placeHolder: 'LLM Backend Status',
            canPickMany: false
        });

    } catch (error) {
        vscode.window.showErrorMessage(`Failed to check LLM status: ${error}`);
    }
}

export function deactivate() {
    console.log('ContextForge extension is now deactivated');
}
