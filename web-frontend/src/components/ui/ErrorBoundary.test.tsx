import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorBoundary, ErrorFallback, ErrorMessage } from './ErrorBoundary';

// Component that throws an error
function ThrowError({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Test error');
  }
  return <div>No error</div>;
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // Suppress console.error for expected errors
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div>Child content</div>
      </ErrorBoundary>
    );
    
    expect(screen.getByText('Child content')).toBeInTheDocument();
  });

  it('renders default fallback when error occurs', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('renders custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>Custom error UI</div>}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    
    expect(screen.getByText('Custom error UI')).toBeInTheDocument();
  });

  it('calls onError callback when error occurs', () => {
    const onError = vi.fn();
    
    render(
      <ErrorBoundary onError={onError}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    
    expect(onError).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({ componentStack: expect.any(String) })
    );
  });

  it('resets error state when Try again is clicked', () => {
    const onReset = vi.fn();
    let shouldThrow = true;
    
    const { rerender } = render(
      <ErrorBoundary onReset={onReset}>
        <ThrowError shouldThrow={shouldThrow} />
      </ErrorBoundary>
    );
    
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    
    // Change state so component won't throw on re-render
    shouldThrow = false;
    
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    
    expect(onReset).toHaveBeenCalled();
    
    // Re-render with non-throwing component
    rerender(
      <ErrorBoundary onReset={onReset}>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );
  });
});

describe('ErrorFallback', () => {
  it('renders with default props', () => {
    render(<ErrorFallback error={null} />);
    
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText('An unexpected error occurred. Please try again.')).toBeInTheDocument();
  });

  it('renders with custom title and description', () => {
    render(
      <ErrorFallback 
        error={null} 
        title="Custom Title" 
        description="Custom description" 
      />
    );
    
    expect(screen.getByText('Custom Title')).toBeInTheDocument();
    expect(screen.getByText('Custom description')).toBeInTheDocument();
  });

  it('renders reset button when onReset is provided', () => {
    const onReset = vi.fn();
    render(<ErrorFallback error={null} onReset={onReset} />);
    
    const button = screen.getByRole('button', { name: /try again/i });
    expect(button).toBeInTheDocument();
    
    fireEvent.click(button);
    expect(onReset).toHaveBeenCalled();
  });

  it('does not render reset button when onReset is not provided', () => {
    render(<ErrorFallback error={null} />);
    
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});

describe('ErrorMessage', () => {
  it('renders error message', () => {
    render(<ErrorMessage message="Something went wrong" />);
    
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('renders retry button when onRetry is provided', () => {
    const onRetry = vi.fn();
    render(<ErrorMessage message="Error" onRetry={onRetry} />);
    
    const button = screen.getByRole('button', { name: /retry/i });
    expect(button).toBeInTheDocument();
    
    fireEvent.click(button);
    expect(onRetry).toHaveBeenCalled();
  });

  it('applies custom className', () => {
    render(<ErrorMessage message="Error" className="custom-class" />);
    
    expect(screen.getByRole('alert')).toHaveClass('custom-class');
  });
});

