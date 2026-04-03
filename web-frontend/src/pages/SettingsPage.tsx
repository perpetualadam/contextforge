import { useState } from 'react';
import { Key, Trash2, Download, Sun, Moon, FolderOpen, Sliders, Github } from 'lucide-react';
import { Button, Input, Textarea, Card, CardHeader, CardTitle, CardContent } from '../components/ui';
import { ConfirmDialog } from '../components/ui/Modal';
import { useTheme, useChat, useWorkspace, MAX_TOKENS_UI_CAP } from '../store';
import apiClient from '../api/client';

export function SettingsPage() {
  const { isDark, setDark } = useTheme();
  const { conversations, clearHistory } = useChat();
  const {
    repoPath,
    privacyMode,
    projectRules,
    setRepoPath,
    setPrivacyMode,
    setProjectRules,
    queryMaxTokens,
    chatMaxTokens,
    chatWebSearch,
    llmProvider,
    contextCurrentFile,
    contextSelection,
    contextCursorLine,
    contextOpenFiles,
    contextGitDiff,
    queryAutoTerminal,
    queryAutoTerminalTimeout,
    setQueryMaxTokens,
    setChatMaxTokens,
    setChatWebSearch,
    setLlmProvider,
    setContextCurrentFile,
    setContextSelection,
    setContextCursorLine,
    setContextOpenFiles,
    setContextGitDiff,
    setQueryAutoTerminal,
    setQueryAutoTerminalTimeout,
  } = useWorkspace();
  const [apiKey, setApiKey] = useState(apiClient.getApiKey() || '');
  const [showApiKey, setShowApiKey] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSaveApiKey = () => {
    apiClient.setApiKey(apiKey.trim() || null);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleClearApiKey = () => {
    setApiKey('');
    apiClient.setApiKey(null);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleExportHistory = () => {
    const data = JSON.stringify(conversations, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `contextforge-history-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
          Settings
        </h1>
        <p className="text-gray-500 dark:text-gray-400">
          Configure your ContextForge preferences.
        </p>
      </div>

      {/* Theme Settings */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>
            <Sun className="w-5 h-5 inline mr-2" />
            Appearance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <span className="text-gray-700 dark:text-gray-300">Theme:</span>
            <div className="flex gap-2">
              <button
                onClick={() => setDark(false)}
                className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-colors ${
                  !isDark 
                    ? 'bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300' 
                    : 'bg-gray-100 dark:bg-gray-700'
                }`}
                aria-pressed={!isDark}
              >
                <Sun className="w-4 h-4" />
                Light
              </button>
              <button
                onClick={() => setDark(true)}
                className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-colors ${
                  isDark 
                    ? 'bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300' 
                    : 'bg-gray-100 dark:bg-gray-700'
                }`}
                aria-pressed={isDark}
              >
                <Moon className="w-4 h-4" />
                Dark
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>
            <FolderOpen className="w-5 h-5 inline mr-2" />
            Workspace (context engine)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            label="Indexed repository path"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            placeholder="/path/on/server — must match ingest and agent paths"
          />
          <p className="text-sm text-gray-500 dark:text-gray-400 -mt-2">
            Used by Studio tools (composer, agent, orchestrate, terminal cwd). The gateway must see this
            same path when indexing your repo.
          </p>
          <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={privacyMode}
              onChange={(e) => setPrivacyMode(e.target.checked)}
              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            Privacy mode (reduces sensitive context sent to the model; same as the VS Code extension)
          </label>
          <Textarea
            label="Project rules"
            rows={6}
            value={projectRules}
            onChange={(e) => setProjectRules(e.target.value)}
            placeholder="Rules appended to chat, query, agent, and composer requests (like .contextforge-rules)."
          />
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>
            <Sliders className="w-5 h-5 inline mr-2" />
            Model and extra context
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <Input
              type="number"
              min={1}
              max={MAX_TOKENS_UI_CAP}
              label="Query max tokens"
              value={queryMaxTokens}
              onChange={(e) => setQueryMaxTokens(Number(e.target.value))}
            />
            <Input
              type="number"
              min={1}
              max={MAX_TOKENS_UI_CAP}
              label="Chat max tokens"
              value={chatMaxTokens}
              onChange={(e) => setChatMaxTokens(Number(e.target.value))}
            />
          </div>
          <Input
            label="LLM provider (optional)"
            value={llmProvider}
            onChange={(e) => setLlmProvider(e.target.value)}
            placeholder="ollama, openai, anthropic…"
          />
          <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={chatWebSearch}
              onChange={(e) => setChatWebSearch(e.target.checked)}
              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            Enable web search in chat (when the gateway supports it)
          </label>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Optional editor context (sent with chat and query)</p>
          <Input
            label="Current file path"
            value={contextCurrentFile}
            onChange={(e) => setContextCurrentFile(e.target.value)}
            placeholder="src/app.tsx"
          />
          <Input
            label="Cursor line"
            value={contextCursorLine}
            onChange={(e) => setContextCursorLine(e.target.value)}
            placeholder="42"
          />
          <Input
            label="Open files (comma-separated)"
            value={contextOpenFiles}
            onChange={(e) => setContextOpenFiles(e.target.value)}
            placeholder="a.ts, b.ts"
          />
          <Textarea
            label="Current selection (optional)"
            rows={3}
            value={contextSelection}
            onChange={(e) => setContextSelection(e.target.value)}
            placeholder="Highlighted code or notes"
          />
          <Textarea
            label="Git diff snippet (optional)"
            rows={4}
            value={contextGitDiff}
            onChange={(e) => setContextGitDiff(e.target.value)}
            placeholder="Paste a small diff for retrieval context"
          />
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Query: auto-terminal hints</p>
          <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={queryAutoTerminal}
              onChange={(e) => setQueryAutoTerminal(e.target.checked)}
              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            Let the gateway suggest terminal commands from query answers
          </label>
          <Input
            type="number"
            min={1}
            max={300}
            label="Auto-terminal timeout (seconds)"
            value={queryAutoTerminalTimeout}
            onChange={(e) => setQueryAutoTerminalTimeout(Number(e.target.value))}
          />
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>
            <Github className="w-5 h-5 inline mr-2" />
            GitHub API (server, optional)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
            Future PR/issue actions from the web will use a token on the <strong>gateway only</strong> (
            <code className="text-xs font-mono">GITHUB_SERVER_TOKEN</code> or{' '}
            <code className="text-xs font-mono">GITHUB_TOKEN</code>
            ). See <code className="text-xs font-mono">GET /github/status</code> in the API docs. Status is also shown on{' '}
            <a href="/studio/git" className="text-primary-600 dark:text-primary-400 hover:underline">
              Studio → Git
            </a>
            .
          </p>
        </CardContent>
      </Card>

      {/* API Key Settings */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>
            <Key className="w-5 h-5 inline mr-2" />
            API Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              API Key (optional)
            </label>
            <div className="flex gap-2">
              <Input
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your API key"
              />
              <Button variant="secondary" onClick={() => setShowApiKey(!showApiKey)}>
                {showApiKey ? 'Hide' : 'Show'}
              </Button>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Only required if the ContextForge API has authentication enabled. The key is stored in
              this browser&apos;s local storage; anyone with script access to this origin could read it,
              so use a dedicated key and avoid high-privilege credentials in untrusted environments.
            </p>
          </div>

          <div className="flex gap-2">
            <Button onClick={handleSaveApiKey}>
              {saved ? 'Saved!' : 'Save API Key'}
            </Button>
            {apiKey && (
              <Button variant="ghost" onClick={handleClearApiKey}>
                Clear
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Data Management */}
      <Card>
        <CardHeader>
          <CardTitle>
            <Trash2 className="w-5 h-5 inline mr-2" />
            Data Management
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-gray-700 dark:text-gray-300 mb-2">
              Chat History: {conversations.length} conversations
            </p>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={handleExportHistory} disabled={conversations.length === 0}>
                <Download className="w-4 h-4 mr-2" />
                Export History
              </Button>
              <Button variant="danger" onClick={() => setShowClearConfirm(true)} disabled={conversations.length === 0}>
                <Trash2 className="w-4 h-4 mr-2" />
                Clear All
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <ConfirmDialog
        isOpen={showClearConfirm}
        onClose={() => setShowClearConfirm(false)}
        onConfirm={clearHistory}
        title="Clear Chat History"
        message="Are you sure you want to delete all chat conversations? This action cannot be undone."
        confirmText="Delete All"
        variant="danger"
      />
    </div>
  );
}

