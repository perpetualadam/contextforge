import { useState } from 'react';
import { Button, Input, Card, CardHeader, CardTitle, CardContent, CodeBlock } from '../../components/ui';
import { useConnection } from '../../store';
import apiClient from '../../api/client';

export function SymbolsStudioPage() {
  const { isOnline } = useConnection();
  const [symbol, setSymbol] = useState('');
  const [filePath, setFilePath] = useState('');
  const [line, setLine] = useState('');
  const [kind, setKind] = useState<'definition' | 'references'>('definition');
  const [out, setOut] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    if (!symbol.trim()) return;
    setLoading(true);
    setOut(null);
    try {
      const r = await apiClient.symbolLookup({
        symbol: symbol.trim(),
        file_path: filePath.trim() || undefined,
        line: line ? parseInt(line, 10) : undefined,
        kind,
      });
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
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Symbol lookup</h1>
        <p className="text-gray-500 dark:text-gray-400">Definitions and references via the code graph / vector index.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Lookup</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} label="Symbol" placeholder="myFunction" />
          <Input value={filePath} onChange={(e) => setFilePath(e.target.value)} label="File path (optional)" />
          <Input value={line} onChange={(e) => setLine(e.target.value)} label="Line (optional)" />
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Kind</label>
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as 'definition' | 'references')}
              className="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
            >
              <option value="definition">definition</option>
              <option value="references">references</option>
            </select>
          </div>
          <Button type="button" onClick={() => void run()} disabled={!symbol.trim() || loading || !isOnline} isLoading={loading}>
            Lookup
          </Button>
          {out && <CodeBlock language="json" code={out} />}
        </CardContent>
      </Card>
    </div>
  );
}
