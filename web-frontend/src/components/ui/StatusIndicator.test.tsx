import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { StatusIndicator, ConnectionBanner } from './StatusIndicator';

describe('StatusIndicator', () => {
  it('renders online status', () => {
    render(<StatusIndicator status="online" />);
    const indicator = screen.getByRole('status');
    expect(indicator).toBeInTheDocument();
    expect(screen.getByText('Connected')).toBeInTheDocument();
  });

  it('renders offline status', () => {
    render(<StatusIndicator status="offline" />);
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
  });

  it('renders loading status with animation', () => {
    const { container } = render(<StatusIndicator status="loading" />);
    const dot = container.querySelector('.animate-pulse');
    expect(dot).toBeInTheDocument();
    expect(screen.getByText('Connecting...')).toBeInTheDocument();
  });

  it('renders warning status', () => {
    render(<StatusIndicator status="warning" />);
    expect(screen.getByText('Warning')).toBeInTheDocument();
  });

  it('renders error status', () => {
    render(<StatusIndicator status="error" />);
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('uses custom label', () => {
    render(<StatusIndicator status="online" label="API Connected" />);
    expect(screen.getByText('API Connected')).toBeInTheDocument();
  });

  it('hides label when showLabel is false', () => {
    render(<StatusIndicator status="online" showLabel={false} />);
    expect(screen.queryByText('Connected')).not.toBeInTheDocument();
  });

  it('renders with small size', () => {
    const { container } = render(<StatusIndicator status="online" size="sm" />);
    const dot = container.querySelector('.w-2');
    expect(dot).toBeInTheDocument();
  });

  it('renders with medium size', () => {
    const { container } = render(<StatusIndicator status="online" size="md" />);
    const dot = container.querySelector('.w-3');
    expect(dot).toBeInTheDocument();
  });

  it('renders with large size', () => {
    const { container } = render(<StatusIndicator status="online" size="lg" />);
    const dot = container.querySelector('.w-4');
    expect(dot).toBeInTheDocument();
  });

  it('has accessible aria-label', () => {
    render(<StatusIndicator status="online" />);
    const indicator = screen.getByRole('status');
    expect(indicator).toHaveAttribute('aria-label', 'Connected');
  });

  it('applies correct color for each status', () => {
    const { container, rerender } = render(<StatusIndicator status="online" />);
    expect(container.querySelector('.bg-green-500')).toBeInTheDocument();

    rerender(<StatusIndicator status="offline" />);
    expect(container.querySelector('.bg-gray-400')).toBeInTheDocument();

    rerender(<StatusIndicator status="error" />);
    expect(container.querySelector('.bg-red-500')).toBeInTheDocument();

    rerender(<StatusIndicator status="warning" />);
    expect(container.querySelector('.bg-yellow-500')).toBeInTheDocument();
  });
});

describe('ConnectionBanner', () => {
  it('returns null when online', () => {
    const { container } = render(<ConnectionBanner isOnline={true} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders banner when offline', () => {
    render(<ConnectionBanner isOnline={false} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/You are currently offline/)).toBeInTheDocument();
  });

  it('shows retry button when onRetry provided', () => {
    const onRetry = vi.fn();
    render(<ConnectionBanner isOnline={false} onRetry={onRetry} />);
    expect(screen.getByText('Retry connection')).toBeInTheDocument();
  });

  it('does not show retry button when onRetry not provided', () => {
    render(<ConnectionBanner isOnline={false} />);
    expect(screen.queryByText('Retry connection')).not.toBeInTheDocument();
  });

  it('calls onRetry when retry button clicked', () => {
    const onRetry = vi.fn();
    render(<ConnectionBanner isOnline={false} onRetry={onRetry} />);
    
    fireEvent.click(screen.getByText('Retry connection'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

