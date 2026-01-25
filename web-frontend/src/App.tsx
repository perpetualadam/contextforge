import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/layout';
import { ChatPage, QueryPage, IngestPage, AgentsPage, SettingsPage, HelpPage } from './pages';

function App() {
  return (
    <Layout>
      <Routes>
        {/* Default redirect to chat */}
        <Route path="/" element={<Navigate to="/chat" replace />} />
        
        {/* Main routes */}
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/query" element={<QueryPage />} />
        <Route path="/ingest" element={<IngestPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/help" element={<HelpPage />} />
        
        {/* 404 fallback */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <h1 className="text-6xl font-bold text-gray-300 dark:text-gray-600 mb-4">404</h1>
      <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
        Page Not Found
      </h2>
      <p className="text-gray-500 dark:text-gray-400 mb-6">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <a
        href="/chat"
        className="inline-flex items-center px-4 py-2 rounded-lg bg-primary-600 text-white hover:bg-primary-700 transition-colors"
      >
        Go to Chat
      </a>
    </div>
  );
}

export default App;

