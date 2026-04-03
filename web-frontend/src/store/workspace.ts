import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { EditorContext } from '../api/client';

/** Matches gateway MAX_OUTPUT_TOKENS default cap (raise via server env if needed). */
export const MAX_TOKENS_UI_CAP = 131072;

/**
 * Mirrors VS Code extension workspace settings: indexed repo path on the server,
 * privacy mode, project rules, and optional editor/model hints for the context engine.
 */
interface WorkspaceState {
  repoPath: string;
  privacyMode: boolean;
  projectRules: string;
  /** Query (/query) max output tokens (1–MAX_TOKENS_UI_CAP). */
  queryMaxTokens: number;
  /** Chat max output tokens. */
  chatMaxTokens: number;
  /** Pass web search flag to chat (same as extension capability). */
  chatWebSearch: boolean;
  /** Optional LLM provider id sent to the gateway when set. */
  llmProvider: string;
  contextCurrentFile: string;
  contextSelection: string;
  /** Line number as string; empty if unset. */
  contextCursorLine: string;
  /** Comma-separated paths. */
  contextOpenFiles: string;
  contextGitDiff: string;
  queryAutoTerminal: boolean;
  queryAutoTerminalTimeout: number;

  setRepoPath: (p: string) => void;
  setPrivacyMode: (v: boolean) => void;
  setProjectRules: (s: string) => void;
  setQueryMaxTokens: (n: number) => void;
  setChatMaxTokens: (n: number) => void;
  setChatWebSearch: (v: boolean) => void;
  setLlmProvider: (s: string) => void;
  setContextCurrentFile: (s: string) => void;
  setContextSelection: (s: string) => void;
  setContextCursorLine: (s: string) => void;
  setContextOpenFiles: (s: string) => void;
  setContextGitDiff: (s: string) => void;
  setQueryAutoTerminal: (v: boolean) => void;
  setQueryAutoTerminalTimeout: (n: number) => void;
}

export function clampTokens(n: number): number {
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.min(Math.floor(n), MAX_TOKENS_UI_CAP);
}

export function buildEditorContext(w: {
  contextCurrentFile: string;
  contextSelection: string;
  contextCursorLine: string;
  contextOpenFiles: string;
  contextGitDiff: string;
}): EditorContext | undefined {
  const openFiles = w.contextOpenFiles
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  const line = parseInt(w.contextCursorLine.trim(), 10);
  const cursor_line = Number.isFinite(line) && line > 0 ? line : undefined;

  const ec: EditorContext = {};
  if (w.contextCurrentFile.trim()) ec.current_file = w.contextCurrentFile.trim();
  if (w.contextSelection.trim()) ec.current_selection = w.contextSelection.trim();
  if (cursor_line != null) ec.cursor_line = cursor_line;
  if (openFiles.length) ec.open_files = openFiles;
  if (w.contextGitDiff.trim()) ec.git_diff = w.contextGitDiff.trim();

  if (
    !ec.current_file &&
    !ec.current_selection &&
    ec.cursor_line == null &&
    !ec.open_files?.length &&
    !ec.git_diff
  ) {
    return undefined;
  }
  return ec;
}

export const useWorkspace = create<WorkspaceState>()(
  persist(
    (set) => ({
      repoPath: '',
      privacyMode: false,
      projectRules: '',
      queryMaxTokens: 8192,
      chatMaxTokens: 4096,
      chatWebSearch: false,
      llmProvider: '',
      contextCurrentFile: '',
      contextSelection: '',
      contextCursorLine: '',
      contextOpenFiles: '',
      contextGitDiff: '',
      queryAutoTerminal: false,
      queryAutoTerminalTimeout: 30,

      setRepoPath: (repoPath) => set({ repoPath }),
      setPrivacyMode: (privacyMode) => set({ privacyMode }),
      setProjectRules: (projectRules) => set({ projectRules }),
      setQueryMaxTokens: (queryMaxTokens) => set({ queryMaxTokens: clampTokens(queryMaxTokens) }),
      setChatMaxTokens: (chatMaxTokens) => set({ chatMaxTokens: clampTokens(chatMaxTokens) }),
      setChatWebSearch: (chatWebSearch) => set({ chatWebSearch }),
      setLlmProvider: (llmProvider) => set({ llmProvider }),
      setContextCurrentFile: (contextCurrentFile) => set({ contextCurrentFile }),
      setContextSelection: (contextSelection) => set({ contextSelection }),
      setContextCursorLine: (contextCursorLine) => set({ contextCursorLine }),
      setContextOpenFiles: (contextOpenFiles) => set({ contextOpenFiles }),
      setContextGitDiff: (contextGitDiff) => set({ contextGitDiff }),
      setQueryAutoTerminal: (queryAutoTerminal) => set({ queryAutoTerminal }),
      setQueryAutoTerminalTimeout: (queryAutoTerminalTimeout) =>
        set({
          queryAutoTerminalTimeout: Math.min(300, Math.max(1, Math.floor(queryAutoTerminalTimeout))),
        }),
    }),
    {
      name: 'contextforge-workspace',
      version: 2,
      partialize: (s) => ({
        repoPath: s.repoPath,
        privacyMode: s.privacyMode,
        projectRules: s.projectRules,
        queryMaxTokens: s.queryMaxTokens,
        chatMaxTokens: s.chatMaxTokens,
        chatWebSearch: s.chatWebSearch,
        llmProvider: s.llmProvider,
        contextCurrentFile: s.contextCurrentFile,
        contextSelection: s.contextSelection,
        contextCursorLine: s.contextCursorLine,
        contextOpenFiles: s.contextOpenFiles,
        contextGitDiff: s.contextGitDiff,
        queryAutoTerminal: s.queryAutoTerminal,
        queryAutoTerminalTimeout: s.queryAutoTerminalTimeout,
      }),
      migrate: (persisted: unknown) => {
        const p = persisted as Partial<WorkspaceState>;
        return {
          repoPath: p.repoPath ?? '',
          privacyMode: p.privacyMode ?? false,
          projectRules: p.projectRules ?? '',
          queryMaxTokens: clampTokens(p.queryMaxTokens ?? 8192),
          chatMaxTokens: clampTokens(p.chatMaxTokens ?? 4096),
          chatWebSearch: p.chatWebSearch ?? false,
          llmProvider: p.llmProvider ?? '',
          contextCurrentFile: p.contextCurrentFile ?? '',
          contextSelection: p.contextSelection ?? '',
          contextCursorLine: p.contextCursorLine ?? '',
          contextOpenFiles: p.contextOpenFiles ?? '',
          contextGitDiff: p.contextGitDiff ?? '',
          queryAutoTerminal: p.queryAutoTerminal ?? false,
          queryAutoTerminalTimeout: p.queryAutoTerminalTimeout ?? 30,
        };
      },
    }
  )
);

/** Effective repo path for Studio tools: inline override wins, then saved Settings path. */
export function effectiveRepoPath(override: string, saved: string): string {
  return override.trim() || saved.trim();
}
