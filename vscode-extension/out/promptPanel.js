"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ContextForgePromptProvider = void 0;
const vscode = require("vscode");
const axios_1 = require("axios");
class ContextForgePromptProvider {
    constructor(_extensionUri) {
        this._extensionUri = _extensionUri;
        this._promptHistory = [];
        this._promptTemplates = [];
        this._initializeTemplates();
    }
    resolveWebviewView(webviewView, context, _token) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };
        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
        webviewView.webview.onDidReceiveMessage(data => {
            this._handleMessage(data);
        });
    }
    setConfig(config) {
        this._config = config;
    }
    _initializeTemplates() {
        this._promptTemplates = [
            {
                id: 'code-review',
                name: 'Code Review',
                category: 'Development',
                description: 'Review code for quality, performance, and best practices',
                template: 'Please review the following code for:\n- Code quality and readability\n- Performance optimizations\n- Security concerns\n- Best practices\n\nCode:\n${code}',
                variables: ['code']
            },
            {
                id: 'debug-issue',
                name: 'Debug Issue',
                category: 'Development',
                description: 'Help debug and fix code issues',
                template: 'I\'m encountering the following issue:\n${issue}\n\nError message:\n${error}\n\nRelevant code:\n${code}\n\nPlease help me debug and fix this issue.',
                variables: ['issue', 'error', 'code']
            },
            {
                id: 'documentation',
                name: 'Generate Documentation',
                category: 'Documentation',
                description: 'Generate documentation for code',
                template: 'Please generate comprehensive documentation for the following code:\n\n${code}\n\nInclude:\n- Function/class description\n- Parameters and return values\n- Usage examples\n- Edge cases',
                variables: ['code']
            },
            {
                id: 'refactor',
                name: 'Refactor Code',
                category: 'Development',
                description: 'Suggest refactoring improvements',
                template: 'Please suggest refactoring improvements for this code:\n\n${code}\n\nFocus on:\n- Simplification\n- Readability\n- Performance\n- Maintainability',
                variables: ['code']
            },
            {
                id: 'test-generation',
                name: 'Generate Tests',
                category: 'Testing',
                description: 'Generate unit tests for code',
                template: 'Please generate comprehensive unit tests for the following code:\n\n${code}\n\nInclude:\n- Happy path tests\n- Edge case tests\n- Error handling tests\n- Test framework: ${framework}',
                variables: ['code', 'framework']
            },
            {
                id: 'explain-code',
                name: 'Explain Code',
                category: 'Learning',
                description: 'Explain what code does',
                template: 'Please explain what this code does in simple terms:\n\n${code}\n\nInclude:\n- Overall purpose\n- Key steps\n- Important concepts\n- Potential improvements',
                variables: ['code']
            },
            {
                id: 'api-design',
                name: 'API Design Review',
                category: 'Architecture',
                description: 'Review API design and suggest improvements',
                template: 'Please review this API design:\n\n${api_spec}\n\nConsider:\n- RESTful principles\n- Error handling\n- Versioning strategy\n- Security\n- Performance',
                variables: ['api_spec']
            },
            {
                id: 'performance-optimization',
                name: 'Performance Optimization',
                category: 'Development',
                description: 'Identify and suggest performance optimizations',
                template: 'Please analyze this code for performance issues and suggest optimizations:\n\n${code}\n\nContext:\n- Current performance: ${current_performance}\n- Target performance: ${target_performance}',
                variables: ['code', 'current_performance', 'target_performance']
            }
        ];
    }
    async _handleMessage(message) {
        switch (message.command) {
            case 'enhancePrompt':
                await this._enhancePrompt(message.prompt, message.context, message.style);
                break;
            case 'useTemplate':
                this._useTemplate(message.templateId);
                break;
            case 'savePrompt':
                this._savePrompt(message.prompt, message.category);
                break;
            case 'toggleFavorite':
                this._toggleFavorite(message.promptId);
                break;
            case 'deletePrompt':
                this._deletePrompt(message.promptId);
                break;
            case 'copyToChat':
                this._copyToChat(message.prompt);
                break;
            case 'loadHistory':
                this._sendPromptHistory();
                break;
            case 'loadTemplates':
                this._sendTemplates();
                break;
        }
    }
    async _enhancePrompt(prompt, context, style) {
        try {
            const response = await axios_1.default.post(`${this._config.apiUrl}/prompts/enhance`, {
                prompt,
                context,
                style: style || 'professional'
            }, { timeout: 30000 });
            const enhancement = response.data;
            this._view?.webview.postMessage({
                command: 'enhancementResult',
                enhancement
            });
        }
        catch (error) {
            vscode.window.showErrorMessage(`Failed to enhance prompt: ${error.message}`);
        }
    }
    _useTemplate(templateId) {
        const template = this._promptTemplates.find(t => t.id === templateId);
        if (template) {
            this._view?.webview.postMessage({
                command: 'templateSelected',
                template
            });
        }
    }
    _savePrompt(prompt, category) {
        const savedPrompt = {
            id: `prompt_${Date.now()}`,
            text: prompt,
            timestamp: Date.now(),
            isFavorite: false,
            category
        };
        this._promptHistory.push(savedPrompt);
        this._persistPromptHistory();
        vscode.window.showInformationMessage('Prompt saved successfully');
        this._sendPromptHistory();
    }
    _toggleFavorite(promptId) {
        const prompt = this._promptHistory.find(p => p.id === promptId);
        if (prompt) {
            prompt.isFavorite = !prompt.isFavorite;
            this._persistPromptHistory();
            this._sendPromptHistory();
        }
    }
    _deletePrompt(promptId) {
        this._promptHistory = this._promptHistory.filter(p => p.id !== promptId);
        this._persistPromptHistory();
        this._sendPromptHistory();
    }
    _copyToChat(prompt) {
        vscode.commands.executeCommand('contextforge.chat.insertText', prompt);
    }
    _sendPromptHistory() {
        this._view?.webview.postMessage({
            command: 'promptHistory',
            history: this._promptHistory
        });
    }
    _sendTemplates() {
        this._view?.webview.postMessage({
            command: 'templates',
            templates: this._promptTemplates
        });
    }
    _persistPromptHistory() {
        // Store in workspace configuration
        const config = vscode.workspace.getConfiguration('contextforge');
        config.update('promptHistory', this._promptHistory, vscode.ConfigurationTarget.Global);
    }
    _getHtmlForWebview(webview) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ContextForge Prompt Generator</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
            padding: 12px;
            line-height: 1.5;
        }

        .container {
            display: flex;
            flex-direction: column;
            gap: 16px;
            height: 100%;
        }

        .section {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .section-title {
            font-weight: 600;
            font-size: 0.95em;
            color: var(--vscode-descriptionForeground);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        textarea {
            width: 100%;
            padding: 8px;
            border: 1px solid var(--vscode-input-border);
            background-color: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: 4px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.85em;
            resize: vertical;
            min-height: 80px;
        }

        textarea:focus {
            outline: none;
            border-color: var(--vscode-focusBorder);
        }

        .button-group {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }

        button {
            flex: 1;
            min-width: 80px;
            padding: 6px 12px;
            border: 1px solid var(--vscode-button-border);
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border-radius: 3px;
            cursor: pointer;
            font-size: 0.85em;
            font-weight: 500;
            transition: background-color 0.2s;
        }

        button:hover {
            background-color: var(--vscode-button-hoverBackground);
        }

        button:active {
            opacity: 0.8;
        }

        .secondary-button {
            background-color: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }

        .secondary-button:hover {
            background-color: var(--vscode-button-secondaryHoverBackground);
        }

        .tabs {
            display: flex;
            gap: 4px;
            border-bottom: 1px solid var(--vscode-input-border);
        }

        .tab {
            padding: 6px 12px;
            border: none;
            background: none;
            color: var(--vscode-descriptionForeground);
            cursor: pointer;
            border-bottom: 2px solid transparent;
            font-size: 0.85em;
        }

        .tab.active {
            color: var(--vscode-focusBorder);
            border-bottom-color: var(--vscode-focusBorder);
        }

        .tab-content {
            display: none;
            overflow-y: auto;
            max-height: 300px;
        }

        .tab-content.active {
            display: block;
        }

        .template-item, .prompt-item {
            padding: 8px;
            border: 1px solid var(--vscode-input-border);
            border-radius: 3px;
            background-color: var(--vscode-input-background);
            margin-bottom: 6px;
            cursor: pointer;
            transition: background-color 0.2s;
        }

        .template-item:hover, .prompt-item:hover {
            background-color: var(--vscode-list-hoverBackground);
        }

        .template-name, .prompt-text {
            font-weight: 500;
            font-size: 0.9em;
            margin-bottom: 2px;
        }

        .template-description, .prompt-meta {
            font-size: 0.8em;
            color: var(--vscode-descriptionForeground);
        }

        .prompt-actions {
            display: flex;
            gap: 4px;
            margin-top: 4px;
        }

        .prompt-actions button {
            flex: 1;
            padding: 4px 8px;
            font-size: 0.75em;
        }

        .favorite-btn.active {
            color: #FFD700;
        }

        .enhancement-result {
            padding: 8px;
            border-left: 3px solid var(--vscode-focusBorder);
            background-color: var(--vscode-input-background);
            border-radius: 3px;
            margin-top: 8px;
        }

        .enhancement-title {
            font-weight: 600;
            margin-bottom: 4px;
            font-size: 0.9em;
        }

        .enhancement-text {
            font-size: 0.85em;
            margin-bottom: 6px;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .suggestions-list {
            font-size: 0.8em;
            margin-top: 4px;
        }

        .suggestions-list li {
            margin-left: 16px;
            margin-bottom: 2px;
        }

        .empty-state {
            text-align: center;
            padding: 16px;
            color: var(--vscode-descriptionForeground);
            font-size: 0.9em;
        }

        .loading {
            display: inline-block;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="section">
            <div class="section-title">✨ Prompt Generator</div>
            <textarea id="promptInput" placeholder="Enter your prompt here..."></textarea>
            <div class="button-group">
                <button onclick="enhancePrompt()">Enhance</button>
                <button class="secondary-button" onclick="savePrompt()">Save</button>
            </div>
        </div>

        <div id="enhancementResult"></div>

        <div class="section">
            <div class="tabs">
                <button class="tab active" onclick="switchTab('templates')">Templates</button>
                <button class="tab" onclick="switchTab('history')">History</button>
            </div>

            <div id="templates" class="tab-content active"></div>
            <div id="history" class="tab-content"></div>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();

        function enhancePrompt() {
            const prompt = document.getElementById('promptInput').value;
            if (!prompt.trim()) {
                alert('Please enter a prompt to enhance');
                return;
            }
            vscode.postMessage({
                command: 'enhancePrompt',
                prompt: prompt,
                style: 'professional'
            });
        }

        function savePrompt() {
            const prompt = document.getElementById('promptInput').value;
            if (!prompt.trim()) {
                alert('Please enter a prompt to save');
                return;
            }
            vscode.postMessage({
                command: 'savePrompt',
                prompt: prompt,
                category: 'custom'
            });
        }

        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');

            if (tabName === 'templates') {
                vscode.postMessage({ command: 'loadTemplates' });
            } else if (tabName === 'history') {
                vscode.postMessage({ command: 'loadHistory' });
            }
        }

        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.command) {
                case 'templates':
                    renderTemplates(message.templates);
                    break;
                case 'promptHistory':
                    renderHistory(message.history);
                    break;
                case 'enhancementResult':
                    renderEnhancement(message.enhancement);
                    break;
                case 'templateSelected':
                    insertTemplate(message.template);
                    break;
            }
        });

        function renderTemplates(templates) {
            const container = document.getElementById('templates');
            if (!templates || templates.length === 0) {
                container.innerHTML = '<div class="empty-state">No templates available</div>';
                return;
            }

            container.innerHTML = templates.map(t => \`
                <div class="template-item" onclick="selectTemplate('\${t.id}')">
                    <div class="template-name">\${t.name}</div>
                    <div class="template-description">\${t.description}</div>
                </div>
            \`).join('');
        }

        function renderHistory(history) {
            const container = document.getElementById('history');
            if (!history || history.length === 0) {
                container.innerHTML = '<div class="empty-state">No saved prompts yet</div>';
                return;
            }

            container.innerHTML = history.map(p => \`
                <div class="prompt-item">
                    <div class="prompt-text">\${p.text.substring(0, 100)}...</div>
                    <div class="prompt-meta">Saved: \${new Date(p.timestamp).toLocaleDateString()}</div>
                    <div class="prompt-actions">
                        <button class="secondary-button" onclick="copyPrompt('\${p.text}')">Copy</button>
                        <button class="secondary-button favorite-btn \${p.isFavorite ? 'active' : ''}" onclick="toggleFavorite('\${p.id}')">★</button>
                        <button class="secondary-button" onclick="deletePrompt('\${p.id}')">Delete</button>
                    </div>
                </div>
            \`).join('');
        }

        function renderEnhancement(enhancement) {
            const container = document.getElementById('enhancementResult');
            container.innerHTML = \`
                <div class="enhancement-result">
                    <div class="enhancement-title">Enhanced Prompt:</div>
                    <div class="enhancement-text">\${enhancement.enhanced}</div>
                    \${enhancement.suggestions.length > 0 ? \`
                        <div class="enhancement-title">Suggestions:</div>
                        <ul class="suggestions-list">
                            \${enhancement.suggestions.map(s => \`<li>\${s}</li>\`).join('')}
                        </ul>
                    \` : ''}
                    <div class="button-group" style="margin-top: 8px;">
                        <button onclick="copyEnhanced('\${enhancement.enhanced}')">Copy Enhanced</button>
                        <button class="secondary-button" onclick="useEnhanced('\${enhancement.enhanced}')">Use in Chat</button>
                    </div>
                </div>
            \`;
        }

        function selectTemplate(templateId) {
            vscode.postMessage({ command: 'useTemplate', templateId });
        }

        function insertTemplate(template) {
            document.getElementById('promptInput').value = template.template;
        }

        function copyPrompt(text) {
            navigator.clipboard.writeText(text);
        }

        function copyEnhanced(text) {
            navigator.clipboard.writeText(text);
        }

        function useEnhanced(text) {
            vscode.postMessage({ command: 'copyToChat', prompt: text });
        }

        function toggleFavorite(promptId) {
            vscode.postMessage({ command: 'toggleFavorite', promptId });
        }

        function deletePrompt(promptId) {
            vscode.postMessage({ command: 'deletePrompt', promptId });
        }

        // Load initial data
        vscode.postMessage({ command: 'loadTemplates' });
    </script>
</body>
</html>`;
    }
}
exports.ContextForgePromptProvider = ContextForgePromptProvider;
ContextForgePromptProvider.viewType = 'contextforge.promptView';
//# sourceMappingURL=promptPanel.js.map