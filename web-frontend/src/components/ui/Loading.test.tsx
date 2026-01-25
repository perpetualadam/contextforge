import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Spinner, LoadingDots, PageLoading, Skeleton, MessageSkeleton, LoadingOverlay } from './Loading';

describe('Spinner', () => {
  it('renders with default size', () => {
    render(<Spinner />);
    const spinner = screen.getByRole('status');
    expect(spinner).toBeInTheDocument();
    expect(spinner).toHaveClass('w-8', 'h-8');
  });

  it('renders with small size', () => {
    render(<Spinner size="sm" />);
    const spinner = screen.getByRole('status');
    expect(spinner).toHaveClass('w-4', 'h-4');
  });

  it('renders with large size', () => {
    render(<Spinner size="lg" />);
    const spinner = screen.getByRole('status');
    expect(spinner).toHaveClass('w-12', 'h-12');
  });

  it('applies custom className', () => {
    render(<Spinner className="text-red-500" />);
    const spinner = screen.getByRole('status');
    expect(spinner).toHaveClass('text-red-500');
  });

  it('has loading label for accessibility', () => {
    render(<Spinner />);
    const spinner = screen.getByLabelText('Loading');
    expect(spinner).toBeInTheDocument();
  });
});

describe('LoadingDots', () => {
  it('renders three dots', () => {
    render(<LoadingDots />);
    const status = screen.getByRole('status');
    expect(status).toBeInTheDocument();
    const dots = status.querySelectorAll('.loading-dot');
    expect(dots).toHaveLength(3);
  });

  it('has loading label', () => {
    render(<LoadingDots />);
    const status = screen.getByLabelText('Loading');
    expect(status).toBeInTheDocument();
  });
});

describe('PageLoading', () => {
  it('renders with default message', () => {
    render(<PageLoading />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('renders with custom message', () => {
    render(<PageLoading message="Please wait..." />);
    expect(screen.getByText('Please wait...')).toBeInTheDocument();
  });

  it('contains a spinner', () => {
    render(<PageLoading />);
    const spinner = screen.getByRole('status');
    expect(spinner).toBeInTheDocument();
  });
});

describe('Skeleton', () => {
  it('renders with text variant by default', () => {
    const { container } = render(<Skeleton />);
    const skeleton = container.firstChild as HTMLElement;
    expect(skeleton).toHaveClass('rounded', 'h-4');
  });

  it('renders with rectangular variant', () => {
    const { container } = render(<Skeleton variant="rectangular" />);
    const skeleton = container.firstChild as HTMLElement;
    expect(skeleton).toHaveClass('rounded-lg');
  });

  it('renders with circular variant', () => {
    const { container } = render(<Skeleton variant="circular" />);
    const skeleton = container.firstChild as HTMLElement;
    expect(skeleton).toHaveClass('rounded-full');
  });

  it('applies custom className', () => {
    const { container } = render(<Skeleton className="w-32" />);
    const skeleton = container.firstChild as HTMLElement;
    expect(skeleton).toHaveClass('w-32');
  });

  it('has aria-hidden attribute', () => {
    const { container } = render(<Skeleton />);
    const skeleton = container.firstChild as HTMLElement;
    expect(skeleton).toHaveAttribute('aria-hidden', 'true');
  });
});

describe('MessageSkeleton', () => {
  it('renders avatar and text skeletons', () => {
    const { container } = render(<MessageSkeleton />);
    const skeletons = container.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});

describe('LoadingOverlay', () => {
  it('renders children when not loading', () => {
    render(
      <LoadingOverlay isLoading={false}>
        <div>Content</div>
      </LoadingOverlay>
    );
    expect(screen.getByText('Content')).toBeInTheDocument();
  });

  it('shows overlay when loading', () => {
    render(
      <LoadingOverlay isLoading={true}>
        <div>Content</div>
      </LoadingOverlay>
    );
    expect(screen.getByText('Content')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows label when loading with label', () => {
    render(
      <LoadingOverlay isLoading={true} label="Processing...">
        <div>Content</div>
      </LoadingOverlay>
    );
    expect(screen.getByText('Processing...')).toBeInTheDocument();
  });

  it('does not show label when not loading', () => {
    render(
      <LoadingOverlay isLoading={false} label="Processing...">
        <div>Content</div>
      </LoadingOverlay>
    );
    expect(screen.queryByText('Processing...')).not.toBeInTheDocument();
  });
});

