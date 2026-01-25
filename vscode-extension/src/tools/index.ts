/**
 * ContextForge VS Code Extension Tools
 *
 * This module exports all tool providers for the extension:
 * - DiagnosticsProvider: VS Code IDE diagnostics integration
 * - FileTools: Hybrid file operations (VS Code + backend)
 * - TaskPanelProvider: Task management webview panel
 *
 * @module tools
 */

// Diagnostics - VS Code IDE error/warning collection
export {
    DiagnosticsProvider,
    DiagnosticInfo,
    DiagnosticSummary
} from './diagnostics';

// File operations - Hybrid VS Code + backend file tools
export {
    FileTools,
    ViewResult,
    EditResult,
    SearchResult,
    StrReplacement
} from './fileTools';

// Task management - Visual task list webview
export {
    TaskPanelProvider,
    Task,
    TaskState
} from './taskPanel';
