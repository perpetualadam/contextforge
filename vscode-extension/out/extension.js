"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deactivate = exports.activate = void 0;
const vscode = require("vscode");
const axios_1 = require("axios");
const path = require("path");
const chatPanel_1 = require("./chatPanel");
const promptPanel_1 = require("./promptPanel");
const gitIntegration_1 = require("./gitIntegration");
class ContextForgeProvider {
    constructor(config) {
        this.config = config;
        this._onDidChangeTreeData = new vscode.EventEmitter();
        this.onDidChangeTreeData = this._onDidChangeTreeData.event;
        this.indexStats = null;
    }
    refresh() {
        this.loadIndexStats();
        this._onDidChangeTreeData.fire();
    }
    getTreeItem(element) {
        return element;
    }
    getChildren(element) {
        if (!element) {
            return Promise.resolve(this.getRootItems());
        }
        return Promise.resolve([]);
    }
    async loadIndexStats() {
        try {
            const response = await axios_1.default.get(`${this.config.apiUrl}/index/stats`);
            this.indexStats = response.data;
        }
        catch (error) {
            console.error('Failed to load index stats:', error);
            this.indexStats = null;
        }
    }
    getRootItems() {
        const items = [];
        if (this.indexStats) {
            items.push(new ContextItem(`Indexed Vectors: ${this.indexStats.total_vectors || 0}`, vscode.TreeItemCollapsibleState.None, 'info'));
            items.push(new ContextItem(`Embedding Model: ${this.indexStats.embedding_model || 'Unknown'}`, vscode.TreeItemCollapsibleState.None, 'info'));
            items.push(new ContextItem(`Backend: ${this.indexStats.backend || 'Unknown'}`, vscode.TreeItemCollapsibleState.None, 'info'));
        }
        else {
            items.push(new ContextItem('Index not available', vscode.TreeItemCollapsibleState.None, 'error'));
        }
        return items;
    }
}
class ContextItem extends vscode.TreeItem {
    constructor(label, collapsibleState, type) {
        super(label, collapsibleState);
        this.label = label;
        this.collapsibleState = collapsibleState;
        this.type = type;
        this.tooltip = this.label;
        this.contextValue = type;
    }
}
class ContextForgeWebviewProvider {
    constructor(_extensionUri, config) {
        this._extensionUri = _extensionUri;
        this.config = config;
    }
    resolveWebviewView(webviewView, context, _token) {
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
    showResults(response) {
        if (this._view) {
            this._view.show?.(true);
            this._view.webview.postMessage({
                type: 'showResults',
                data: response
            });
        }
    }
    async openFile(filePath, startLine, endLine) {
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
        }
        catch (error) {
            vscode.window.showErrorMessage(`Failed to open file: ${error}`);
        }
    }
    _getHtmlForWebview(webview) {
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
ContextForgeWebviewProvider.viewType = 'contextforge.resultsView';
function activate(context) {
    console.log('ContextForge extension is now active');
    // Set context for when extension is enabled
    vscode.commands.executeCommand('setContext', 'contextforge.enabled', true);
    // Get configuration
    const getConfig = () => {
        const config = vscode.workspace.getConfiguration('contextforge');
        return {
            apiUrl: config.get('apiUrl', 'http://localhost:8080'),
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
            githubToken: config.get('githubToken', ''),
            autoCommitMessages: config.get('autoCommitMessages', true),
            defaultBranch: config.get('defaultBranch', 'main')
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
    // Create tree data provider
    const provider = new ContextForgeProvider(config);
    vscode.window.registerTreeDataProvider('contextforge.indexView', provider);
    // Create webview provider
    const webviewProvider = new ContextForgeWebviewProvider(context.extensionUri, config);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(ContextForgeWebviewProvider.viewType, webviewProvider));
    // Create chat provider
    const chatProvider = new chatPanel_1.ContextForgeChatProvider(context.extensionUri, config);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(chatPanel_1.ContextForgeChatProvider.viewType, chatProvider));
    // Create prompt provider
    const promptProvider = new promptPanel_1.ContextForgePromptProvider(context.extensionUri);
    promptProvider.setConfig(config);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(promptPanel_1.ContextForgePromptProvider.viewType, promptProvider));
    // Create status bar item for auto-terminal mode
    const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'contextforge.toggleAutoTerminal';
    const updateStatusBar = () => {
        const currentConfig = getConfig();
        if (currentConfig.autoTerminalMode) {
            statusBarItem.text = "$(zap) Auto";
            statusBarItem.tooltip = "Auto Terminal Mode: ENABLED (Click to disable)\nWARNING: Commands will be executed automatically!";
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        }
        else {
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
        const result = await vscode.window.showWarningMessage('Are you sure you want to clear the entire index?', 'Yes', 'No');
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
    const openPromptGeneratorCommand = vscode.commands.registerCommand('contextforge.openPromptGenerator', () => {
        vscode.commands.executeCommand('contextforge.promptView.focus');
    });
    const clearChatHistoryCommand = vscode.commands.registerCommand('contextforge.clearChatHistory', async () => {
        const result = await vscode.window.showWarningMessage('Are you sure you want to clear all chat history?', 'Yes', 'No');
        if (result === 'Yes') {
            vscode.commands.executeCommand('workbench.action.reloadWindow');
        }
    });
    // Git Integration
    let gitIntegration = null;
    if (config.gitEnabled && vscode.workspace.workspaceFolders) {
        const workspaceRoot = vscode.workspace.workspaceFolders[0].uri.fsPath;
        gitIntegration = new gitIntegration_1.GitIntegration(workspaceRoot, {
            gitEnabled: config.gitEnabled,
            githubToken: config.githubToken,
            autoCommitMessages: config.autoCommitMessages,
            defaultBranch: config.defaultBranch
        }, config.apiUrl);
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
            }
            else {
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
        }
        catch (error) {
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
                await gitIntegration.commit(undefined, status.staged.length === 0);
            });
        }
        catch (error) {
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
                await gitIntegration.push();
            });
            vscode.window.showInformationMessage('Successfully pushed to remote');
        }
        catch (error) {
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
                await gitIntegration.pull();
            });
            vscode.window.showInformationMessage('Successfully pulled from remote');
        }
        catch (error) {
            vscode.window.showErrorMessage(`Git pull failed: ${error}`);
        }
    });
    // Update config for providers when settings change
    vscode.workspace.onDidChangeConfiguration(e => {
        if (e.affectsConfiguration('contextforge')) {
            const newConfig = getConfig();
            chatProvider.updateConfig(newConfig);
            // Update Git integration config
            if (gitIntegration && newConfig.gitEnabled) {
                gitIntegration = new gitIntegration_1.GitIntegration(vscode.workspace.workspaceFolders[0].uri.fsPath, {
                    gitEnabled: newConfig.gitEnabled,
                    githubToken: newConfig.githubToken,
                    autoCommitMessages: newConfig.autoCommitMessages,
                    defaultBranch: newConfig.defaultBranch
                }, newConfig.apiUrl);
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
            if (!action)
                return;
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
                        const confirm = await vscode.window.showWarningMessage(`Delete branch "${branchToDelete}"?`, 'Delete', 'Cancel');
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
        }
        catch (error) {
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
            if (!title)
                return;
            const body = await vscode.window.showInputBox({
                prompt: 'Enter PR description (optional)',
                placeHolder: 'Describe your changes...'
            });
            const baseBranch = await vscode.window.showInputBox({
                prompt: 'Enter base branch',
                value: config.defaultBranch,
                placeHolder: 'main'
            });
            if (!baseBranch)
                return;
            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: 'Creating pull request...',
                cancellable: false
            }, async () => {
                await gitIntegration.createPullRequest(title, body || '', baseBranch);
            });
        }
        catch (error) {
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
        }
        catch (error) {
            vscode.window.showErrorMessage(`Failed to fetch issues: ${error}`);
        }
    });
    context.subscriptions.push(askCommand, ingestCommand, openIndexPanelCommand, clearIndexCommand, showSettingsCommand, executeTerminalCommand, suggestTerminalCommand, showTerminalProcesses, toggleAutoTerminalCommand, openChatCommand, openPromptGeneratorCommand, clearChatHistoryCommand, gitStatusCommand, gitCommitCommand, gitPushCommand, gitPullCommand, gitBranchCommand, githubPRCommand, githubIssuesCommand);
    // Auto-ingest on startup if enabled
    if (config.autoIngest) {
        setTimeout(() => {
            ingestWorkspace(config, provider);
        }, 2000);
    }
    // Initial refresh
    provider.refresh();
}
exports.activate = activate;
async function queryContextForge(question, config, webviewProvider) {
    const progress = vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Querying ContextForge...",
        cancellable: false
    }, async (progress) => {
        try {
            progress.report({ increment: 0, message: "Sending query..." });
            const response = await axios_1.default.post(`${config.apiUrl}/query`, {
                query: question,
                max_tokens: 512,
                enable_web_search: config.enableWebSearch,
                top_k: config.maxResults,
                auto_terminal_mode: config.autoTerminalMode,
                auto_terminal_timeout: config.autoTerminalTimeout,
                auto_terminal_whitelist: config.autoTerminalWhitelist
            });
            progress.report({ increment: 100, message: "Complete" });
            const queryResponse = response.data;
            // Show notification if auto-commands were executed
            if (queryResponse.auto_terminal_results && queryResponse.auto_terminal_results.length > 0) {
                const executedCommands = queryResponse.auto_terminal_results.length;
                const successfulCommands = queryResponse.auto_terminal_results.filter(r => r.exit_code === 0).length;
                if (successfulCommands === executedCommands) {
                    vscode.window.showInformationMessage(`⚡ Auto-executed ${executedCommands} command(s) successfully`, 'View Results').then(selection => {
                        if (selection === 'View Results') {
                            webviewProvider.showResults(queryResponse);
                        }
                    });
                }
                else {
                    vscode.window.showWarningMessage(`⚡ Auto-executed ${executedCommands} command(s): ${successfulCommands} succeeded, ${executedCommands - successfulCommands} failed`, 'View Results').then(selection => {
                        if (selection === 'View Results') {
                            webviewProvider.showResults(queryResponse);
                        }
                    });
                }
            }
            webviewProvider.showResults(queryResponse);
        }
        catch (error) {
            vscode.window.showErrorMessage(`Query failed: ${error.message}`);
            console.error('Query error:', error);
        }
    });
}
async function ingestWorkspace(config, provider) {
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
            const response = await axios_1.default.post(`${config.apiUrl}/ingest`, {
                path: workspacePath,
                recursive: true
            });
            progress.report({ increment: 100, message: "Complete" });
            const ingestResponse = response.data;
            vscode.window.showInformationMessage(`Workspace ingested successfully! ` +
                `Files: ${ingestResponse.stats.files_processed}, ` +
                `Chunks: ${ingestResponse.stats.chunks_indexed}`);
            provider.refresh();
        }
        catch (error) {
            vscode.window.showErrorMessage(`Ingestion failed: ${error.message}`);
            console.error('Ingestion error:', error);
        }
    });
}
async function clearIndex(config, provider) {
    try {
        await axios_1.default.delete(`${config.apiUrl}/index/clear`);
        vscode.window.showInformationMessage('Index cleared successfully');
        provider.refresh();
    }
    catch (error) {
        vscode.window.showErrorMessage(`Failed to clear index: ${error.message}`);
        console.error('Clear index error:', error);
    }
}
async function executeCommand(command, config, webviewProvider) {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    const workingDirectory = workspaceFolders ? workspaceFolders[0].uri.fsPath : undefined;
    const progress = vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Executing command...",
        cancellable: true
    }, async (progress, token) => {
        try {
            progress.report({ increment: 0, message: `Running: ${command}` });
            const response = await axios_1.default.post(`${config.apiUrl}/terminal/execute`, {
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
            }
            else {
                vscode.window.showWarningMessage(`Command failed with exit code ${result.exit_code}`);
            }
        }
        catch (error) {
            if (error.response?.status === 422) {
                vscode.window.showErrorMessage(`Invalid command: ${error.response.data.detail}`);
            }
            else if (error.response?.status === 408) {
                vscode.window.showErrorMessage('Command timed out');
            }
            else {
                vscode.window.showErrorMessage(`Command execution failed: ${error.message}`);
            }
            console.error('Command execution error:', error);
        }
    });
}
async function suggestCommand(task, config, webviewProvider) {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    const workingDirectory = workspaceFolders ? workspaceFolders[0].uri.fsPath : undefined;
    const progress = vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Generating command suggestions...",
        cancellable: false
    }, async (progress) => {
        try {
            progress.report({ increment: 0, message: "Analyzing task..." });
            const response = await axios_1.default.post(`${config.apiUrl}/terminal/suggest`, {
                task_description: task,
                working_directory: workingDirectory
            });
            progress.report({ increment: 100, message: "Complete" });
            const result = response.data;
            // Format suggestions for display
            let suggestionsText = `Suggested commands for: "${task}"\n\n`;
            result.suggestions.forEach((suggestion, index) => {
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
            const items = result.suggestions.map((suggestion) => ({
                label: suggestion.command,
                description: suggestion.description,
                command: suggestion.command
            }));
            const selected = await vscode.window.showQuickPick(items, {
                placeHolder: 'Select a command to execute (or press Escape to cancel)'
            });
            if (selected) {
                const execute = await vscode.window.showInformationMessage(`Execute: ${selected.command}?`, 'Execute', 'Cancel');
                if (execute === 'Execute') {
                    await executeCommand(selected.command, config, webviewProvider);
                }
            }
        }
        catch (error) {
            vscode.window.showErrorMessage(`Command suggestion failed: ${error.message}`);
            console.error('Command suggestion error:', error);
        }
    });
}
async function showActiveProcesses(config) {
    try {
        const response = await axios_1.default.get(`${config.apiUrl}/terminal/processes`);
        const processes = response.data;
        if (processes.length === 0) {
            vscode.window.showInformationMessage('No active terminal processes');
            return;
        }
        const items = processes.map((process) => ({
            label: `PID ${process.process_id}: ${process.command}`,
            description: `Status: ${process.status} | Started: ${new Date(process.start_time).toLocaleTimeString()}`,
            processId: process.process_id
        }));
        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: 'Select a process to kill (or press Escape to cancel)'
        });
        if (selected) {
            const confirm = await vscode.window.showWarningMessage(`Kill process ${selected.processId}?`, 'Kill', 'Cancel');
            if (confirm === 'Kill') {
                await axios_1.default.delete(`${config.apiUrl}/terminal/processes/${selected.processId}`);
                vscode.window.showInformationMessage(`Process ${selected.processId} killed`);
            }
        }
    }
    catch (error) {
        vscode.window.showErrorMessage(`Failed to get processes: ${error.message}`);
        console.error('Get processes error:', error);
    }
}
async function toggleAutoTerminalMode(config, updateStatusBar) {
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
        const choice = await vscode.window.showWarningMessage(warningMessage, { modal: true }, 'Enable Auto Mode', 'Cancel');
        if (choice !== 'Enable Auto Mode') {
            return;
        }
    }
    // Toggle the setting
    const newMode = !currentMode;
    await vscode.workspace.getConfiguration('contextforge').update('autoTerminalMode', newMode, vscode.ConfigurationTarget.Global);
    // Show confirmation
    if (newMode) {
        vscode.window.showInformationMessage('⚡ Auto Terminal Mode ENABLED - Commands will be executed automatically!', 'View Settings').then(selection => {
            if (selection === 'View Settings') {
                vscode.commands.executeCommand('workbench.action.openSettings', 'contextforge.autoTerminal');
            }
        });
    }
    else {
        vscode.window.showInformationMessage('🛡️ Auto Terminal Mode DISABLED - Manual confirmation required');
    }
    updateStatusBar();
}
function deactivate() {
    console.log('ContextForge extension is now deactivated');
}
exports.deactivate = deactivate;
//# sourceMappingURL=extension.js.map