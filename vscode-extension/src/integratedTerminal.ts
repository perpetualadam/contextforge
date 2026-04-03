/**
 * Full shell workflow via VS Code's integrated terminal (splits, history, interactivity).
 * Complements API-based "Execute Terminal Command" which uses the sandboxed gateway executor.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

function workspaceCwd(): string | undefined {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function terminalName(): string {
    return vscode.workspace.getConfiguration('contextforge').get<string>('integratedTerminalProfileName') || 'ContextForge';
}

/** Locate a Makefile in the workspace root (GNU make search order). */
function findMakefilePath(root: string): string | undefined {
    for (const name of ['Makefile', 'makefile', 'GNUmakefile']) {
        const p = path.join(root, name);
        if (fs.existsSync(p)) {
            return p;
        }
    }
    return undefined;
}

const INCLUDE_LINE = /^-?s?include\s+(.+)$/i;

/**
 * Recursively merge Makefile text from `include` / `-include` / `sinclude` (depth-limited).
 * Targets defined in included fragments are collected for quick-pick.
 */
export function collectMakefileContentWithIncludes(
    makefilePath: string,
    maxDepth: number,
    seen: Set<string> = new Set()
): string {
    if (maxDepth < 0 || seen.has(makefilePath)) {
        return '';
    }
    seen.add(makefilePath);
    let text: string;
    try {
        text = fs.readFileSync(makefilePath, 'utf-8');
    } catch {
        return '';
    }
    const dir = path.dirname(makefilePath);
    const merged: string[] = [];
    for (const raw of text.split(/\r?\n/)) {
        const line = raw.split('#')[0].trim();
        const m = line.match(INCLUDE_LINE);
        if (!m) {
            continue;
        }
        const parts = m[1]
            .trim()
            .split(/\s+/)
            .filter((p) => p && !p.startsWith('-'));
        for (const rel of parts) {
            const abs = path.resolve(dir, rel);
            merged.push(collectMakefileContentWithIncludes(abs, maxDepth - 1, seen));
        }
    }
    return merged.join('\n') + '\n' + text;
}

/**
 * Extract target names for quick-pick (best-effort; skips recipes and most directives).
 */
export function parseMakefileTargets(content: string): string[] {
    const targets = new Set<string>();
    for (const raw of content.split(/\r?\n/)) {
        const line = raw.split('#')[0].replace(/\s+$/, '');
        if (!line || line.startsWith('\t')) {
            continue;
        }
        const phony = line.match(/^\.PHONY\s*:\s*(.+)$/i);
        if (phony) {
            for (const t of phony[1].trim().split(/\s+/)) {
                if (t) {
                    targets.add(t);
                }
            }
            continue;
        }
        if (/^[A-Za-z_][A-Za-z0-9_]*\s*[:+]?=/.test(line)) {
            continue;
        }
        if (
            /^(ifeq|ifneq|ifdef|ifndef|else|endif|include|sinclude|-include|define|endef|vpath|export|unexport|override)\b/.test(
                line
            )
        ) {
            continue;
        }
        const m = line.match(/^([a-zA-Z0-9_.@%/\-]+)\s*:/);
        if (!m) {
            continue;
        }
        const name = m[1];
        if (name.startsWith('.')) {
            continue;
        }
        targets.add(name);
    }
    return Array.from(targets).sort();
}

/**
 * Show or create a terminal and run a line (press Enter).
 */
export function runInIntegratedTerminal(
    command: string,
    options: { newTerminal?: boolean; cwd?: string } = {}
): vscode.Terminal {
    const cwd = options.cwd ?? workspaceCwd();
    const useNew = options.newTerminal === true || !vscode.window.activeTerminal;
    let term: vscode.Terminal;
    if (useNew) {
        term = vscode.window.createTerminal({ name: terminalName(), cwd });
    } else {
        term = vscode.window.activeTerminal!;
    }
    term.show(true);
    term.sendText(command, true);
    return term;
}

