import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Card, CardHeader, CardTitle, CardContent } from './index';

describe('Card', () => {
  it('renders children', () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText('Card content')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<Card className="custom-class" data-testid="card">Content</Card>);
    expect(screen.getByTestId('card')).toHaveClass('custom-class');
  });

  it('has correct base styles', () => {
    render(<Card data-testid="card">Content</Card>);
    const card = screen.getByTestId('card');
    expect(card).toHaveClass('rounded-xl', 'bg-white', 'border');
  });

  it('applies variant classes', () => {
    const { rerender } = render(<Card variant="default" data-testid="card">Content</Card>);
    expect(screen.getByTestId('card')).toHaveClass('bg-white', 'border');

    rerender(<Card variant="bordered" data-testid="card">Content</Card>);
    expect(screen.getByTestId('card')).toHaveClass('border-2');

    rerender(<Card variant="elevated" data-testid="card">Content</Card>);
    expect(screen.getByTestId('card')).toHaveClass('shadow-lg');
  });

  it('applies padding classes', () => {
    const { rerender } = render(<Card padding="none" data-testid="card">Content</Card>);
    expect(screen.getByTestId('card')).not.toHaveClass('p-3', 'p-4', 'p-6');

    rerender(<Card padding="sm" data-testid="card">Content</Card>);
    expect(screen.getByTestId('card')).toHaveClass('p-3');

    rerender(<Card padding="md" data-testid="card">Content</Card>);
    expect(screen.getByTestId('card')).toHaveClass('p-4');

    rerender(<Card padding="lg" data-testid="card">Content</Card>);
    expect(screen.getByTestId('card')).toHaveClass('p-6');
  });
});

describe('CardHeader', () => {
  it('renders children', () => {
    render(<CardHeader>Header content</CardHeader>);
    expect(screen.getByText('Header content')).toBeInTheDocument();
  });

  it('has flex and border styles', () => {
    render(<CardHeader data-testid="header">Header</CardHeader>);
    expect(screen.getByTestId('header')).toHaveClass('flex', 'items-center', 'border-b');
  });

  it('applies custom className', () => {
    render(<CardHeader className="custom-header" data-testid="header">Header</CardHeader>);
    expect(screen.getByTestId('header')).toHaveClass('custom-header');
  });
});

describe('CardTitle', () => {
  it('renders as heading', () => {
    render(<CardTitle>Title</CardTitle>);
    expect(screen.getByRole('heading', { name: 'Title' })).toBeInTheDocument();
  });

  it('applies text styles', () => {
    render(<CardTitle>Title</CardTitle>);
    expect(screen.getByRole('heading')).toHaveClass('text-lg', 'font-semibold');
  });

  it('applies custom className', () => {
    render(<CardTitle className="custom-title">Title</CardTitle>);
    expect(screen.getByRole('heading')).toHaveClass('custom-title');
  });
});

describe('CardContent', () => {
  it('renders children', () => {
    render(<CardContent>Body content</CardContent>);
    expect(screen.getByText('Body content')).toBeInTheDocument();
  });

  it('applies top padding', () => {
    render(<CardContent data-testid="content">Body</CardContent>);
    expect(screen.getByTestId('content')).toHaveClass('pt-4');
  });

  it('applies custom className', () => {
    render(<CardContent className="custom-content" data-testid="content">Body</CardContent>);
    expect(screen.getByTestId('content')).toHaveClass('custom-content');
  });
});

describe('Card composition', () => {
  it('renders complete card structure', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Test Card</CardTitle>
        </CardHeader>
        <CardContent>
          <p>Card body content</p>
        </CardContent>
      </Card>
    );

    expect(screen.getByRole('heading', { name: 'Test Card' })).toBeInTheDocument();
    expect(screen.getByText('Card body content')).toBeInTheDocument();
  });
});

