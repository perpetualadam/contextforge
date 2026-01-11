import * as vscode from 'vscode';
import axios from 'axios';

interface AgentInfo {
    name: string;
    execution_hint: 'local' | 'remote' | 'hybrid';
    resolved_location: 'local' | 'remote';
    capabilities: {
        consumes: string[];
        produces: string[];
        requires_filesystem: boolean;
        requires_network: boolean;
    };
}

interface AgentStatus {
    agents: Record<string, AgentInfo>;
    total_agents: number;
    local_agents: number;
    remote_agents: number;
    llm_mode: 'online' | 'offline';
}

interface ContextForgeConfig {
    apiUrl: string;
}

export class AgentStatusProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'contextforge.agentView';

    private _view?: vscode.WebviewView;
    private _status: AgentStatus | null = null;
    private _refreshInterval: NodeJS.Timeout | null = null;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private _config: ContextForgeConfig
    ) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken,
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._getHtmlForWebview();

        webviewView.webview.onDidReceiveMessage(async data => {
            switch (data.type) {
                case 'refresh':
                    await this.refreshStatus();
                    break;
                case 'runPipeline':
                    await this.runPipeline();
                    break;
            }
        });

        // Initial refresh
        this.refreshStatus();

        // Auto-refresh every 30 seconds
        this._refreshInterval = setInterval(() => {
            this.refreshStatus();
        }, 30000);

        webviewView.onDidDispose(() => {
            if (this._refreshInterval) {
                clearInterval(this._refreshInterval);
            }
        });
    }

    public async refreshStatus() {
        try {
            const response = await axios.get(`${this._config.apiUrl}/agents/status`);
            this._status = response.data;
            this._updateWebview();
        } catch (error) {
            this._status = null;
            this._updateWebview();
        }
    }

    private async runPipeline() {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }

        const repoPath = workspaceFolders[0].uri.fsPath;

        try {
            this._postMessage({ type: 'pipelineStarted' });

            const response = await axios.post(`${this._config.apiUrl}/agents/pipeline`, {
                repo_path: repoPath,
                mode: 'auto',
                task: 'full_analysis'
            });

            this._postMessage({
                type: 'pipelineComplete',
                result: response.data
            });

            vscode.window.showInformationMessage(
                `Pipeline complete! ${response.data.agents_executed?.length || 0} agents executed.`
            );
        } catch (error) {
            this._postMessage({
                type: 'pipelineError',
                error: String(error)
            });
            vscode.window.showErrorMessage(`Pipeline failed: ${error}`);
        }
    }

    private _updateWebview() {
        this._postMessage({
            type: 'statusUpdate',
            status: this._status
        });
    }

    private _postMessage(message: any) {
        if (this._view) {
            this._view.webview.postMessage(message);
        }
    }

    public updateConfig(config: ContextForgeConfig) {
        this._config = config;
    }

    private _getHtmlForWebview(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Status</title>
    <style>
        body { font-family: var(--vscode-font-family); padding: 10px; color: var(--vscode-foreground); }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .header h3 { margin: 0; }
        .status-badge { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .online { background: #28a745; color: white; }
        .offline { background: #dc3545; color: white; }
        .agent-card { background: var(--vscode-editor-background); border: 1px solid var(--vscode-panel-border);
            border-radius: 6px; padding: 10px; margin-bottom: 10px; }
        .agent-name { font-weight: bold; display: flex; align-items: center; gap: 8px; }
        .location-badge { font-size: 10px; padding: 2px 6px; border-radius: 3px; }
        .local { background: #17a2b8; color: white; }
        .remote { background: #6f42c1; color: white; }
        .hybrid { background: #fd7e14; color: white; }
        .capabilities { font-size: 11px; color: var(--vscode-descriptionForeground); margin-top: 5px; }
        .summary { display: flex; gap: 15px; margin-bottom: 15px; font-size: 12px; }
        .summary-item { display: flex; align-items: center; gap: 5px; }
        button { background: var(--vscode-button-background); color: var(--vscode-button-foreground);
            border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }
        button:hover { background: var(--vscode-button-hoverBackground); }
        .loading { text-align: center; padding: 20px; color: var(--vscode-descriptionForeground); }
    </style>
</head>
<body>
    <div class="header">
        <h3>🤖 Agent Status</h3>
        <button onclick="refresh()">↻ Refresh</button>
    </div>
    <div id="content"><div class="loading">Loading...</div></div>
    <script>
        const vscode = acquireVsCodeApi();
        function refresh() { vscode.postMessage({ type: 'refresh' }); }
        function runPipeline() { vscode.postMessage({ type: 'runPipeline' }); }
        window.addEventListener('message', event => {
            const msg = event.data;
            if (msg.type === 'statusUpdate') { renderStatus(msg.status); }
            else if (msg.type === 'pipelineStarted') { document.getElementById('pipelineBtn').disabled = true; }
            else if (msg.type === 'pipelineComplete' || msg.type === 'pipelineError') {
                document.getElementById('pipelineBtn').disabled = false;
            }
        });
        function renderStatus(status) {
            const el = document.getElementById('content');
            if (!status) { el.innerHTML = '<div class="loading">Unable to connect to API</div>'; return; }
            let html = '<div class="summary">' +
                '<div class="summary-item"><span class="status-badge ' + status.llm_mode + '">' + 
                (status.llm_mode === 'online' ? '☁️ Online' : '🖥️ Offline') + '</span></div>' +
                '<div class="summary-item">🤖 ' + status.total_agents + ' agents</div>' +
                '<div class="summary-item">📍 ' + status.local_agents + ' local</div>' +
                '<div class="summary-item">🌐 ' + status.remote_agents + ' remote</div></div>' +
                '<button id="pipelineBtn" onclick="runPipeline()">▶️ Run Pipeline</button><br><br>';
            for (const [name, agent] of Object.entries(status.agents || {})) {
                const a = agent;
                html += '<div class="agent-card"><div class="agent-name">' +
                    '<span>' + name + '</span>' +
                    '<span class="location-badge ' + a.resolved_location + '">' + a.resolved_location + '</span>' +
                    '<span class="location-badge ' + a.execution_hint + '">' + a.execution_hint + '</span></div>' +
                    '<div class="capabilities">Consumes: ' + (a.capabilities?.consumes?.join(', ') || 'none') + 
                    ' | Produces: ' + (a.capabilities?.produces?.join(', ') || 'none') + '</div></div>';
            }
            el.innerHTML = html;
        }
    </script>
</body>
</html>`;
    }
}

