import { useState } from 'react';
import { Search, FileCode, Globe } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Button, Input, Card, CardHeader, CardTitle, CardContent, CodeBlock, Spinner } from '../components/ui';
import { useQuery, useConnection } from '../store';
import apiClient, { CodeContext } from '../api/client';

export function QueryPage() {
  const [query, setQuery] = useState('');
  const [enableWebSearch, setEnableWebSearch] = useState(false);
  const [topK, setTopK] = useState(5);
  
  const { isOnline } = useConnection();
  const { lastResult, isLoading, error, setResult, setLoading, setError, setQuery: storeSetQuery } = useQuery();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    setLoading(true);
    setError(null);
    storeSetQuery(query);

    try {
      const response = await apiClient.query({
        query: query.trim(),
        enable_web_search: enableWebSearch,
        top_k: topK,
      });

      setResult({
        answer: response.answer,
        contexts: response.contexts,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Query failed');
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
          Query Your Codebase
        </h1>
        <p className="text-gray-500 dark:text-gray-400">
          Ask questions about your code and get answers with relevant context.
        </p>
      </div>

      {/* Query Form */}
      <Card className="mb-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-2">
            <div className="flex-1">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask a question about your codebase..."
                disabled={isLoading}
                aria-label="Query input"
              />
            </div>
            <Button type="submit" disabled={!query.trim() || isLoading || !isOnline} isLoading={isLoading}>
              <Search className="w-4 h-4 mr-2" />
              Search
            </Button>
          </div>

          {/* Options */}
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={enableWebSearch}
                onChange={(e) => setEnableWebSearch(e.target.checked)}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <Globe className="w-4 h-4 text-gray-500" />
              <span className="text-gray-700 dark:text-gray-300">Include web search</span>
            </label>

            <label className="flex items-center gap-2">
              <span className="text-gray-700 dark:text-gray-300">Results:</span>
              <select
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="rounded border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
              >
                {[3, 5, 10, 15, 20].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </label>
          </div>
        </form>
      </Card>

      {/* Error */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6" role="alert">
          <p className="text-red-700 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Spinner size="lg" />
        </div>
      )}

      {/* Results */}
      {lastResult && !isLoading && (
        <div className="space-y-6">
          {/* Answer */}
          <Card>
            <CardHeader>
              <CardTitle>Answer</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="prose dark:prose-invert max-w-none">
                <ReactMarkdown>{lastResult.answer}</ReactMarkdown>
              </div>
            </CardContent>
          </Card>

          {/* Code Contexts */}
          {lastResult.contexts.length > 0 && (
            <Card padding="none">
              <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                <h3 className="text-lg font-semibold">Related Code ({lastResult.contexts.length})</h3>
              </div>
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {lastResult.contexts.map((ctx, idx) => (
                  <ContextItem key={idx} context={ctx} />
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Empty State */}
      {!lastResult && !isLoading && !error && (
        <EmptyQueryState />
      )}
    </div>
  );
}

// Context Item Component
function ContextItem({ context }: { context: CodeContext }) {
  const [expanded, setExpanded] = useState(false);
  const language = context.language || context.source.split('.').pop() || 'text';

  return (
    <div className="p-4">
      <div 
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-gray-500" />
          <span className="font-mono text-sm text-primary-600 dark:text-primary-400">{context.source}</span>
          {context.line_start && (
            <span className="text-xs text-gray-500">
              Line {context.line_start}{context.line_end && context.line_end !== context.line_start ? `-${context.line_end}` : ''}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
            Score: {(context.score * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {expanded && (
        <div className="mt-3">
          <CodeBlock
            code={context.content}
            language={language}
            filename={context.source}
            lineStart={context.line_start}
          />
        </div>
      )}
    </div>
  );
}

function EmptyQueryState() {
  return (
    <div className="text-center py-12">
      <Search className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
      <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
        No queries yet
      </h3>
      <p className="text-gray-500 dark:text-gray-400">
        Enter a question above to search your codebase.
      </p>
    </div>
  );
}