/** Register all integrated-terminal commands; caller must add disposables to context.subscriptions. */
export function registerIntegratedTerminalCommands(): vscode.Disposable[] {
    const disposables: vscode.Disposable[] = [];

    disposables.push(
        vscode.commands.registerCommand('contextforge.openIntegratedTerminal', () => {
            const cwd = workspaceCwd();
            const t = vscode.window.createTerminal({ name: terminalName(), cwd });
            t.show(true);
        })
    );

    disposables.push(
        vscode.commands.registerCommand('contextforge.runInIntegratedTerminal', async () => {
            const cmd = await vscode.window.showInputBox({
                title: 'Run in integrated terminal',
                prompt: 'Full shell — same as a normal terminal (not the API sandbox)',
                placeHolder: 'e.g. npm test, docker compose up, git log',
            });
            if (!cmd?.trim()) {
                return;
            }
            const pick = await vscode.window.showQuickPick(
                [
                    { label: '$(terminal) Use active terminal', value: 'active' as const },
                    { label: '$(add) New terminal tab', value: 'new' as const },
                ],
                { title: 'Where to run', placeHolder: 'Choose terminal' }
            );
            if (!pick) {
                return;
            }
            runInIntegratedTerminal(cmd.trim(), { newTerminal: pick.value === 'new' });
        })
    );

    disposables.push(
        vscode.commands.registerCommand('contextforge.runSelectionInIntegratedTerminal', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('No active editor');
                return;
            }
            const text = editor.document.getText(editor.selection).trim();
            if (!text) {
                vscode.window.showWarningMessage('Select a command or text to run');
                return;
            }
            const singleLine = text.includes('\n') ? text.split('\n')[0].trim() : text;
            runInIntegratedTerminal(singleLine, { newTerminal: false });
        })
    );

    disposables.push(
        vscode.commands.registerCommand('contextforge.terminalHub', async () => {
            const choice = await vscode.window.showQuickPick(
                [
                    {
                        label: '$(terminal) Open new integrated terminal',
                        description: 'Workspace folder — full shell',
                        id: 'open',
                    },
                    {
                        label: '$(play) Run command…',
                        description: 'Type a command to run',
                        id: 'run',
                    },
                    {
                        label: '$(code) Run selected text as command',
                        description: 'Uses current selection',
                        id: 'selection',
                    },
                    {
                        label: '$(package) Run npm/yarn/pnpm script…',
                        description: 'From package.json',
                        id: 'npm',
                    },
                    {
                        label: '$(tools) Run Makefile target…',
                        description: 'make & GNUmakefile in workspace root',
                        id: 'makefile',
                    },
                    {
                        label: '$(split-horizontal) Split terminal',
                        description: 'VS Code built-in',
                        id: 'split',
                    },
                    {
                        label: '$(terminal-view) Focus terminal panel',
                        description: 'Bring keyboard to terminal',
                        id: 'focus',
                    },
                    {
                        label: '$(server-process) Execute via ContextForge API (sandboxed)',
                        description: 'Whitelist — capture output in results panel',
                        id: 'api',
                    },
                ],
                { title: 'ContextForge terminal', placeHolder: 'Choose an action' }
            );
            if (!choice) {
                return;
            }
            switch (choice.id) {
                case 'open':
                    vscode.commands.executeCommand('contextforge.openIntegratedTerminal');
                    break;
                case 'run':
                    vscode.commands.executeCommand('contextforge.runInIntegratedTerminal');
                    break;
                case 'selection':
                    vscode.commands.executeCommand('contextforge.runSelectionInIntegratedTerminal');
                    break;
                case 'npm':
                    await pickAndRunPackageScript();
                    break;
                case 'makefile':
                    await pickAndRunMakefileTarget();
                    break;
                case 'split':
                    await vscode.commands.executeCommand('workbench.action.terminal.split');
                    break;
                case 'focus':
                    await vscode.commands.executeCommand('workbench.action.terminal.focus');
                    break;
                case 'api':
                    await vscode.commands.executeCommand('contextforge.executeTerminal');
                    break;
                default:
                    break;
            }
        })
    );

    disposables.push(
        vscode.commands.registerCommand('contextforge.runPackageScript', async () => {
            await pickAndRunPackageScript();
        })
    );

    disposables.push(
        vscode.commands.registerCommand('contextforge.runMakefileTarget', async () => {
            await pickAndRunMakefileTarget();
        })
    );

    async function pickAndRunPackageScript(): Promise<void> {
        const root = workspaceCwd();
        if (!root) {
            vscode.window.showWarningMessage('Open a folder workspace first');
            return;
        }
        const pkgPath = path.join(root, 'package.json');
        if (!fs.existsSync(pkgPath)) {
            vscode.window.showWarningMessage('No package.json in workspace root');
            return;
        }
        let pkg: { scripts?: Record<string, string> };
        try {
            pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
        } catch {
            vscode.window.showErrorMessage('Could not parse package.json');
            return;
        }
        const scripts = pkg.scripts || {};
        const names = Object.keys(scripts);
        if (!names.length) {
            vscode.window.showInformationMessage('No scripts in package.json');
            return;
        }
        const runner = vscode.workspace.getConfiguration('contextforge').get<string>('packageScriptRunner') || 'npm';
        const pick = await vscode.window.showQuickPick(names.sort(), {
            placeHolder: `Run with ${runner} run <script>`,
        });
        if (!pick) {
            return;
        }
        const prefix =
            runner === 'pnpm' ? 'pnpm run' : runner === 'yarn' ? 'yarn' : 'npm run';
        const cmd = runner === 'yarn' ? `yarn ${pick}` : `${prefix} ${pick}`;
        runInIntegratedTerminal(cmd, { newTerminal: false });
    }

    async function pickAndRunMakefileTarget(): Promise<void> {
        const root = workspaceCwd();
        if (!root) {
            vscode.window.showWarningMessage('Open a folder workspace first');
            return;
        }
        const mf = findMakefilePath(root);
        if (!mf) {
            vscode.window.showWarningMessage('No Makefile, makefile, or GNUmakefile in workspace root');
            return;
        }
        const depth =
            vscode.workspace.getConfiguration('contextforge').get<number>('makefileIncludeDepth') ?? 3;
        const content = collectMakefileContentWithIncludes(mf, Math.max(0, depth));
        const names = parseMakefileTargets(content);
        if (!names.length) {
            vscode.window.showInformationMessage('No targets parsed from Makefile (add explicit rules or .PHONY)');
            return;
        }
        const pick = await vscode.window.showQuickPick(names, {
            placeHolder: `make <target> (${path.basename(mf)})`,
        });
        if (!pick) {
            return;
        }
        const makeBin =
            vscode.workspace.getConfiguration('contextforge').get<string>('makeBinary') || 'make';
        runInIntegratedTerminal(`${makeBin} ${pick}`, { newTerminal: false });
    }

    return disposables;
}
