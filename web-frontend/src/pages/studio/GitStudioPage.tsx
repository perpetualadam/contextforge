import { useState, useEffect } from 'react';
import { GitBranch, Loader2 } from 'lucide-react';
import {
  Button,
  Input,
  Textarea,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CodeBlock,
} from '../../components/ui';
import { useConnection, useWorkspace, effectiveRepoPath } from '../../store';
import apiClient, { GitRepoOperation, GitCommandTerminalResult, GitHubServerStatus } from '../../api/client';

const OPS: { op: GitRepoOperation; label: string }[] = [
  { op: 'status', label: 'Status' },
  { op: 'branch', label: 'Branches' },
  { op: 'log', label: 'Log' },
  { op: 'diff', label: 'Diff (unstaged)' },
  { op: 'diff_staged', label: 'Diff (staged)' },
  { op: 'remote', label: 'Remotes' },
  { op: 'head', label: 'HEAD' },
  { op: 'stash_list', label: 'Stash' },
];

export function GitStudioPage() {
  const { isOnline } = useConnection();
  const { repoPath } = useWorkspace();
  const [repoOverride, setRepoOverride] = useState('');
  const [logLimit, setLogLimit] = useState(20);
  const [lastResult, setLastResult] = useState<GitCommandTerminalResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingOp, setLoadingOp] = useState<GitRepoOperation | null>(null);

  const path = effectiveRepoPath(repoOverride, repoPath);

  const run = async (operation: GitRepoOperation) => {
    if (!path) {
      setError('Set a repository path (above or in Settings).');
      return;
    }
    setLoadingOp(operation);
    setError(null);
    setLastResult(null);
    try {
      const res = await apiClient.gitRepoCommand({
        repo_path: path,
        operation,
        log_limit: operation === 'log' ? logLimit : 20,
        timeout: 90,
      });
      setLastResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Git command failed');
    } finally {
      setLoadingOp(null);
    }
  };

  const [diffText, setDiffText] = useState('');
  const [stagedFiles, setStagedFiles] = useState('');
  const [branch, setBranch] = useState('main');
  const [recentCommits, setRecentCommits] = useState('');
  const [aiOut, setAiOut] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [ghServer, setGhServer] = useState<GitHubServerStatus | null>(null);

  useEffect(() => {
    if (!isOnline) return;
    let cancelled = false;
    void (async () => {
      try {
        const s = await apiClient.getGitHubServerStatus();
        if (!cancelled) setGhServer(s);
      } catch {
        if (!cancelled) setGhServer(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isOnline]);

  const suggestCommit = async () => {
    const files = stagedFiles
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (!diffText.trim() || files.length === 0) {
      setError('Fill staged diff and at least one staged file path for AI commit message.');
      return;
    }
    setAiLoading(true);
    setError(null);
    setAiOut(null);
    try {
      const r = await apiClient.generateCommitMessage({
        diff: diffText,
        staged_files: files,
        branch: branch.trim() || 'main',
        recent_commits: recentCommits
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean),
      });
      setAiOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Commit message failed');
    } finally {
      setAiLoading(false);
    }
  };

  const fillDiffFromStaged = async () => {
    if (!path) {
      setError('Set a repository path first.');
      return;
    }
    setLoadingOp('diff_staged');
    setError(null);
    try {
      const res = await apiClient.gitRepoCommand({
        repo_path: path,
        operation: 'diff_staged',
        timeout: 120,
      });
      setDiffText(res.stdout + (res.stderr ? `\n${res.stderr}` : ''));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load staged diff');
    } finally {
      setLoadingOp(null);
    }
  };

  const outputText = lastResult
    ? `${lastResult.stdout}${lastResult.stderr ? `\n--- stderr ---\n${lastResult.stderr}` : ''}\n(exit ${lastResult.exit_code})`
    : '';

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-start gap-3">
        <GitBranch className="w-8 h-8 text-primary-600 dark:text-primary-400 shrink-0 mt-1" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Git</h1>
          <p className="text-gray-500 dark:text-gray-400">
            Read-only git commands run on the <strong>server</strong> where the API and terminal executor live. The path
            must be a real git repo on that machine (same idea as ingest).
          </p>
          {ghServer && (
            <div className="mt-3 rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900/40 px-3 py-2 text-sm text-gray-600 dark:text-gray-400">
              <strong className="text-gray-800 dark:text-gray-200">Future GitHub API (gateway):</strong>{' '}
              {ghServer.github_server_disabled
                ? 'Disabled via GITHUB_SERVER_DISABLED.'
                : ghServer.github_server_configured
                  ? 'Token present on server — PR/issue endpoints can be added later.'
                  : 'No GITHUB_SERVER_TOKEN on server yet (optional).'}
            </div>
          )}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Repository</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            label="Path (optional override)"
            value={repoOverride}
            onChange={(e) => setRepoOverride(e.target.value)}
            placeholder={repoPath.trim() || 'Uses Settings workspace path'}
          />
          <p className="text-sm text-gray-500">
            Effective: <span className="font-mono">{path || '(empty)'}</span>
          </p>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 dark:text-gray-400">Log limit</span>
            <input
              type="number"
              min={1}
              max={100}
              value={logLimit}
              onChange={(e) => setLogLimit(Number(e.target.value) || 20)}
              className="w-20 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2 py-1 text-sm"
            />
            <span className="text-xs text-gray-500">(for Log only)</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Commands</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {OPS.map(({ op, label }) => (
              <Button
                key={op}
                type="button"
                variant="secondary"
                size="sm"
                disabled={!path || loadingOp !== null || !isOnline}
                onClick={() => void run(op)}
              >
                {loadingOp === op ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  label
                )}
              </Button>
            ))}
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          {outputText && (
            <CodeBlock code={outputText} language="text" />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AI commit message</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Uses the gateway <code className="text-xs">/git/commit-message</code> endpoint. Paste a diff or load staged
            diff from the repo path above.
          </p>
          <Button type="button" variant="secondary" size="sm" onClick={() => void fillDiffFromStaged()} disabled={!path || loadingOp !== null || !isOnline}>
            Load staged diff from repo
          </Button>
          <Textarea rows={8} value={diffText} onChange={(e) => setDiffText(e.target.value)} placeholder="git diff --cached..." />
          <Input
            label="Staged files (comma-separated paths)"
            value={stagedFiles}
            onChange={(e) => setStagedFiles(e.target.value)}
            placeholder="src/a.ts, src/b.ts"
          />
          <Input label="Branch" value={branch} onChange={(e) => setBranch(e.target.value)} />
          <Textarea
            rows={2}
            value={recentCommits}
            onChange={(e) => setRecentCommits(e.target.value)}
            placeholder="Recent commit subjects (one per line, optional)"
          />
          <Button type="button" onClick={() => void suggestCommit()} disabled={aiLoading || !isOnline} isLoading={aiLoading}>
            Suggest commit message
          </Button>
          {aiOut && <CodeBlock language="json" code={aiOut} />}
        </CardContent>
      </Card>
    </div>
  );
}
