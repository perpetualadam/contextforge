import { useState } from 'react';
import { Key, Trash2, Download, Sun, Moon } from 'lucide-react';
import { Button, Input, Card, CardHeader, CardTitle, CardContent } from '../components/ui';
import { ConfirmDialog } from '../components/ui/Modal';
import { useTheme, useChat } from '../store';
import apiClient from '../api/client';

export function SettingsPage() {
  const { isDark, setDark } = useTheme();
  const { conversations, clearHistory } = useChat();
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
              Only required if the ContextForge API has authentication enabled.
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

