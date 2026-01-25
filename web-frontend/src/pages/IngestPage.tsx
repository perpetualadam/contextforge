import { useState, useEffect } from 'react';
import { FolderUp, Upload, Check, AlertCircle } from 'lucide-react';
import { Button, Input, Card, CardHeader, CardTitle, CardContent } from '../components/ui';
import { useConnection } from '../store';
import apiClient from '../api/client';
import { clsx } from 'clsx';

interface IngestHistory {
  path: string;
  files: number;
  chunks: number;
  timestamp: number;
  status: 'success' | 'error';
}

export function IngestPage() {
  const [path, setPath] = useState('');
  const [recursive, setRecursive] = useState(true);
  const [patterns, setPatterns] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const [history, setHistory] = useState<IngestHistory[]>(() => {
    const saved = localStorage.getItem('contextforge_ingest_history');
    return saved ? JSON.parse(saved) : [];
  });
  const [indexStats, setIndexStats] = useState<{ files: number; chunks: number } | null>(null);

  const { isOnline } = useConnection();

  // Load index stats
  useEffect(() => {
    const loadStats = async () => {
      try {
        const stats = await apiClient.getIngestStatus();
        setIndexStats(stats);
      } catch {
        // Ignore errors
      }
    };
    if (isOnline) loadStats();
  }, [isOnline]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!path.trim() || isLoading) return;

    setIsLoading(true);
    setResult(null);

    try {
      const filePatterns = patterns.trim() 
        ? patterns.split(',').map(p => p.trim()).filter(Boolean)
        : undefined;

      const response = await apiClient.ingest({
        path: path.trim(),
        recursive,
        file_patterns: filePatterns,
      });

      const historyEntry: IngestHistory = {
        path: path.trim(),
        files: response.files_indexed,
        chunks: response.chunks_created,
        timestamp: Date.now(),
        status: 'success',
      };

      const newHistory = [historyEntry, ...history.slice(0, 9)];
      setHistory(newHistory);
      localStorage.setItem('contextforge_ingest_history', JSON.stringify(newHistory));

      setResult({
        success: true,
        message: `Successfully indexed ${response.files_indexed} files (${response.chunks_created} chunks) in ${(response.duration_ms / 1000).toFixed(1)}s`,
      });

      // Refresh stats
      const stats = await apiClient.getIngestStatus();
      setIndexStats(stats);

      setPath('');
    } catch (err) {
      setResult({
        success: false,
        message: err instanceof Error ? err.message : 'Ingestion failed',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
          Ingest Repository
        </h1>
        <p className="text-gray-500 dark:text-gray-400">
          Index a repository or directory to enable code search and context retrieval.
        </p>
      </div>

      {/* Stats */}
      {indexStats && (
        <div className="grid grid-cols-2 gap-4 mb-6">
          <Card className="text-center">
            <div className="text-3xl font-bold text-primary-600 dark:text-primary-400">
              {indexStats.files.toLocaleString()}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">Files Indexed</div>
          </Card>
          <Card className="text-center">
            <div className="text-3xl font-bold text-primary-600 dark:text-primary-400">
              {indexStats.chunks.toLocaleString()}
            </div>
            <div className="text-sm text-gray-500 dark:text-gray-400">Code Chunks</div>
          </Card>
        </div>
      )}

      {/* Ingest Form */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>
            <FolderUp className="w-5 h-5 inline mr-2" />
            Add Repository
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Repository Path"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/path/to/repository or C:\path\to\repo"
              disabled={isLoading}
              helperText="Enter the absolute path to the repository you want to index"
            />

            <Input
              label="File Patterns (optional)"
              value={patterns}
              onChange={(e) => setPatterns(e.target.value)}
              placeholder="*.py, *.js, *.ts"
              disabled={isLoading}
              helperText="Comma-separated file patterns to include. Leave empty for all supported files."
            />

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={recursive}
                onChange={(e) => setRecursive(e.target.checked)}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                disabled={isLoading}
              />
              <span className="text-gray-700 dark:text-gray-300">Include subdirectories</span>
            </label>

            <Button type="submit" disabled={!path.trim() || isLoading || !isOnline} isLoading={isLoading}>
              <Upload className="w-4 h-4 mr-2" />
              {isLoading ? 'Indexing...' : 'Start Ingestion'}
            </Button>
          </form>

          {/* Result Message */}
          {result && (
            <div className={clsx(
              'mt-4 p-4 rounded-lg flex items-start gap-3',
              result.success 
                ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
            )} role="alert">
              {result.success ? <Check className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
              <span>{result.message}</span>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

