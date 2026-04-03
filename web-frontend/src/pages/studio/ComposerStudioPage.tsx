import { useState, useCallback } from 'react';
import { Button, Textarea, Input, Card, CardHeader, CardTitle, CardContent, CodeBlock } from '../../components/ui';
import { useConnection, useWorkspace, effectiveRepoPath } from '../../store';
import apiClient from '../../api/client';

interface ComposerSession {
  session_id?: string;
  state?: string;
  progress?: number;
  current_step?: string;
  changes?: unknown[];
  error?: string | null;
  log?: string[];
}

export function ComposerStudioPage() {
  const { isOnline } = useConnection();
  const { repoPath, projectRules, privacyMode } = useWorkspace();
  const [repoOverride, setRepoOverride] = useState('');
  const [task, setTask] = useState('');
  const [session, setSession] = useState<ComposerSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [pollError, setPollError] = useState<string | null>(null);

  const pollUntilDone = useCallback(async (sessionId: string) => {
    setPollError(null);
    for (;;) {
      try {
        const s = (await apiClient.composerStatus(sessionId)) as ComposerSession;
        setSession({ session_id: sessionId, ...s });
        const st = s.state;
        if (st === 'completed' || st === 'failed') break;
      } catch (e) {
        setPollError(e instanceof Error ? e.message : 'Status poll failed');
        break;
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
  }, []);

  const handleStart = async () => {
    const path = effectiveRepoPath(repoOverride, repoPath);
    if (!task.trim() || !path) return;
    setBusy(true);
    setSession(null);
    setPollError(null);
    try {
      const start = (await apiClient.composerStart({
        task: task.trim(),
        repo_path: path,
        ...(projectRules.trim() ? { project_rules: projectRules.trim() } : {}),
        privacy_mode: privacyMode,
      })) as { session_id: string };
      const sid = start.session_id;
      setSession({ session_id: sid, state: 'starting' });
      await pollUntilDone(sid);
    } catch (e) {
      setPollError(e instanceof Error ? e.message : 'Composer failed to start');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Composer</h1>
        <p className="text-gray-500 dark:text-gray-400">
          Long-running multi-step edits. Uses workspace repo path and rules from Settings.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Task</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            label="Repository path (optional override)"
            value={repoOverride}
            onChange={(e) => setRepoOverride(e.target.value)}
            placeholder={repoPath.trim() || 'Uses Settings path if empty'}
            disabled={busy}
          />
          <Textarea
            rows={5}
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Describe what to build or change across files..."
            disabled={busy}
          />
          <p className="text-sm text-gray-500">
            Effective repo:{' '}
            <span className="font-mono text-gray-700 dark:text-gray-300">
              {effectiveRepoPath(repoOverride, repoPath) || '(set above or in Settings)'}
            </span>
          </p>
          <Button
            type="button"
            onClick={() => void handleStart()}
            disabled={!task.trim() || !effectiveRepoPath(repoOverride, repoPath) || busy || !isOnline}
            isLoading={busy}
          >
            Start session
          </Button>
        </CardContent>
      </Card>

      {(session || pollError) && (
        <Card>
          <CardHeader>
            <CardTitle>Session</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {pollError && <p className="text-red-600 dark:text-red-400 text-sm">{pollError}</p>}
            {session && (
              <>
                <p className="text-sm text-gray-600 dark:text-gray-300">
                  State: <strong>{session.state}</strong>
                  {session.progress != null && ` — ${Math.round(session.progress * 100)}%`}
                </p>
                {session.current_step && (
                  <p className="text-sm text-gray-500">{session.current_step}</p>
                )}
                {session.error && (
                  <p className="text-sm text-red-600 dark:text-red-400">{session.error}</p>
                )}
                <CodeBlock language="json" code={JSON.stringify(session, null, 2)} />
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
