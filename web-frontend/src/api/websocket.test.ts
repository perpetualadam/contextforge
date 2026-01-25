import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { WebSocketClient, createWebSocketClient } from './websocket';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onclose: ((event: { code: number; reason: string }) => void) | null = null;
  onerror: ((error: Event) => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;

  constructor(public url: string) {
    // Simulate sync connection for easier testing
    Promise.resolve().then(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.();
    });
  }

  send = vi.fn();
  close = vi.fn((code?: number, reason?: string) => {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({ code: code || 1000, reason: reason || '' });
  });
}

// Store original WebSocket
const OriginalWebSocket = global.WebSocket;

describe('WebSocketClient', () => {
  beforeEach(() => {
    // @ts-expect-error - Mock WebSocket
    global.WebSocket = MockWebSocket;
  });

  afterEach(() => {
    global.WebSocket = OriginalWebSocket;
  });

  it('creates a client with default URL', () => {
    const client = createWebSocketClient();
    expect(client).toBeInstanceOf(WebSocketClient);
  });

  it('creates a client with custom URL', () => {
    const client = createWebSocketClient('ws://custom:8080/ws');
    expect(client).toBeInstanceOf(WebSocketClient);
  });

  it('connects to WebSocket server', async () => {
    const client = createWebSocketClient('ws://test:8080/ws');
    const onConnect = vi.fn();

    client.on('connected', onConnect);
    client.connect();

    // Wait for microtask queue to flush
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(onConnect).toHaveBeenCalled();
    expect(client.isConnected).toBe(true);
    expect(client.connectionState).toBe('connected');

    // Clean up
    client.disconnect();
  });

  it('emits disconnected event when connection closes', async () => {
    const client = createWebSocketClient('ws://test:8080/ws');
    const onDisconnect = vi.fn();

    client.on('disconnected', onDisconnect);
    client.connect();

    await new Promise(resolve => setTimeout(resolve, 0));

    client.disconnect();

    expect(onDisconnect).toHaveBeenCalled();
    expect(client.isConnected).toBe(false);
    expect(client.connectionState).toBe('disconnected');
  });

  it('handles incoming messages', async () => {
    const client = createWebSocketClient('ws://test:8080/ws');
    const onAgentStatus = vi.fn();

    client.on('agent_status', onAgentStatus);
    client.connect();

    await new Promise(resolve => setTimeout(resolve, 0));

    // Get the mock socket and simulate a message
    // @ts-expect-error - accessing private property for testing
    const socket = client.socket as MockWebSocket;
    socket.onmessage?.({
      data: JSON.stringify({
        type: 'agent_status',
        data: { agents: {}, total_agents: 0 },
        timestamp: Date.now()
      })
    });

    expect(onAgentStatus).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'agent_status',
        data: { agents: {}, total_agents: 0 }
      })
    );

    client.disconnect();
  });

  it('sends messages when connected', async () => {
    const client = createWebSocketClient('ws://test:8080/ws');
    client.connect();

    await new Promise(resolve => setTimeout(resolve, 0));

    // @ts-expect-error - accessing private property for testing
    const socket = client.socket as MockWebSocket;

    client.send('test', { foo: 'bar' });

    expect(socket.send).toHaveBeenCalledWith(
      expect.stringContaining('"type":"test"')
    );

    client.disconnect();
  });

  it('unsubscribes handlers correctly', async () => {
    const client = createWebSocketClient('ws://test:8080/ws');
    const handler = vi.fn();

    const unsubscribe = client.on('connected', handler);
    unsubscribe();

    client.connect();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(handler).not.toHaveBeenCalled();

    client.disconnect();
  });

  it('calls global handlers for all message types', async () => {
    const client = createWebSocketClient('ws://test:8080/ws');
    const globalHandler = vi.fn();

    client.onAny(globalHandler);
    client.connect();

    await new Promise(resolve => setTimeout(resolve, 0));

    // Should receive 'connected' event
    expect(globalHandler).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'connected' })
    );

    client.disconnect();
  });
});

