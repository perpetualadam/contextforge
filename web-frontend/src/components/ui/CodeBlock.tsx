import { useState, lazy, Suspense, useMemo } from 'react';
import { Copy, Check, FileCode } from 'lucide-react';
import { useTheme } from '../../store';
import { clsx } from 'clsx';

// Lazy load syntax highlighter - this is the largest dependency
const SyntaxHighlighter = lazy(() =>
  import('react-syntax-highlighter/dist/esm/prism-light').then((mod) => ({
    default: mod.default,
  }))
);

// Lazy load styles
const loadStyles = async (isDark: boolean) => {
  if (isDark) {
    const { oneDark } = await import('react-syntax-highlighter/dist/esm/styles/prism');
    return oneDark;
  } else {
    const { oneLight } = await import('react-syntax-highlighter/dist/esm/styles/prism');
    return oneLight;
  }
};

// Pre-defined fallback for loading state
function CodeLoadingFallback({ code, maxHeight }: { code: string; maxHeight: string }) {
  return (
    <pre
      className="overflow-auto p-4 font-mono text-sm bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-200"
      style={{ maxHeight }}
    >
      {code.trim()}
    </pre>
  );
}

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
  lineStart?: number;
  showLineNumbers?: boolean;
  maxHeight?: string;
}

// Map common language aliases
const languageMap: Record<string, string> = {
  py: 'python',
  js: 'javascript',
  ts: 'typescript',
  tsx: 'tsx',
  jsx: 'jsx',
  sh: 'bash',
  yml: 'yaml',
  md: 'markdown',
};

function CodeBlockInner({
  code,
  language = 'text',
  lineStart = 1,
  showLineNumbers = true,
  maxHeight = '400px',
  isDark,
}: CodeBlockProps & { isDark: boolean }) {
  const [style, setStyle] = useState<Record<string, React.CSSProperties> | null>(null);

  // Load style on mount
  useMemo(() => {
    loadStyles(isDark).then(setStyle);
  }, [isDark]);

  const normalizedLang = languageMap[language.toLowerCase()] || language.toLowerCase();

  if (!style) {
    return <CodeLoadingFallback code={code} maxHeight={maxHeight} />;
  }

  return (
    <div className="overflow-auto" style={{ maxHeight }}>
      <SyntaxHighlighter
        language={normalizedLang}
        style={style}
        showLineNumbers={showLineNumbers}
        startingLineNumber={lineStart}
        customStyle={{
          margin: 0,
          padding: '1rem',
          fontSize: '0.875rem',
          backgroundColor: isDark ? '#1e1e1e' : '#fafafa',
        }}
        lineNumberStyle={{
          minWidth: '3em',
          paddingRight: '1em',
          color: isDark ? '#606060' : '#999',
        }}
      >
        {code.trim()}
      </SyntaxHighlighter>
    </div>
  );
}

export function CodeBlock({
  code,
  language = 'text',
  filename,
  lineStart = 1,
  showLineNumbers = true,
  maxHeight = '400px',
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const { isDark } = useTheme();

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
          <FileCode className="w-4 h-4" aria-hidden="true" />
          {filename && (
            <span className="font-mono">{filename}</span>
          )}
          {lineStart > 1 && (
            <span className="text-gray-500">Line {lineStart}</span>
          )}
        </div>
        <button
          onClick={handleCopy}
          className={clsx(
            'flex items-center gap-1 px-2 py-1 rounded text-sm transition-colors',
            'hover:bg-gray-200 dark:hover:bg-gray-700',
            'focus:outline-none focus:ring-2 focus:ring-primary-500'
          )}
          aria-label={copied ? 'Copied!' : 'Copy code'}
        >
          {copied ? (
            <>
              <Check className="w-4 h-4 text-green-500" aria-hidden="true" />
              <span className="text-green-500">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-4 h-4" aria-hidden="true" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Code with lazy loading */}
      <Suspense fallback={<CodeLoadingFallback code={code} maxHeight={maxHeight} />}>
        <CodeBlockInner
          code={code}
          language={language}
          lineStart={lineStart}
          showLineNumbers={showLineNumbers}
          maxHeight={maxHeight}
          isDark={isDark}
        />
      </Suspense>
    </div>
  );
}

// Inline code component
export function InlineCode({ children }: { children: React.ReactNode }) {
  return (
    <code className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 font-mono text-sm text-primary-600 dark:text-primary-400">
      {children}
    </code>
  );
}

