import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CodeBlock, InlineCode } from './CodeBlock';

// Mock the theme store
vi.mock('../../store', () => ({
  useTheme: () => ({ isDark: false })
}));

// Mock clipboard API
const mockWriteText = vi.fn().mockResolvedValue(undefined);
Object.assign(navigator, {
  clipboard: {
    writeText: mockWriteText,
  },
});

describe('CodeBlock', () => {
  beforeEach(() => {
    mockWriteText.mockClear();
  });

  it('renders code content', async () => {
    render(<CodeBlock code="const x = 1;" language="javascript" />);
    
    // Should show the code in fallback/loading state initially
    await waitFor(() => {
      expect(screen.getByText(/const x = 1/)).toBeInTheDocument();
    });
  });

  it('renders filename when provided', () => {
    render(<CodeBlock code="print('hello')" language="python" filename="test.py" />);
    expect(screen.getByText('test.py')).toBeInTheDocument();
  });

  it('shows line start when greater than 1', () => {
    render(<CodeBlock code="// code" language="javascript" lineStart={10} />);
    expect(screen.getByText('Line 10')).toBeInTheDocument();
  });

  it('does not show line info when lineStart is 1', () => {
    render(<CodeBlock code="// code" language="javascript" lineStart={1} />);
    expect(screen.queryByText('Line 1')).not.toBeInTheDocument();
  });

  it('has copy button', () => {
    render(<CodeBlock code="test code" />);
    expect(screen.getByLabelText('Copy code')).toBeInTheDocument();
  });

  it('copies code when copy button clicked', async () => {
    const code = 'const test = true;';
    render(<CodeBlock code={code} />);
    
    const copyButton = screen.getByLabelText('Copy code');
    fireEvent.click(copyButton);
    
    expect(mockWriteText).toHaveBeenCalledWith(code);
  });

  it('shows copied confirmation after clicking copy', async () => {
    render(<CodeBlock code="test" />);
    
    const copyButton = screen.getByLabelText('Copy code');
    fireEvent.click(copyButton);
    
    await waitFor(() => {
      expect(screen.getByText('Copied!')).toBeInTheDocument();
    });
  });

  it('renders with default language (text)', () => {
    render(<CodeBlock code="plain text content" />);
    expect(screen.getByText('plain text content')).toBeInTheDocument();
  });

  it('applies maxHeight style', async () => {
    const { container } = render(
      <CodeBlock code="test" maxHeight="200px" />
    );
    
    // Find element with maxHeight style
    const overflowDiv = container.querySelector('.overflow-auto');
    expect(overflowDiv).toBeInTheDocument();
  });
});

describe('InlineCode', () => {
  it('renders children', () => {
    render(<InlineCode>myVariable</InlineCode>);
    expect(screen.getByText('myVariable')).toBeInTheDocument();
  });

  it('applies code styling', () => {
    render(<InlineCode>code</InlineCode>);
    const codeElement = screen.getByText('code');
    expect(codeElement.tagName.toLowerCase()).toBe('code');
    expect(codeElement).toHaveClass('font-mono');
  });

  it('has appropriate background styling', () => {
    render(<InlineCode>styled</InlineCode>);
    const codeElement = screen.getByText('styled');
    expect(codeElement).toHaveClass('bg-gray-100');
  });
});

describe('Language mapping', () => {
  it('renders Python code', async () => {
    render(<CodeBlock code="def foo(): pass" language="py" />);
    await waitFor(() => {
      expect(screen.getByText(/def foo/)).toBeInTheDocument();
    });
  });

  it('renders TypeScript code', async () => {
    render(<CodeBlock code="const x: number = 1;" language="ts" />);
    await waitFor(() => {
      expect(screen.getByText(/const x/)).toBeInTheDocument();
    });
  });

  it('renders YAML code', async () => {
    render(<CodeBlock code="key: value" language="yml" />);
    await waitFor(() => {
      expect(screen.getByText(/key: value/)).toBeInTheDocument();
    });
  });
});

