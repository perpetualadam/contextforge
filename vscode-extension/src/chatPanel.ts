import * as vscode from 'vscode';
import axios from 'axios';

interface FileAttachment {
    id: string;
    name: string;
    type: string;
    size: number;
    data: string; // base64 encoded
    extractedText?: string;
    analysisResult?: string;
}

interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    isMarkdown?: boolean;
    attachments?: FileAttachment[];
}

interface ChatSession {
    id: string;
    messages: ChatMessage[];
    title: string;
    createdAt: Date;
    updatedAt: Date;
}

interface ContextForgeConfig {
    apiUrl: string;
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
}

export class ContextForgeChatProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'contextforge.chatView';

    private _view?: vscode.WebviewView;
    private _currentSession: ChatSession;
    private _sessions: ChatSession[] = [];

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private _config: ContextForgeConfig
    ) {
        this._currentSession = this.createNewSession();
        this.loadChatHistory();
    }

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

        webviewView.webview.onDidReceiveMessage(async data => {
            switch (data.type) {
                case 'sendMessage':
                    await this.handleSendMessage(data.message, data.attachments);
                    break;
                case 'uploadFile':
                    await this.handleFileUpload(data.file);
                    break;
                case 'clearHistory':
                    this.clearChatHistory();
                    break;
                case 'newSession':
                    this.createNewSession();
                    this.updateWebview();
                    break;
                case 'copyCode':
                    vscode.env.clipboard.writeText(data.code);
                    vscode.window.showInformationMessage('Code copied to clipboard');
                    break;
                case 'insertCode':
                    await this.insertCodeAtCursor(data.code);
                    break;
                case 'loadSession':
                    this.loadSession(data.sessionId);
                    break;
            }
        });

        this.updateWebview();
    }

    private createNewSession(): ChatSession {
        const session: ChatSession = {
            id: this.generateId(),
            messages: [],
            title: `Chat ${new Date().toLocaleTimeString()}`,
            createdAt: new Date(),
            updatedAt: new Date()
        };

        this._sessions.unshift(session);
        
        // Limit number of sessions
        if (this._sessions.length > this._config.chatMaxHistory) {
            this._sessions = this._sessions.slice(0, this._config.chatMaxHistory);
        }

        this._currentSession = session;
        this.saveChatHistory();
        return session;
    }

    private async handleSendMessage(messageContent: string, attachments?: FileAttachment[]) {
        if (!messageContent.trim() && (!attachments || attachments.length === 0)) return;

        // Add user message
        const userMessage: ChatMessage = {
            id: this.generateId(),
            role: 'user',
            content: messageContent.trim(),
            timestamp: new Date(),
            attachments: attachments
        };

        this._currentSession.messages.push(userMessage);
        this._currentSession.updatedAt = new Date();

        // Update title if this is the first message
        if (this._currentSession.messages.length === 1) {
            this._currentSession.title = messageContent.slice(0, 50) + (messageContent.length > 50 ? '...' : '');
        }

        this.updateWebview();
        this.saveChatHistory();

        try {
            // Show typing indicator
            this.showTypingIndicator();

            // Send to API
            const response = await axios.post(`${this._config.apiUrl}/chat`, {
                messages: this._currentSession.messages.map(msg => ({
                    role: msg.role,
                    content: msg.content
                })),
                max_tokens: 1024,
                enable_web_search: this._config.enableWebSearch,
                enable_context: true
            });

            // Add assistant response
            const assistantMessage: ChatMessage = {
                id: this.generateId(),
                role: 'assistant',
                content: response.data.response,
                timestamp: new Date(),
                isMarkdown: true
            };

            this._currentSession.messages.push(assistantMessage);
            this._currentSession.updatedAt = new Date();

            this.hideTypingIndicator();
            this.updateWebview();
            this.saveChatHistory();

        } catch (error: any) {
            this.hideTypingIndicator();
            
            const errorMessage: ChatMessage = {
                id: this.generateId(),
                role: 'assistant',
                content: `Error: ${error.message || 'Failed to get response from AI'}`,
                timestamp: new Date()
            };

            this._currentSession.messages.push(errorMessage);
            this.updateWebview();
            
            vscode.window.showErrorMessage(`Chat error: ${error.message}`);
        }
    }

    private showTypingIndicator() {
        this._view?.webview.postMessage({
            type: 'showTyping'
        });
    }

    private hideTypingIndicator() {
        this._view?.webview.postMessage({
            type: 'hideTyping'
        });
    }

    private async insertCodeAtCursor(code: string) {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            const position = editor.selection.active;
            await editor.edit(editBuilder => {
                editBuilder.insert(position, code);
            });
            vscode.window.showInformationMessage('Code inserted at cursor');
        } else {
            vscode.window.showWarningMessage('No active editor to insert code');
        }
    }

    private clearChatHistory() {
        this._sessions = [];
        this._currentSession = this.createNewSession();
        this.updateWebview();
        this.saveChatHistory();
        vscode.window.showInformationMessage('Chat history cleared');
    }

    private loadSession(sessionId: string) {
        const session = this._sessions.find(s => s.id === sessionId);
        if (session) {
            this._currentSession = session;
            this.updateWebview();
        }
    }

    private updateWebview() {
        if (this._view) {
            this._view.webview.postMessage({
                type: 'updateChat',
                data: {
                    currentSession: this._currentSession,
                    sessions: this._sessions.slice(0, 10) // Show last 10 sessions
                }
            });
        }
    }

    private loadChatHistory() {
        if (!this._config.chatHistoryEnabled) return;

        try {
            const workspaceState = vscode.workspace.getConfiguration('contextforge');
            const savedSessions = workspaceState.get<ChatSession[]>('chatSessions', []);
            
            this._sessions = savedSessions.map(session => ({
                ...session,
                createdAt: new Date(session.createdAt),
                updatedAt: new Date(session.updatedAt),
                messages: session.messages.map(msg => ({
                    ...msg,
                    timestamp: new Date(msg.timestamp)
                }))
            }));

            if (this._sessions.length > 0) {
                this._currentSession = this._sessions[0];
            }
        } catch (error) {
            console.error('Failed to load chat history:', error);
        }
    }

    private saveChatHistory() {
        if (!this._config.chatHistoryEnabled) return;

        try {
            // Save only essential data to avoid storage bloat
            const sessionsToSave = this._sessions.slice(0, this._config.chatMaxHistory);
            vscode.workspace.getConfiguration('contextforge').update(
                'chatSessions',
                sessionsToSave,
                vscode.ConfigurationTarget.Global  // Use Global (User settings) instead of Workspace
            ).then(() => {}, (err) => console.error('Failed to save chat history:', err));
        } catch (error) {
            console.error('Failed to save chat history:', error);
        }
    }

    private generateId(): string {
        return Math.random().toString(36).substr(2, 9);
    }

    public updateConfig(config: ContextForgeConfig) {
        this._config = config;
    }

    public openChat() {
        if (this._view) {
            this._view.show?.(true);
        }
    }

    public sendMessage(message: string) {
        if (this._view) {
            this._view.webview.postMessage({
                type: 'setMessage',
                message: message
            });
            this._view.show?.(true);
        }
    }

    private async handleFileUpload(file: any) {
        try {
            // Validate file size
            const maxSize = this._config.maxFileSize || 10 * 1024 * 1024; // 10MB default
            if (file.size > maxSize) {
                vscode.window.showErrorMessage(`File size exceeds maximum of ${maxSize / 1024 / 1024}MB`);
                return;
            }

            // Validate file type
            const allowedTypes = this._config.allowedFileTypes || ['image/*', 'application/pdf', 'text/*'];
            const isAllowed = allowedTypes.some(type => {
                if (type.endsWith('*')) {
                    return file.type.startsWith(type.slice(0, -1));
                }
                return file.type === type;
            });

            if (!isAllowed) {
                vscode.window.showErrorMessage(`File type ${file.type} is not allowed`);
                return;
            }

            // Send file to backend for processing
            const formData = new FormData();
            formData.append('file', file);

            const response = await axios.post(
                `${this._config.apiUrl}/files/upload`,
                formData,
                {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    },
                    timeout: 30000
                }
            );

            const fileAttachment: FileAttachment = {
                id: response.data.id,
                name: file.name,
                type: file.type,
                size: file.size,
                data: response.data.data,
                extractedText: response.data.extractedText,
                analysisResult: response.data.analysisResult
            };

            // Notify webview of successful upload
            if (this._view) {
                this._view.webview.postMessage({
                    type: 'fileUploaded',
                    attachment: fileAttachment
                });
            }

            vscode.window.showInformationMessage(`File "${file.name}" uploaded successfully`);
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to upload file: ${error}`);
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ContextForge Chat</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
            margin: 0;
            padding: 0;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .chat-header {
            padding: 8px 12px;
            border-bottom: 1px solid var(--vscode-panel-border);
            background-color: var(--vscode-sideBar-background);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .chat-title {
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .chat-actions {
            display: flex;
            gap: 4px;
        }
        
        .action-button {
            background: none;
            border: none;
            color: var(--vscode-foreground);
            cursor: pointer;
            padding: 4px;
            border-radius: 3px;
            font-size: 0.8em;
        }
        
        .action-button:hover {
            background-color: var(--vscode-toolbar-hoverBackground);
        }
        
        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 8px;
            scroll-behavior: smooth;
        }
        
        .message {
            margin-bottom: 16px;
            padding: 8px 12px;
            border-radius: 8px;
            max-width: 90%;
            word-wrap: break-word;
        }
        
        .message.user {
            background-color: var(--vscode-inputOption-activeBackground);
            margin-left: auto;
            text-align: right;
        }
        
        .message.assistant {
            background-color: var(--vscode-input-background);
            border: 1px solid var(--vscode-input-border);
        }
        
        .message-header {
            font-size: 0.8em;
            color: var(--vscode-descriptionForeground);
            margin-bottom: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .message-content {
            line-height: 1.4;
        }
        
        .message-content pre {
            background-color: var(--vscode-textCodeBlock-background);
            border: 1px solid var(--vscode-panel-border);
            border-radius: 4px;
            padding: 8px;
            margin: 8px 0;
            overflow-x: auto;
            font-family: var(--vscode-editor-font-family);
            font-size: 0.9em;
            position: relative;
        }
        
        .message-content code {
            background-color: var(--vscode-textCodeBlock-background);
            padding: 2px 4px;
            border-radius: 3px;
            font-family: var(--vscode-editor-font-family);
            font-size: 0.9em;
        }
        
        .code-actions {
            position: absolute;
            top: 4px;
            right: 4px;
            display: flex;
            gap: 4px;
            opacity: 0;
            transition: opacity 0.2s;
        }
        
        .message-content pre:hover .code-actions {
            opacity: 1;
        }
        
        .code-button {
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 2px 6px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 0.7em;
        }
        
        .code-button:hover {
            background-color: var(--vscode-button-hoverBackground);
        }
        
        .typing-indicator {
            display: none;
            padding: 8px 12px;
            color: var(--vscode-descriptionForeground);
            font-style: italic;
            font-size: 0.9em;
        }
        
        .typing-indicator.show {
            display: block;
        }
        
        .input-container {
            padding: 8px;
            border-top: 1px solid var(--vscode-panel-border);
            background-color: var(--vscode-sideBar-background);
        }
        
        .input-wrapper {
            display: flex;
            gap: 8px;
            align-items: flex-end;
        }
        
        .message-input {
            flex: 1;
            min-height: 20px;
            max-height: 100px;
            padding: 8px;
            border: 1px solid var(--vscode-input-border);
            border-radius: 4px;
            background-color: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            resize: none;
            overflow-y: auto;
        }
        
        .message-input:focus {
            outline: none;
            border-color: var(--vscode-focusBorder);
        }
        
        .send-button {
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
        }
        
        .send-button:hover {
            background-color: var(--vscode-button-hoverBackground);
        }
        
        .send-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .file-upload-area {
            padding: 8px;
            border: 2px dashed var(--vscode-input-border);
            border-radius: 4px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background-color: var(--vscode-input-background);
        }

        .file-upload-area:hover {
            border-color: var(--vscode-focusBorder);
            background-color: var(--vscode-editor-hoverHighlightBackground);
        }

        .file-upload-area.drag-over {
            border-color: var(--vscode-focusBorder);
            background-color: var(--vscode-editor-selectionBackground);
        }

        .file-upload-button {
            background-color: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 6px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 0.85em;
            margin: 0 4px;
        }

        .file-upload-button:hover {
            background-color: var(--vscode-button-hoverBackground);
        }

        .attachments-container {
            padding: 8px;
            border-top: 1px solid var(--vscode-panel-border);
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .attachment-item {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 10px;
            background-color: var(--vscode-input-background);
            border: 1px solid var(--vscode-input-border);
            border-radius: 4px;
            font-size: 0.85em;
        }

        .attachment-remove {
            cursor: pointer;
            color: var(--vscode-errorForeground);
            font-weight: bold;
        }

        .attachment-remove:hover {
            opacity: 0.7;
        }

        .message-attachments {
            margin-top: 8px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .attachment-preview {
            padding: 8px;
            background-color: var(--vscode-editor-background);
            border: 1px solid var(--vscode-input-border);
            border-radius: 4px;
            max-width: 250px;
        }

        .attachment-preview img {
            display: block;
            max-width: 100%;
            height: auto;
            border-radius: 3px;
        }

        .attachment-info {
            font-size: 0.85em;
            color: var(--vscode-descriptionForeground);
        }

        .attachment-text-preview {
            margin-top: 6px;
            padding: 6px;
            background-color: var(--vscode-input-background);
            border-left: 2px solid var(--vscode-focusBorder);
            font-size: 0.8em;
            color: var(--vscode-foreground);
            max-height: 100px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .empty-state {
            text-align: center;
            color: var(--vscode-descriptionForeground);
            margin-top: 50px;
            padding: 20px;
        }
        
        .empty-state h3 {
            margin-bottom: 8px;
            color: var(--vscode-foreground);
        }
        
        .empty-state p {
            margin: 4px 0;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="chat-header">
        <div class="chat-title">ContextForge Chat</div>
        <div class="chat-actions">
            <button class="action-button" onclick="newSession()" title="New Chat">➕</button>
            <button class="action-button" onclick="clearHistory()" title="Clear History">🗑️</button>
        </div>
    </div>
    
    <div class="chat-container">
        <div class="messages-container" id="messagesContainer">
            <div class="empty-state" id="emptyState">
                <h3>Welcome to ContextForge Chat</h3>
                <p>Start a conversation with your AI assistant</p>
                <p>Ask questions about your code, get help with debugging, or discuss your project</p>
            </div>
        </div>
        
        <div class="typing-indicator" id="typingIndicator">
            AI is typing...
        </div>
        
        <div class="attachments-container" id="attachmentsContainer" style="display: none;"></div>

        <div class="input-container">
            <div class="file-upload-area" id="fileUploadArea" ondrop="handleDrop(event)" ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)">
                <input type="file" id="fileInput" style="display: none;" onchange="handleFileSelect(event)" multiple accept="image/*,.pdf,.doc,.docx,.txt,.md">
                <button class="file-upload-button" onclick="document.getElementById('fileInput').click()">📎 Attach</button>
                <span style="font-size: 0.85em; color: var(--vscode-descriptionForeground);">or drag files here</span>
            </div>
            <div class="input-wrapper">
                <textarea
                    class="message-input"
                    id="messageInput"
                    placeholder="Ask me anything about your code..."
                    rows="1"
                ></textarea>
                <button class="send-button" id="sendButton" onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let currentSession = null;
        let sessions = [];

        window.addEventListener('message', event => {
            const message = event.data;
            switch (message.type) {
                case 'updateChat':
                    updateChatDisplay(message.data);
                    break;
                case 'showTyping':
                    showTypingIndicator();
                    break;
                case 'hideTyping':
                    hideTypingIndicator();
                    break;
                case 'setMessage':
                    setInputMessage(message.message);
                    break;
            }
        });

        function updateChatDisplay(data) {
            currentSession = data.currentSession;
            sessions = data.sessions;
            
            const messagesContainer = document.getElementById('messagesContainer');
            const emptyState = document.getElementById('emptyState');
            
            if (currentSession.messages.length === 0) {
                emptyState.style.display = 'block';
                messagesContainer.innerHTML = '';
                messagesContainer.appendChild(emptyState);
            } else {
                emptyState.style.display = 'none';
                messagesContainer.innerHTML = '';
                
                currentSession.messages.forEach(message => {
                    const messageElement = createMessageElement(message);
                    messagesContainer.appendChild(messageElement);
                });
                
                scrollToBottom();
            }
        }

        function createMessageElement(message) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + message.role;

            const headerDiv = document.createElement('div');
            headerDiv.className = 'message-header';
            headerDiv.innerHTML =
                '<span>' + (message.role === 'user' ? 'You' : 'AI Assistant') + '</span>' +
                '<span>' + new Date(message.timestamp).toLocaleTimeString() + '</span>';

            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';

            if (message.isMarkdown) {
                contentDiv.innerHTML = formatMarkdown(message.content);
                addCodeActions(contentDiv);
            } else {
                contentDiv.textContent = message.content;
            }

            messageDiv.appendChild(headerDiv);
            messageDiv.appendChild(contentDiv);

            // Add attachments if present
            if (message.attachments && message.attachments.length > 0) {
                const attachmentsDiv = document.createElement('div');
                attachmentsDiv.className = 'message-attachments';

                message.attachments.forEach(attachment => {
                    const attachmentElement = createAttachmentElement(attachment);
                    attachmentsDiv.appendChild(attachmentElement);
                });

                messageDiv.appendChild(attachmentsDiv);
            }

            return messageDiv;
        }

        function createAttachmentElement(attachment) {
            const div = document.createElement('div');
            div.className = 'attachment-preview';

            if (attachment.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.src = attachment.data;
                img.style.maxWidth = '200px';
                img.style.maxHeight = '200px';
                img.style.borderRadius = '4px';
                div.appendChild(img);
            } else if (attachment.type === 'application/pdf' || attachment.type.includes('document')) {
                const info = document.createElement('div');
                info.className = 'attachment-info';
                info.innerHTML = '<strong>📄 ' + attachment.name + '</strong><br>' +
                    '<small>' + (attachment.size / 1024).toFixed(2) + ' KB</small>';
                div.appendChild(info);

                if (attachment.extractedText) {
                    const preview = document.createElement('div');
                    preview.className = 'attachment-text-preview';
                    preview.textContent = attachment.extractedText.substring(0, 200) + '...';
                    div.appendChild(preview);
                }
            } else {
                const info = document.createElement('div');
                info.className = 'attachment-info';
                info.innerHTML = '<strong>📎 ' + attachment.name + '</strong><br>' +
                    '<small>' + (attachment.size / 1024).toFixed(2) + ' KB</small>';
                div.appendChild(info);
            }

            return div;
        }

        function formatMarkdown(text) {
            return text
                .replace(/\`\`\`([\\s\\S]*?)\`\`\`/g, '<pre><code>$1</code></pre>')
                .replace(/\`([^\`]+)\`/g, '<code>$1</code>')
                .replace(/\\*\\*([^\\*]+)\\*\\*/g, '<strong>$1</strong>')
                .replace(/\\*([^\\*]+)\\*/g, '<em>$1</em>')
                .replace(/\\n/g, '<br>');
        }

        function addCodeActions(contentDiv) {
            const codeBlocks = contentDiv.querySelectorAll('pre code');
            codeBlocks.forEach(codeBlock => {
                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'code-actions';
                actionsDiv.innerHTML = 
                    '<button class="code-button" onclick="copyCode(this)">Copy</button>' +
                    '<button class="code-button" onclick="insertCode(this)">Insert</button>';
                codeBlock.parentElement.style.position = 'relative';
                codeBlock.parentElement.appendChild(actionsDiv);
            });
        }

        function copyCode(button) {
            const codeBlock = button.closest('pre').querySelector('code');
            const code = codeBlock.textContent;
            vscode.postMessage({
                type: 'copyCode',
                code: code
            });
        }

        function insertCode(button) {
            const codeBlock = button.closest('pre').querySelector('code');
            const code = codeBlock.textContent;
            vscode.postMessage({
                type: 'insertCode',
                code: code
            });
        }

        let attachedFiles = [];

        function handleFileSelect(event) {
            const files = event.target.files;
            for (let file of files) {
                addAttachment(file);
            }
        }

        function handleDrop(event) {
            event.preventDefault();
            event.stopPropagation();
            document.getElementById('fileUploadArea').classList.remove('drag-over');

            const files = event.dataTransfer.files;
            for (let file of files) {
                addAttachment(file);
            }
        }

        function handleDragOver(event) {
            event.preventDefault();
            event.stopPropagation();
            document.getElementById('fileUploadArea').classList.add('drag-over');
        }

        function handleDragLeave(event) {
            event.preventDefault();
            event.stopPropagation();
            document.getElementById('fileUploadArea').classList.remove('drag-over');
        }

        function addAttachment(file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                const attachment = {
                    id: 'file_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
                    name: file.name,
                    type: file.type,
                    size: file.size,
                    data: e.target.result
                };

                attachedFiles.push(attachment);
                updateAttachmentsDisplay();
            };
            reader.readAsDataURL(file);
        }

        function updateAttachmentsDisplay() {
            const container = document.getElementById('attachmentsContainer');
            if (attachedFiles.length === 0) {
                container.style.display = 'none';
                return;
            }

            container.style.display = 'flex';
            let html = '';
            for (let file of attachedFiles) {
                html += '<div class="attachment-item">' +
                    '<span>📄 ' + file.name + '</span>' +
                    '<span class="attachment-remove" onclick="removeAttachment(\'' + file.id + '\')">✕</span>' +
                    '</div>';
            }
            container.innerHTML = html;
        }

        function removeAttachment(fileId) {
            attachedFiles = attachedFiles.filter(f => f.id !== fileId);
            updateAttachmentsDisplay();
        }

        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();

            if (message || attachedFiles.length > 0) {
                vscode.postMessage({
                    type: 'sendMessage',
                    message: message,
                    attachments: attachedFiles
                });
                input.value = '';
                attachedFiles = [];
                updateAttachmentsDisplay();
                adjustTextareaHeight(input);
            }
        }

        function newSession() {
            vscode.postMessage({
                type: 'newSession'
            });
        }

        function clearHistory() {
            if (confirm('Are you sure you want to clear all chat history?')) {
                vscode.postMessage({
                    type: 'clearHistory'
                });
            }
        }

        function showTypingIndicator() {
            document.getElementById('typingIndicator').classList.add('show');
            scrollToBottom();
        }

        function hideTypingIndicator() {
            document.getElementById('typingIndicator').classList.remove('show');
        }

        function setInputMessage(message) {
            const input = document.getElementById('messageInput');
            input.value = message;
            adjustTextareaHeight(input);
            input.focus();
        }

        function scrollToBottom() {
            const container = document.getElementById('messagesContainer');
            container.scrollTop = container.scrollHeight;
        }

        function adjustTextareaHeight(textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 100) + 'px';
        }

        // Event listeners
        document.getElementById('messageInput').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        document.getElementById('messageInput').addEventListener('input', function(e) {
            adjustTextareaHeight(e.target);
        });
    </script>
</body>
</html>`;
    }
}
