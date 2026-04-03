import { useState } from 'react';
import { Button, Input, Textarea, Card, CardHeader, CardTitle, CardContent, CodeBlock } from '../../components/ui';
import { useConnection } from '../../store';
import apiClient from '../../api/client';

export function DocsStudioPage() {
  const { isOnline } = useConnection();
  const [url, setUrl] = useState('');
  const [label, setLabel] = useState('');
  const [q, setQ] = useState('');
  const [topK, setTopK] = useState(5);
  const [indexOut, setIndexOut] = useState<string | null>(null);
  const [searchOut, setSearchOut] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  const runIndex = async () => {
    if (!url.trim()) return;
    setLoading('index');
    setIndexOut(null);
    try {
      const r = await apiClient.indexDocs(url.trim(), label.trim() || undefined);
      setIndexOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setIndexOut(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(null);
    }
  };

  const runSearch = async () => {
    if (!q.trim()) return;
    setLoading('search');
    setSearchOut(null);
    try {
      const r = await apiClient.searchDocs(q.trim(), topK);
      setSearchOut(JSON.stringify(r, null, 2));
    } catch (e) {
      setSearchOut(e instanceof Error ? e.message : 'Error');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Documentation</h1>
        <p className="text-gray-500 dark:text-gray-400">Index external URLs and search the docs store.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Index URL</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://..." label="URL" />
          <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Optional label" label="Label" />
          <Button type="button" onClick={() => void runIndex()} disabled={!url.trim() || loading !== null || !isOnline} isLoading={loading === 'index'}>
            Index
          </Button>
          {indexOut && <CodeBlock language="json" code={indexOut} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Search</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea rows={3} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Question..." />
          <Input
            type="number"
            min={1}
            max={100}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value) || 5)}
            label="Top K (up to 100)"
          />
          <Button type="button" onClick={() => void runSearch()} disabled={!q.trim() || loading !== null || !isOnline} isLoading={loading === 'search'}>
            Search
          </Button>
          {searchOut && <CodeBlock language="json" code={searchOut} />}
        </CardContent>
      </Card>
    </div>
  );
}
