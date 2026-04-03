import { useState } from 'react';
import { Button, Textarea, Input, Card, CardHeader, CardTitle, CardContent, CodeBlock } from '../../components/ui';
import { useConnection, useWorkspace, effectiveRepoPath } from '../../store';
import apiClient from '../../api/client';

export function TerminalStudioPage() {
  const { isOnline } = useConnection();
  const { repoPath } = useWorkspace();
  const [repoOverride, setRepoOverride] = useState('');
  const [command, setCommand] = useState('');
  const [cwd, setCwd] = useState('');
  const [timeoutSec, setTimeoutSec] = useState(60);
  const [taskDesc, setTaskDesc] = useState('');
  const [ctx, setCtx] = useState('');
  const [execOut, setExecOut] = useState<string | null>(null);
  const [suggestOut, setSuggestOut] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  const effectiveCwd = cwd.trim() || effectiveRepoPath(repoOverride, repoPath);

  const runExec = async () => {
    if (!command.trim()) return;
    setLoading('exec');
    setExecOut(null);
    try {
      const r = await apiClient.terminalExecute({
        command: command.trim(),
        working_directory: effectiveCwd || undefined,
        timeout: timeoutSec,
      });
      setExecOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setExecOut(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(null);
    }
  };

  const runSuggest = async () => {
    if (!taskDesc.trim()) return;
    setLoading('suggest');
    setSuggestOut(null);
    try {
      const r = await apiClient.terminalSuggest({
        task_description: taskDesc.trim(),
        context: ctx.trim() || undefined,
        working_directory: effectiveCwd || undefined,
      });
      setSuggestOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setSuggestOut(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Terminal</h1>
        <p className="text-gray-500 dark:text-gray-400">
          Executes on the gateway host. Default working directory falls back to the workspace repo path from Settings.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Execute</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            label="Default repo path (optional override)"
            value={repoOverride}
            onChange={(e) => setRepoOverride(e.target.value)}
            placeholder={repoPath.trim() || 'Used as cwd when below is empty'}
          />
          <Input value={command} onChange={(e) => setCommand(e.target.value)} placeholder="npm test" label="Command" />
          <Input
            value={cwd}
            onChange={(e) => setCwd(e.target.value)}
            label="Working directory (optional)"
            placeholder="Overrides repo path if set"
          />
          <Input
            type="number"
            min={5}
            max={300}
            value={timeoutSec}
            onChange={(e) => setTimeoutSec(Number(e.target.value) || 60)}
            label="Timeout (seconds, max 300 per gateway)"
          />
          <Button type="button" onClick={() => void runExec()} disabled={!command.trim() || loading !== null || !isOnline} isLoading={loading === 'exec'}>
            Run
          </Button>
          {execOut && <CodeBlock language="json" code={execOut} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Suggest command</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea rows={3} value={taskDesc} onChange={(e) => setTaskDesc(e.target.value)} placeholder="Describe what you want to do..." />
          <Textarea rows={2} value={ctx} onChange={(e) => setCtx(e.target.value)} placeholder="Extra context (optional)" />
          <Button type="button" onClick={() => void runSuggest()} disabled={!taskDesc.trim() || loading !== null || !isOnline} isLoading={loading === 'suggest'}>
            Suggest
          </Button>
          {suggestOut && <CodeBlock language="json" code={suggestOut} />}
        </CardContent>
      </Card>
    </div>
  );
}
