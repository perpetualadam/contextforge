import { useState } from 'react';
import { Button, Textarea, Input, Card, CardHeader, CardTitle, CardContent, CodeBlock } from '../../components/ui';
import { useConnection, useWorkspace, effectiveRepoPath } from '../../store';
import apiClient from '../../api/client';

export function AgentExecuteStudioPage() {
  const { isOnline } = useConnection();
  const { repoPath, projectRules, privacyMode } = useWorkspace();
  const [repoOverride, setRepoOverride] = useState('');
  const [task, setTask] = useState('');
  const [mode, setMode] = useState('plan');
  const [dryRun, setDryRun] = useState(true);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    const path = effectiveRepoPath(repoOverride, repoPath);
    if (!task.trim() || !path) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiClient.agentExecute({
        task: task.trim(),
        repo_path: path,
        mode: mode || undefined,
        dry_run: dryRun,
        ...(projectRules.trim() ? { project_rules: projectRules.trim() } : {}),
        privacy_mode: privacyMode,
      });
      setResult(JSON.stringify(res, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Agent failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Agent execute</h1>
        <p className="text-gray-500 dark:text-gray-400">
          Same endpoint as the extension&apos;s agent mode: proposed file changes from a natural-language task.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Request</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            label="Repository path (optional override)"
            value={repoOverride}
            onChange={(e) => setRepoOverride(e.target.value)}
            placeholder={repoPath.trim() || 'Uses Settings if empty'}
          />
          <Textarea rows={4} value={task} onChange={(e) => setTask(e.target.value)} placeholder="Task..." />
          <Input label="Mode (optional)" value={mode} onChange={(e) => setMode(e.target.value)} placeholder="plan" />
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="rounded border-gray-300 text-primary-600"
            />
            Dry run (no writes)
          </label>
          <p className="text-sm text-gray-500">
            Effective repo:{' '}
            <span className="font-mono">{effectiveRepoPath(repoOverride, repoPath) || '(set above or Settings)'}</span>
          </p>
          <Button
            type="button"
            onClick={() => void run()}
            disabled={!task.trim() || !effectiveRepoPath(repoOverride, repoPath) || loading || !isOnline}
            isLoading={loading}
          >
            Execute
          </Button>
        </CardContent>
      </Card>

      {error && <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Response</CardTitle>
          </CardHeader>
          <CardContent>
            <CodeBlock language="json" code={result} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
