import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './Button';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[ErrorBoundary] Caught error:', error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <ErrorFallback
          error={this.state.error}
          onReset={this.handleReset}
        />
      );
    }

    return this.props.children;
  }
}

interface ErrorFallbackProps {
  error: Error | null;
  onReset?: () => void;
  title?: string;
  description?: string;
}

export function ErrorFallback({ 
  error, 
  onReset, 
  title = 'Something went wrong',
  description = 'An unexpected error occurred. Please try again.'
}: ErrorFallbackProps) {
  return (
    <div 
      className="flex flex-col items-center justify-center min-h-[300px] p-8 text-center"
      role="alert"
    >
      <div className="flex items-center justify-center w-16 h-16 mb-4 rounded-full bg-red-100 dark:bg-red-900/30">
        <AlertTriangle className="w-8 h-8 text-red-600 dark:text-red-400" aria-hidden="true" />
      </div>
      
      <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
        {title}
      </h2>
      
      <p className="text-gray-600 dark:text-gray-400 mb-4 max-w-md">
        {description}
      </p>
      
      {error && import.meta.env.DEV && (
        <details className="mb-4 text-left w-full max-w-lg">
          <summary className="cursor-pointer text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
            Error details
          </summary>
          <pre className="mt-2 p-4 bg-gray-100 dark:bg-gray-800 rounded-lg text-xs overflow-auto">
            <code>{error.message}</code>
            {error.stack && (
              <>
                {'\n\n'}
                <code className="text-gray-500">{error.stack}</code>
              </>
            )}
          </pre>
        </details>
      )}
      
      {onReset && (
        <Button onClick={onReset} variant="primary">
          <RefreshCw className="w-4 h-4 mr-2" aria-hidden="true" />
          Try again
        </Button>
      )}
    </div>
  );
}

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorMessage({ message, onRetry, className }: ErrorMessageProps) {
  return (
    <div 
      className={`flex items-center gap-3 p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 ${className || ''}`}
      role="alert"
    >
      <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0" aria-hidden="true" />
      <p className="text-sm text-red-700 dark:text-red-300 flex-1">{message}</p>
      {onRetry && (
        <Button size="sm" variant="ghost" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

