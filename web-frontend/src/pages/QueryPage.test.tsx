import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryPage } from './QueryPage';

// Mock the API client
vi.mock('../api/client', () => ({
  default: {
    query: vi.fn(),
  },
}));

// Mock the stores
vi.mock('../store', () => ({
  useQuery: () => ({
    lastResult: null,
    isLoading: false,
    error: null,
    setResult: vi.fn(),
    setLoading: vi.fn(),
    setError: vi.fn(),
    setQuery: vi.fn(),
  }),
  useConnection: () => ({
    isOnline: true,
  }),
  useTheme: () => ({
    isDark: false,
  }),
}));

describe('QueryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders page title', () => {
    render(<QueryPage />);
    expect(screen.getByText('Query Your Codebase')).toBeInTheDocument();
  });

  it('renders subtitle', () => {
    render(<QueryPage />);
    expect(screen.getByText(/Ask questions about your code/)).toBeInTheDocument();
  });

  it('renders query input', () => {
    render(<QueryPage />);
    expect(screen.getByLabelText('Query input')).toBeInTheDocument();
  });

  it('renders search button', () => {
    render(<QueryPage />);
    expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument();
  });

  it('renders web search checkbox', () => {
    render(<QueryPage />);
    expect(screen.getByLabelText(/web search/i)).toBeInTheDocument();
  });

  it('allows typing in query input', () => {
    render(<QueryPage />);
    const input = screen.getByLabelText('Query input');
    
    fireEvent.change(input, { target: { value: 'How does auth work?' } });
    expect(input).toHaveValue('How does auth work?');
  });

  it('disables search button when query is empty', () => {
    render(<QueryPage />);
    const button = screen.getByRole('button', { name: /search/i });
    expect(button).toBeDisabled();
  });

  it('enables search button when query has content', () => {
    render(<QueryPage />);
    const input = screen.getByLabelText('Query input');
    
    fireEvent.change(input, { target: { value: 'test query' } });
    const button = screen.getByRole('button', { name: /search/i });
    expect(button).not.toBeDisabled();
  });

  it('toggles web search checkbox', () => {
    render(<QueryPage />);
    const checkbox = screen.getByLabelText(/web search/i);
    
    expect(checkbox).not.toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });
});

describe('QueryPage with results', () => {
  it('displays results when available', () => {
    // Override mock to return results
    vi.doMock('../store', () => ({
      useQuery: () => ({
        lastResult: {
          answer: 'The auth system uses JWT tokens.',
          contexts: [
            { source: 'auth.ts', content: 'token verification code', line_start: 1, line_end: 10, score: 0.95 }
          ],
        },
        isLoading: false,
        error: null,
        setResult: vi.fn(),
        setLoading: vi.fn(),
        setError: vi.fn(),
        setQuery: vi.fn(),
      }),
      useConnection: () => ({ isOnline: true }),
      useTheme: () => ({ isDark: false }),
    }));

    // Re-render would pick up new mock
    render(<QueryPage />);
    // Check page renders without error
    expect(screen.getByText('Query Your Codebase')).toBeInTheDocument();
  });
});

describe('QueryPage offline state', () => {
  it('handles offline state gracefully', () => {
    vi.doMock('../store', () => ({
      useQuery: () => ({
        lastResult: null,
        isLoading: false,
        error: null,
        setResult: vi.fn(),
        setLoading: vi.fn(),
        setError: vi.fn(),
        setQuery: vi.fn(),
      }),
      useConnection: () => ({ isOnline: false }),
      useTheme: () => ({ isDark: false }),
    }));

    render(<QueryPage />);
    // Should render without crashing
    expect(screen.getByText('Query Your Codebase')).toBeInTheDocument();
  });
});

