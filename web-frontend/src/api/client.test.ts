import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import apiClient from './client';

describe('ApiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as ReturnType<typeof vi.fn>).mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('getHealth', () => {
    it('returns health status on success', async () => {
      const mockHealth = { status: 'ok', services: {}, version: '1.0.0' };
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockHealth),
      });

      const result = await apiClient.getHealth();
      expect(result).toEqual(mockHealth);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/health'),
        expect.objectContaining({
          headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        })
      );
    });

    it('throws error on failure', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: () => Promise.resolve({ message: 'Server error' }),
      });

      await expect(apiClient.getHealth()).rejects.toMatchObject({ status: 500 });
    });
  });

  describe('query', () => {
    it('sends query request correctly', async () => {
      const mockResponse = {
        answer: 'Test answer',
        contexts: [{ source: 'test.ts', content: 'code', line_start: 1, line_end: 10, score: 0.9 }],
        latency_ms: 100,
      };
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiClient.query({ query: 'test query' });
      expect(result).toEqual(mockResponse);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/query'),
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });

  describe('chat', () => {
    it('sends chat request with messages', async () => {
      const mockResponse = {
        response: 'Bot response',
        conversation_id: 'conv_123',
        contexts: [],
      };
      const request = {
        messages: [
          { role: 'user' as const, content: 'Hello' },
          { role: 'assistant' as const, content: 'Hi there!' },
        ],
      };

      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiClient.chat(request);
      expect(result).toEqual(mockResponse);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/chat'),
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });

  describe('ingest', () => {
    it('sends ingest request', async () => {
      const mockResponse = { status: 'completed', files_indexed: 10, chunks_created: 100, duration_ms: 500 };
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiClient.ingest({ path: '/path/to/repo' });
      expect(result).toEqual(mockResponse);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/ingest'),
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });

  describe('connection listeners', () => {
    it('notifies listeners of connection changes', () => {
      const listener = vi.fn();
      const unsubscribe = apiClient.onConnectionChange(listener);

      expect(typeof unsubscribe).toBe('function');
      unsubscribe();
    });
  });

  describe('setApiKey', () => {
    it('stores API key', () => {
      apiClient.setApiKey('test-api-key');
      expect(apiClient.getApiKey()).toBe('test-api-key');

      // Clean up
      apiClient.setApiKey(null);
    });
  });

  describe('isConnected', () => {
    it('returns connection status', () => {
      const status = apiClient.isConnected();
      expect(typeof status).toBe('boolean');
    });
  });
});

