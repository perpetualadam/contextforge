import { MessageSquare, Search, FolderUp, Bot, ExternalLink, Keyboard } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui';

export function HelpPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
          Help & Documentation
        </h1>
        <p className="text-gray-500 dark:text-gray-400">
          Learn how to use ContextForge effectively.
        </p>
      </div>

      {/* Features */}
      <div className="grid gap-6 md:grid-cols-2 mb-8">
        <FeatureCard
          icon={MessageSquare}
          title="Chat"
          description="Have multi-turn conversations with an AI assistant that has context about your codebase. Ask questions, get explanations, and explore your code."
        />
        <FeatureCard
          icon={Search}
          title="Query"
          description="Search your codebase with natural language queries. Get relevant code snippets with file paths and line numbers."
        />
        <FeatureCard
          icon={FolderUp}
          title="Ingest"
          description="Index new repositories to make them searchable. Supports multiple programming languages and file types."
        />
        <FeatureCard
          icon={Bot}
          title="Agents"
          description="Monitor the status of local and remote agents that power ContextForge's capabilities."
        />
      </div>

      {/* Keyboard Shortcuts */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>
            <Keyboard className="w-5 h-5 inline mr-2" />
            Keyboard Shortcuts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Shortcut keys={['Enter']} description="Send message (in chat)" />
            <Shortcut keys={['Shift', 'Enter']} description="New line in message" />
            <Shortcut keys={['Ctrl/Cmd', 'K']} description="Focus search" />
            <Shortcut keys={['Esc']} description="Close modal" />
          </div>
        </CardContent>
      </Card>

      {/* API Documentation */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>API Documentation</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            ContextForge provides a REST API for programmatic access. View the full API documentation:
          </p>
          <div className="flex flex-wrap gap-4">
            <a
              href="http://localhost:8080/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-primary-600 dark:text-primary-400 hover:underline"
            >
              <ExternalLink className="w-4 h-4" />
              Swagger UI (localhost:8080/docs)
            </a>
            <a
              href="http://localhost:8080/redoc"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-primary-600 dark:text-primary-400 hover:underline"
            >
              <ExternalLink className="w-4 h-4" />
              ReDoc (localhost:8080/redoc)
            </a>
          </div>
        </CardContent>
      </Card>

      {/* Tips */}
      <Card>
        <CardHeader>
          <CardTitle>Tips for Best Results</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3 text-gray-600 dark:text-gray-400">
            <li className="flex items-start gap-2">
              <span className="text-primary-500 mt-1">•</span>
              <span>Be specific in your queries - include function names, class names, or file paths when possible.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary-500 mt-1">•</span>
              <span>Ingest repositories before querying them for the best context retrieval.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary-500 mt-1">•</span>
              <span>Use the chat for exploratory questions and the query interface for specific code searches.</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary-500 mt-1">•</span>
              <span>Enable web search for questions about external libraries or frameworks.</span>
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function FeatureCard({ icon: Icon, title, description }: { icon: React.ElementType; title: string; description: string }) {
  return (
    <Card>
      <div className="flex items-start gap-4">
        <div className="p-3 rounded-lg bg-primary-100 dark:bg-primary-900">
          <Icon className="w-6 h-6 text-primary-600 dark:text-primary-400" />
        </div>
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">{title}</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">{description}</p>
        </div>
      </div>
    </Card>
  );
}

function Shortcut({ keys, description }: { keys: string[]; description: string }) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-gray-600 dark:text-gray-400">{description}</span>
      <div className="flex gap-1">
        {keys.map((key, idx) => (
          <span key={idx}>
            <kbd className="px-2 py-1 text-xs font-mono bg-gray-100 dark:bg-gray-700 rounded border border-gray-200 dark:border-gray-600">
              {key}
            </kbd>
            {idx < keys.length - 1 && <span className="mx-1 text-gray-400">+</span>}
          </span>
        ))}
      </div>
    </div>
  );
}

