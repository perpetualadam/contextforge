/**
 * WebSocket client for real-time updates from ContextForge backend
 */

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws';

export type WebSocketEventType =
  | 'connected'
  | 'disconnected'
  | 'agent_status'
  | 'health_update'
  | 'chat_response'
  | 'chat_chunk'
  | 'ingest_progress'
  | 'error';

export interface WebSocketMessage<T = unknown> {
  type: WebSocketEventType;
  data: T;
  timestamp: number;
}

export interface AgentStatusData {
  agents: Record<string, { status: 'running' | 'stopped' | 'error'; last_heartbeat: string }>;
  total_agents: number;
}

export interface ChatChunkData {
  conversation_id: string;
  chunk: string;
  done: boolean;
}

export interface IngestProgressData {
  job_id: string;
  files_processed: number;
  total_files: number;
  current_file?: string;
  status: 'running' | 'completed' | 'failed';
}

type MessageHandler<T = unknown> = (message: WebSocketMessage<T>) => void;

class WebSocketClient {
  private socket: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private handlers: Map<WebSocketEventType, Set<MessageHandler>> = new Map();
  private globalHandlers: Set<MessageHandler> = new Set();
  private url: string;
  private shouldReconnect = true;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;

  constructor(url: string = WS_BASE_URL) {
    this.url = url;
  }

  connect(): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      this.socket = new WebSocket(this.url);
      this.setupEventListeners();
    } catch (error) {
      console.error('[WebSocket] Connection failed:', error);
      this.scheduleReconnect();
    }
  }

  private setupEventListeners(): void {
    if (!this.socket) return;

    this.socket.onopen = () => {
      console.log('[WebSocket] Connected');
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      this.emit({ type: 'connected', data: null, timestamp: Date.now() });
    };

    this.socket.onclose = (event) => {
      console.log('[WebSocket] Disconnected:', event.code, event.reason);
      this.stopHeartbeat();
      this.emit({ type: 'disconnected', data: { code: event.code, reason: event.reason }, timestamp: Date.now() });

      if (this.shouldReconnect && event.code !== 1000) {
        this.scheduleReconnect();
      }
    };

    this.socket.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
      this.emit({ type: 'error', data: error, timestamp: Date.now() });
    };

    this.socket.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.emit(message);
      } catch (error) {
        console.error('[WebSocket] Failed to parse message:', error);
      }
    };
  }

  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnection attempts reached');
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);

    setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  private emit(message: WebSocketMessage): void {
    // Call type-specific handlers
    const handlers = this.handlers.get(message.type);
    if (handlers) {
      handlers.forEach(handler => handler(message));
    }

    // Call global handlers
    this.globalHandlers.forEach(handler => handler(message));
  }

  on<T = unknown>(type: WebSocketEventType, handler: MessageHandler<T>): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler as MessageHandler);

    return () => {
      this.handlers.get(type)?.delete(handler as MessageHandler);
    };
  }

  onAny(handler: MessageHandler): () => void {
    this.globalHandlers.add(handler);
    return () => {
      this.globalHandlers.delete(handler);
    };
  }

  send<T = unknown>(type: string, data: T): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type, data, timestamp: Date.now() }));
    } else {
      console.warn('[WebSocket] Cannot send message, socket not connected');
    }
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this.stopHeartbeat();
    if (this.socket) {
      this.socket.close(1000, 'Client disconnect');
      this.socket = null;
    }
  }

  get isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  get connectionState(): 'connecting' | 'connected' | 'disconnected' {
    if (!this.socket) return 'disconnected';
    switch (this.socket.readyState) {
      case WebSocket.CONNECTING: return 'connecting';
      case WebSocket.OPEN: return 'connected';
      default: return 'disconnected';
    }
  }
}

// Singleton instance
let wsClient: WebSocketClient | null = null;

export function getWebSocketClient(): WebSocketClient {
  if (!wsClient) {
    wsClient = new WebSocketClient();
  }
  return wsClient;
}

export function createWebSocketClient(url?: string): WebSocketClient {
  return new WebSocketClient(url);
}

export { WebSocketClient };
