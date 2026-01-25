import { clsx } from 'clsx';

interface StatusIndicatorProps {
  status: 'online' | 'offline' | 'loading' | 'warning' | 'error';
  label?: string;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export function StatusIndicator({ 
  status, 
  label, 
  showLabel = true,
  size = 'md' 
}: StatusIndicatorProps) {
  const colors = {
    online: 'bg-green-500',
    offline: 'bg-gray-400',
    loading: 'bg-yellow-500',
    warning: 'bg-yellow-500',
    error: 'bg-red-500',
  };

  const labels = {
    online: label || 'Connected',
    offline: label || 'Disconnected',
    loading: label || 'Connecting...',
    warning: label || 'Warning',
    error: label || 'Error',
  };

  const sizes = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4',
  };

  const textSizes = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
  };

  return (
    <div 
      className="flex items-center gap-2"
      role="status"
      aria-label={labels[status]}
    >
      <span 
        className={clsx(
          'rounded-full flex-shrink-0',
          sizes[size],
          colors[status],
          status === 'loading' && 'animate-pulse'
        )}
        aria-hidden="true"
      />
      {showLabel && (
        <span className={clsx(
          'text-gray-600 dark:text-gray-400',
          textSizes[size]
        )}>
          {labels[status]}
        </span>
      )}
    </div>
  );
}

// Connection Status Banner
interface ConnectionBannerProps {
  isOnline: boolean;
  onRetry?: () => void;
}

export function ConnectionBanner({ isOnline, onRetry }: ConnectionBannerProps) {
  if (isOnline) return null;

  return (
    <div 
      className="fixed top-0 left-0 right-0 z-50 bg-yellow-500 text-yellow-900 px-4 py-2 text-center text-sm font-medium"
      role="alert"
    >
      <span>You are currently offline. Some features may be unavailable.</span>
      {onRetry && (
        <button 
          onClick={onRetry}
          className="ml-4 underline hover:no-underline focus:outline-none focus:ring-2 focus:ring-yellow-900 rounded"
        >
          Retry connection
        </button>
      )}
    </div>
  );
}

