import { useState } from 'react';
import { Button, Textarea, Input, Card, CardHeader, CardTitle, CardContent, CodeBlock } from '../../components/ui';
import { useConnection } from '../../store';
import apiClient from '../../api/client';

export function PromptStudioPage() {
  const { isOnline } = useConnection();
  const [prompt, setPrompt] = useState('');
  const [context, setContext] = useState('');
  const [style, setStyle] = useState('professional');
  const [taskType, setTaskType] = useState('general');
  const [filePath, setFilePath] = useState('');
  const [enhanceOut, setEnhanceOut] = useState<string | null>(null);
  const [ctxOut, setCtxOut] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  const runEnhance = async () => {
    if (!prompt.trim()) return;
    setLoading('enhance');
    setEnhanceOut(null);
    try {
      const r = await apiClient.promptEnhance({
        prompt: prompt.trim(),
        context: context.trim() || undefined,
        style,
      });
      setEnhanceOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setEnhanceOut(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(null);
    }
  };

  const runContext = async () => {
    if (!prompt.trim()) return;
    setLoading('context');
    setCtxOut(null);
    try {
      const r = await apiClient.promptContextEnhance({
        prompt: prompt.trim(),
        context: context.trim() || undefined,
        task_type: taskType,
        file_path: filePath.trim() || undefined,
      });
      setCtxOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setCtxOut(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Prompt tools</h1>
        <p className="text-gray-500 dark:text-gray-400">
          LLM prompt enhancement and context-aware injection (same gateway routes as the extension).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Enhance (LLM)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea rows={4} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Your prompt..." />
          <Textarea rows={2} value={context} onChange={(e) => setContext(e.target.value)} placeholder="Extra context (optional)" />
          <Input value={style} onChange={(e) => setStyle(e.target.value)} label="Style" />
          <Button type="button" onClick={() => void runEnhance()} disabled={!prompt.trim() || loading !== null || !isOnline} isLoading={loading === 'enhance'}>
            Enhance
          </Button>
          {enhanceOut && <CodeBlock language="json" code={enhanceOut} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Context enhance</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input value={taskType} onChange={(e) => setTaskType(e.target.value)} label="Task type" placeholder="general, code_review, ..." />
          <Input value={filePath} onChange={(e) => setFilePath(e.target.value)} label="File path (optional)" />
          <Button type="button" onClick={() => void runContext()} disabled={!prompt.trim() || loading !== null || !isOnline} isLoading={loading === 'context'}>
            Context enhance
          </Button>
          {ctxOut && <CodeBlock language="json" code={ctxOut} />}
        </CardContent>
      </Card>
    </div>
  );
}
