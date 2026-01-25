import { describe, it, expect, beforeEach } from 'vitest';
import { useChat, useQuery, useTheme, useConnection, useStatus } from './index';
import { act, renderHook } from '@testing-library/react';

describe('useChat store', () => {
  beforeEach(() => {
    const { result } = renderHook(() => useChat());
    act(() => {
      result.current.clearHistory();
    });
  });

  it('starts with empty conversations', () => {
    const { result } = renderHook(() => useChat());
    expect(result.current.conversations).toEqual([]);
  });

  it('creates a new conversation', () => {
    const { result } = renderHook(() => useChat());

    let convId: string;
    act(() => {
      convId = result.current.createConversation();
    });

    expect(result.current.conversations).toHaveLength(1);
    expect(result.current.activeConversationId).toBe(convId!);
  });

  it('adds messages to a conversation', () => {
    const { result } = renderHook(() => useChat());

    let convId: string;
    act(() => {
      convId = result.current.createConversation();
      result.current.addMessage(convId, { role: 'user', content: 'Hello' });
    });

    const conv = result.current.conversations.find(c => c.id === convId!);
    expect(conv?.messages).toHaveLength(1);
    expect(conv?.messages[0]).toMatchObject({
      role: 'user',
      content: 'Hello',
    });
  });

  it('clears all conversations', () => {
    const { result } = renderHook(() => useChat());

    act(() => {
      result.current.createConversation();
      result.current.clearHistory();
    });

    expect(result.current.conversations).toEqual([]);
    expect(result.current.activeConversationId).toBeNull();
  });

  it('manages loading state', () => {
    const { result } = renderHook(() => useChat());

    expect(result.current.isLoading).toBe(false);

    act(() => {
      result.current.setLoading(true);
    });

    expect(result.current.isLoading).toBe(true);
  });

  it('manages error state', () => {
    const { result } = renderHook(() => useChat());

    expect(result.current.error).toBeNull();

    act(() => {
      result.current.setError('Something went wrong');
    });

    expect(result.current.error).toBe('Something went wrong');
  });

  it('deletes a conversation', () => {
    const { result } = renderHook(() => useChat());

    let convId: string;
    act(() => {
      convId = result.current.createConversation();
    });

    expect(result.current.conversations).toHaveLength(1);

    act(() => {
      result.current.deleteConversation(convId!);
    });

    expect(result.current.conversations).toHaveLength(0);
  });
});

describe('useQuery store', () => {
  it('manages query state', () => {
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.setQuery('test query');
    });

    expect(result.current.lastQuery).toBe('test query');
  });

  it('manages result state', () => {
    const { result } = renderHook(() => useQuery());
    const mockResult = {
      answer: 'Test answer',
      contexts: [{ source: 'test.ts', content: 'code', line_start: 1, line_end: 10, score: 0.9 }],
    };

    act(() => {
      result.current.setResult(mockResult);
    });

    expect(result.current.lastResult).toEqual(mockResult);
  });

  it('manages loading state', () => {
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.setLoading(true);
    });

    expect(result.current.isLoading).toBe(true);
  });

  it('manages error state', () => {
    const { result } = renderHook(() => useQuery());

    act(() => {
      result.current.setError('Query failed');
    });

    expect(result.current.error).toBe('Query failed');
  });
});

describe('useTheme store', () => {
  it('toggles theme', () => {
    const { result } = renderHook(() => useTheme());
    const initialDark = result.current.isDark;

    act(() => {
      result.current.toggle();
    });

    expect(result.current.isDark).toBe(!initialDark);
  });

  it('sets theme explicitly', () => {
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setDark(true);
    });

    expect(result.current.isDark).toBe(true);

    act(() => {
      result.current.setDark(false);
    });

    expect(result.current.isDark).toBe(false);
  });
});

describe('useConnection store', () => {
  it('manages online state', () => {
    const { result } = renderHook(() => useConnection());

    act(() => {
      result.current.setOnline(false);
    });

    expect(result.current.isOnline).toBe(false);

    act(() => {
      result.current.setOnline(true);
    });

    expect(result.current.isOnline).toBe(true);
  });

  it('tracks last checked timestamp', () => {
    const { result } = renderHook(() => useConnection());
    const before = Date.now();

    act(() => {
      result.current.setOnline(true);
    });

    expect(result.current.lastChecked).toBeGreaterThanOrEqual(before);
  });
});

describe('useStatus store', () => {
  it('manages health status', () => {
    const { result } = renderHook(() => useStatus());
    const mockHealth = { status: 'ok', services: {}, version: '1.0.0' };

    act(() => {
      result.current.setHealth(mockHealth);
    });

    expect(result.current.health).toEqual(mockHealth);
  });

  it('manages agents status', () => {
    const { result } = renderHook(() => useStatus());
    const mockAgents = {
      agents: {},
      total_agents: 5,
      local_agents: 3,
      remote_agents: 2,
      llm_mode: 'online' as const,
    };

    act(() => {
      result.current.setAgents(mockAgents);
    });

    expect(result.current.agents).toEqual(mockAgents);
  });

  it('manages loading state', () => {
    const { result } = renderHook(() => useStatus());

    act(() => {
      result.current.setLoading(true);
    });

    expect(result.current.isLoading).toBe(true);
  });
});

