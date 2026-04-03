import { useState } from 'react';
import { Button, Input, Textarea, Card, CardHeader, CardTitle, CardContent, CodeBlock } from '../../components/ui';
import { useConnection, useWorkspace, effectiveRepoPath } from '../../store';
import apiClient from '../../api/client';

export function OrchestrateStudioPage() {
  const { isOnline } = useConnection();
  const { repoPath } = useWorkspace();
  const [repoOverride, setRepoOverride] = useState('');
  const [mode, setMode] = useState('auto');
  const [task, setTask] = useState('full_analysis');
  const [out, setOut] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    const path = effectiveRepoPath(repoOverride, repoPath);
    if (!path) return;
    setLoading(true);
    setOut(null);
    try {
      const r = await apiClient.orchestrate(path, mode, task);
      setOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setOut(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Orchestrate</h1>
        <p className="text-gray-500 dark:text-gray-400">
          Production orchestration pass over the indexed repo (uses workspace path from Settings).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Run</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            label="Repository path (optional override)"
            value={repoOverride}
            onChange={(e) => setRepoOverride(e.target.value)}
            placeholder={repoPath.trim() || 'Uses Settings if empty'}
          />
          <p className="text-sm text-gray-500">
            Effective repo:{' '}
            <span className="font-mono">{effectiveRepoPath(repoOverride, repoPath) || '(set above or Settings)'}</span>
          </p>
          <Input value={mode} onChange={(e) => setMode(e.target.value)} label="Mode" />
          <Textarea rows={2} value={task} onChange={(e) => setTask(e.target.value)} label="Task id" />
          <Button
            type="button"
            onClick={() => void run()}
            disabled={!effectiveRepoPath(repoOverride, repoPath) || loading || !isOnline}
            isLoading={loading}
          >
            Run orchestration
          </Button>
          {out && <CodeBlock language="json" code={out} />}
        </CardContent>
      </Card>
    </div>
  );
}
