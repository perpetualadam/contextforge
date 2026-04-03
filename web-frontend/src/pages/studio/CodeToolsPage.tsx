import { useState } from 'react';
import { Button, Textarea, Input, Card, CardHeader, CardTitle, CardContent, CodeBlock } from '../../components/ui';
import { useConnection, useWorkspace } from '../../store';
import apiClient from '../../api/client';

export function CodeToolsPage() {
  const { isOnline } = useConnection();
  const { projectRules, privacyMode } = useWorkspace();

  const [prefix, setPrefix] = useState('');
  const [suffix, setSuffix] = useState('');
  const [lang, setLang] = useState('typescript');
  const [path, setPath] = useState('');
  const [completionMaxTokens, setCompletionMaxTokens] = useState(256);
  const [completionOut, setCompletionOut] = useState<string | null>(null);

  const [code, setCode] = useState('');
  const [instruction, setInstruction] = useState('');
  const [inlineOut, setInlineOut] = useState<string | null>(null);

  const [fileContent, setFileContent] = useState('');
  const [smartBlock, setSmartBlock] = useState('');
  const [smartPath, setSmartPath] = useState('');
  const [smartOut, setSmartOut] = useState<string | null>(null);

  const [mcContent, setMcContent] = useState('');
  const [mcInstr, setMcInstr] = useState('');
  const [mcOut, setMcOut] = useState<string | null>(null);

  const [loading, setLoading] = useState<string | null>(null);

  const runCompletion = async () => {
    setLoading('completion');
    setCompletionOut(null);
    try {
      const r = await apiClient.completion({
        prefix,
        suffix: suffix || undefined,
        language: lang,
        file_path: path || undefined,
        max_tokens: Math.min(8192, Math.max(1, completionMaxTokens)),
        privacy_mode: privacyMode,
      });
      setCompletionOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setCompletionOut(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(null);
    }
  };

  const runInline = async () => {
    setLoading('inline');
    setInlineOut(null);
    try {
      const r = await apiClient.inlineEdit({
        code,
        instruction,
        language: lang,
        file_path: path || undefined,
        ...(projectRules.trim() ? { project_rules: projectRules.trim() } : {}),
        privacy_mode: privacyMode,
      });
      setInlineOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setInlineOut(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(null);
    }
  };

  const runSmart = async () => {
    setLoading('smart');
    setSmartOut(null);
    try {
      const r = await apiClient.smartApply({
        file_path: smartPath || 'file.ts',
        file_content: fileContent,
        code_block: smartBlock,
        language: lang,
      });
      setSmartOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setSmartOut(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(null);
    }
  };

  const runMulti = async () => {
    setLoading('multi');
    setMcOut(null);
    try {
      const r = await apiClient.multiCursorEdit({
        file_content: mcContent,
        instruction: mcInstr,
        language: lang,
        file_path: path || undefined,
      });
      setMcOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setMcOut(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Code tools</h1>
        <p className="text-gray-500 dark:text-gray-400">
          Completion, inline edit, smart apply, and multi-cursor edit — same routes as the extension.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Completion</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea rows={4} value={prefix} onChange={(e) => setPrefix(e.target.value)} placeholder="Prefix..." />
          <Textarea rows={2} value={suffix} onChange={(e) => setSuffix(e.target.value)} placeholder="Suffix (optional)" />
          <div className="grid sm:grid-cols-2 gap-3">
            <Input value={lang} onChange={(e) => setLang(e.target.value)} label="Language" />
            <Input value={path} onChange={(e) => setPath(e.target.value)} label="File path (optional)" />
          </div>
          <Input
            type="number"
            min={1}
            max={8192}
            value={completionMaxTokens}
            onChange={(e) => setCompletionMaxTokens(Number(e.target.value) || 256)}
            label="Max completion tokens"
          />
          <Button type="button" onClick={() => void runCompletion()} disabled={!prefix || loading !== null || !isOnline} isLoading={loading === 'completion'}>
            Complete
          </Button>
          {completionOut && <CodeBlock language="json" code={completionOut} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Inline edit</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea rows={6} value={code} onChange={(e) => setCode(e.target.value)} placeholder="Code to edit..." />
          <Textarea rows={2} value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="Instruction..." />
          <Button type="button" onClick={() => void runInline()} disabled={!code || !instruction || loading !== null || !isOnline} isLoading={loading === 'inline'}>
            Edit
          </Button>
          {inlineOut && <CodeBlock language="json" code={inlineOut} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Smart apply</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input value={smartPath} onChange={(e) => setSmartPath(e.target.value)} label="File path" />
          <Textarea rows={6} value={fileContent} onChange={(e) => setFileContent(e.target.value)} placeholder="Full file content..." />
          <Textarea rows={4} value={smartBlock} onChange={(e) => setSmartBlock(e.target.value)} placeholder="Suggested code block to merge..." />
          <Button type="button" onClick={() => void runSmart()} disabled={!fileContent || !smartBlock || loading !== null || !isOnline} isLoading={loading === 'smart'}>
            Apply
          </Button>
          {smartOut && <CodeBlock language="json" code={smartOut} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Multi-cursor edit</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea rows={6} value={mcContent} onChange={(e) => setMcContent(e.target.value)} placeholder="File content..." />
          <Textarea rows={2} value={mcInstr} onChange={(e) => setMcInstr(e.target.value)} placeholder="Instruction for multiple edits..." />
          <Button type="button" onClick={() => void runMulti()} disabled={!mcContent || !mcInstr || loading !== null || !isOnline} isLoading={loading === 'multi'}>
            Propose edits
          </Button>
          {mcOut && <CodeBlock language="json" code={mcOut} />}
        </CardContent>
      </Card>
    </div>
  );
}
