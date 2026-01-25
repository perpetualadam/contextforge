/**
 * ContextForge Task Panel Provider
 * 
 * Visual UI for managing the task list:
 * - Hierarchical task tree with collapsible items
 * - State toggles (NOT_STARTED → IN_PROGRESS → COMPLETE)
 * - Inline editing of task names/descriptions
 * - Add/remove tasks
 * - Apply templates
 * 
 * @module tools/taskPanel
 */

import * as vscode from 'vscode';
import axios from 'axios';

/**
 * Task state enum matching backend
 */
export type TaskState = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETE' | 'CANCELLED';

/**
 * Task data structure
 */
export interface Task {
    task_id: string;
    name: string;
    description: string;
    state: TaskState;
    parent_id: string | null;
    children: string[];
    order: number;
}

/**
 * Task list response from API
 */
interface TaskListResponse {
    markdown: string;
    tasks: Task[];
    stats: {
        total: number;
        not_started: number;
        in_progress: number;
        complete: number;
        cancelled: number;
    };
}

interface TaskPanelConfig {
    apiUrl: string;
}

/**
 * Webview provider for the task panel
 */
export class TaskPanelProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'contextforge.taskView';

    private _view?: vscode.WebviewView;
    private _config: TaskPanelConfig;
    private _tasks: Task[] = [];

    constructor(
        private readonly _extensionUri: vscode.Uri,
        config: { apiUrl: string }
    ) {
        this._config = { apiUrl: config.apiUrl };
    }

    /**
     * Update configuration
     */
    public updateConfig(config: { apiUrl: string }): void {
        this._config = { apiUrl: config.apiUrl };
    }

    /**
     * Called when webview is created
     */
    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ): void {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._getHtmlForWebview();

        // Handle messages from webview
        webviewView.webview.onDidReceiveMessage(async (message) => {
            switch (message.type) {
                case 'refresh':
                    await this.loadTasks();
                    break;
                case 'updateTask':
                    await this.updateTask(message.taskId, message.updates);
                    break;
                case 'addTask':
                    await this.addTask(message.name, message.parentId);
                    break;
                case 'deleteTask':
                    await this.deleteTask(message.taskId);
                    break;
                case 'applyTemplate':
                    await this.applyTemplate(message.templateName, message.title);
                    break;
                case 'toggleState':
                    await this.toggleTaskState(message.taskId);
                    break;
            }
        });

        // Load tasks on init
        this.loadTasks();
    }

    /**
     * Load tasks from backend
     */
    public async loadTasks(): Promise<void> {
        try {
            const response = await axios.get<TaskListResponse>(`${this._config.apiUrl}/tasklist`);
            this._tasks = response.data.tasks;
            
            this._view?.webview.postMessage({
                type: 'tasksLoaded',
                tasks: this._tasks,
                stats: response.data.stats
            });
        } catch (error: any) {
            vscode.window.showErrorMessage(`Failed to load tasks: ${error.message}`);
            this._view?.webview.postMessage({
                type: 'error',
                message: error.message
            });
        }
    }

    /**
     * Update a task
     */
    private async updateTask(taskId: string, updates: Partial<Task>): Promise<void> {
        try {
            await axios.patch(`${this._config.apiUrl}/tasklist/tasks`, {
                tasks: [{ task_id: taskId, ...updates }]
            });
            await this.loadTasks();
        } catch (error: any) {
            vscode.window.showErrorMessage(`Failed to update task: ${error.message}`);
        }
    }

    /**
     * Add a new task
     */
    private async addTask(name: string, parentId?: string): Promise<void> {
        try {
            await axios.post(`${this._config.apiUrl}/tasklist/tasks`, {
                tasks: [{ name, parent_task_id: parentId }]
            });
            await this.loadTasks();
        } catch (error: any) {
            vscode.window.showErrorMessage(`Failed to add task: ${error.message}`);
        }
    }

    /**
     * Delete a task
     */
    private async deleteTask(taskId: string): Promise<void> {
        try {
            await axios.delete(`${this._config.apiUrl}/tasklist/tasks/${taskId}`);
            await this.loadTasks();
        } catch (error: any) {
            vscode.window.showErrorMessage(`Failed to delete task: ${error.message}`);
        }
    }

    /**
     * Apply a template
     */
    private async applyTemplate(templateName: string, title: string): Promise<void> {
        try {
            await axios.post(`${this._config.apiUrl}/tasklist/templates/${templateName}`, null, {
                params: { title }
            });
            await this.loadTasks();
            vscode.window.showInformationMessage(`Applied template: ${templateName}`);
        } catch (error: any) {
            vscode.window.showErrorMessage(`Failed to apply template: ${error.message}`);
        }
    }

    /**
     * Toggle task state: NOT_STARTED → IN_PROGRESS → COMPLETE → NOT_STARTED
     */
    private async toggleTaskState(taskId: string): Promise<void> {
        const task = this._tasks.find(t => t.task_id === taskId);
        if (!task) {
            return;
        }

        const stateOrder: TaskState[] = ['NOT_STARTED', 'IN_PROGRESS', 'COMPLETE'];
        const currentIndex = stateOrder.indexOf(task.state);
        const nextState = stateOrder[(currentIndex + 1) % stateOrder.length];

        await this.updateTask(taskId, { state: nextState });
    }

    /**
     * Generate the webview HTML
     */
    private _getHtmlForWebview(): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ContextForge Tasks</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
            padding: 10px;
            margin: 0;
        }
        .toolbar {
            display: flex;
            gap: 8px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        .toolbar button {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 4px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
        }
        .toolbar button:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .stats {
            display: flex;
            gap: 12px;
            margin-bottom: 15px;
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
        }
        .stat-item {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .stat-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        .stat-dot.complete { background: #4caf50; }
        .stat-dot.in-progress { background: #ff9800; }
        .stat-dot.not-started { background: #9e9e9e; }
        .task-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        .task-item {
            display: flex;
            align-items: flex-start;
            padding: 6px 0;
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .task-checkbox {
            width: 16px;
            height: 16px;
            margin-right: 8px;
            cursor: pointer;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid var(--vscode-foreground);
            border-radius: 3px;
            font-size: 10px;
        }
        .task-checkbox.complete {
            background: #4caf50;
            border-color: #4caf50;
            color: white;
        }
        .task-checkbox.in-progress {
            background: #ff9800;
            border-color: #ff9800;
            color: black;
        }
        .task-checkbox.cancelled {
            background: #f44336;
            border-color: #f44336;
            color: white;
        }
        .task-content { flex: 1; }
        .task-name { cursor: pointer; }
        .task-name.complete {
            text-decoration: line-through;
            opacity: 0.7;
        }
        .task-description {
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
            margin-top: 2px;
        }
        .task-children { margin-left: 24px; }
        .task-actions { display: none; gap: 4px; }
        .task-item:hover .task-actions { display: flex; }
        .task-action-btn {
            background: transparent;
            border: none;
            color: var(--vscode-foreground);
            cursor: pointer;
            padding: 2px 4px;
            font-size: 11px;
            opacity: 0.6;
        }
        .task-action-btn:hover { opacity: 1; }
        .empty-state {
            text-align: center;
            color: var(--vscode-descriptionForeground);
            padding: 40px 20px;
        }
        .add-task-input {
            display: flex;
            gap: 8px;
            margin-top: 15px;
        }
        .add-task-input input {
            flex: 1;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border: 1px solid var(--vscode-input-border);
            padding: 6px 8px;
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <div class="toolbar">
        <button onclick="refresh()">↻ Refresh</button>
        <button onclick="showAddTask()">+ Add Task</button>
        <button onclick="showTemplates()">📋 Templates</button>
    </div>
    <div class="stats" id="stats"></div>
    <ul class="task-list" id="taskList">
        <li class="empty-state">Loading tasks...</li>
    </ul>
    <div class="add-task-input" id="addTaskForm" style="display: none;">
        <input type="text" id="newTaskName" placeholder="New task name..." />
        <button onclick="addTask()">Add</button>
        <button onclick="hideAddTask()">Cancel</button>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        let tasks = [];
        let stats = {};

        window.addEventListener('message', event => {
            const message = event.data;
            if (message.type === 'tasksLoaded') {
                tasks = message.tasks;
                stats = message.stats;
                renderTasks();
                renderStats();
            } else if (message.type === 'error') {
                showError(message.message);
            }
        });

        function refresh() { vscode.postMessage({ type: 'refresh' }); }

        function renderStats() {
            document.getElementById('stats').innerHTML =
                '<div class="stat-item"><span class="stat-dot complete"></span><span>' + (stats.complete || 0) + ' done</span></div>' +
                '<div class="stat-item"><span class="stat-dot in-progress"></span><span>' + (stats.in_progress || 0) + ' in progress</span></div>' +
                '<div class="stat-item"><span class="stat-dot not-started"></span><span>' + (stats.not_started || 0) + ' todo</span></div>';
        }

        function renderTasks() {
            const listEl = document.getElementById('taskList');
            if (!tasks || tasks.length === 0) {
                listEl.innerHTML = '<li class="empty-state">No tasks yet. Add a task to get started!</li>';
                return;
            }
            const rootTasks = tasks.filter(t => !t.parent_id);
            listEl.innerHTML = rootTasks.map(t => renderTask(t)).join('');
        }

        function renderTask(task) {
            const children = tasks.filter(t => t.parent_id === task.task_id);
            const stateClass = task.state.toLowerCase().replace('_', '-');
            const checkMark = task.state === 'COMPLETE' ? '✓' : task.state === 'IN_PROGRESS' ? '/' : task.state === 'CANCELLED' ? '−' : '';
            return '<li class="task-item">' +
                '<div class="task-checkbox ' + stateClass + '" onclick="toggleState(\\'' + task.task_id + '\\')">' + checkMark + '</div>' +
                '<div class="task-content">' +
                '<div class="task-name ' + stateClass + '">' + escapeHtml(task.name) + '</div>' +
                (task.description ? '<div class="task-description">' + escapeHtml(task.description) + '</div>' : '') +
                (children.length > 0 ? '<ul class="task-list task-children">' + children.map(c => renderTask(c)).join('') + '</ul>' : '') +
                '</div>' +
                '<div class="task-actions">' +
                '<button class="task-action-btn" onclick="addSubtask(\\'' + task.task_id + '\\')">+</button>' +
                '<button class="task-action-btn" onclick="deleteTask(\\'' + task.task_id + '\\')">×</button>' +
                '</div></li>';
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function toggleState(taskId) { vscode.postMessage({ type: 'toggleState', taskId }); }
        function showAddTask() {
            document.getElementById('addTaskForm').style.display = 'flex';
            document.getElementById('newTaskName').focus();
        }
        function hideAddTask() {
            document.getElementById('addTaskForm').style.display = 'none';
            document.getElementById('newTaskName').value = '';
        }
        function addTask() {
            const name = document.getElementById('newTaskName').value.trim();
            if (name) { vscode.postMessage({ type: 'addTask', name }); hideAddTask(); }
        }
        function addSubtask(parentId) {
            const name = prompt('Enter subtask name:');
            if (name) { vscode.postMessage({ type: 'addTask', name, parentId }); }
        }
        function deleteTask(taskId) {
            if (confirm('Delete this task?')) { vscode.postMessage({ type: 'deleteTask', taskId }); }
        }
        function showTemplates() {
            const templates = ['feature', 'bug_fix', 'refactor', 'review', 'release'];
            const selected = prompt('Choose template:\\n' + templates.map((t, i) => (i+1) + '. ' + t).join('\\n'));
            if (selected) {
                const idx = parseInt(selected) - 1;
                if (idx >= 0 && idx < templates.length) {
                    const title = prompt('Enter title for template:') || '';
                    vscode.postMessage({ type: 'applyTemplate', templateName: templates[idx], title });
                }
            }
        }
        function showError(message) {
            document.getElementById('taskList').innerHTML = '<li class="empty-state" style="color: #f44336;">Error: ' + escapeHtml(message) + '</li>';
        }
        document.getElementById('newTaskName').addEventListener('keypress', (e) => { if (e.key === 'Enter') addTask(); });
    </script>
</body>
</html>`;
    }
}
