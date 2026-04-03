import { useState } from 'react';
import { Button, Input, Textarea, Card, CardHeader, CardTitle, CardContent, CodeBlock } from '../../components/ui';
import { useConnection } from '../../store';
import apiClient from '../../api/client';

export function VectorSearchPage() {
  const { isOnline } = useConnection();
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(10);
  const [out, setOut] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setOut(null);
    try {
      const r = await apiClient.searchVector(query.trim(), topK);
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
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">Vector search</h1>
        <p className="text-gray-500 dark:text-gray-400">Semantic search over the vector index (distinct from the Query page&apos;s RAG flow).</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Search</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea rows={3} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Natural language query..." />
          <Input
            type="number"
            min={1}
            max={100}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value) || 10)}
            label="Top K (up to 100)"
          />
          <Button type="button" onClick={() => void run()} disabled={!query.trim() || loading || !isOnline} isLoading={loading}>
            Search
          </Button>
          {out && <CodeBlock language="json" code={out} />}
        </CardContent>
      </Card>
    </div>
  );
}
