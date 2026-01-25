import { useEffect, useCallback, useState, useRef } from 'react';
import { 
  getWebSocketClient, 
  WebSocketClient, 
  WebSocketEventType, 
  WebSocketMessage 
} from '../api/websocket';

interface UseWebSocketOptions {
  autoConnect?: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: unknown) => void;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  connectionState: 'connecting' | 'connected' | 'disconnected';
  connect: () => void;
  disconnect: () => void;
  send: <T = unknown>(type: string, data: T) => void;
  subscribe: <T = unknown>(type: WebSocketEventType, handler: (message: WebSocketMessage<T>) => void) => () => void;
}

/**
 * React hook for WebSocket connection management
 */
export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const { autoConnect = true, onConnect, onDisconnect, onError } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const clientRef = useRef<WebSocketClient | null>(null);

  useEffect(() => {
    const client = getWebSocketClient();
    clientRef.current = client;

    // Set up connection status handlers
    const unsubConnect = client.on('connected', () => {
      setIsConnected(true);
      setConnectionState('connected');
      onConnect?.();
    });

    const unsubDisconnect = client.on('disconnected', () => {
      setIsConnected(false);
      setConnectionState('disconnected');
      onDisconnect?.();
    });

    const unsubError = client.on('error', (msg) => {
      onError?.(msg.data);
    });

    // Auto-connect if enabled
    if (autoConnect) {
      setConnectionState('connecting');
      client.connect();
    }

    return () => {
      unsubConnect();
      unsubDisconnect();
      unsubError();
    };
  }, [autoConnect, onConnect, onDisconnect, onError]);

  const connect = useCallback(() => {
    if (clientRef.current) {
      setConnectionState('connecting');
      clientRef.current.connect();
    }
  }, []);

  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
    }
  }, []);

  const send = useCallback(<T = unknown>(type: string, data: T) => {
    if (clientRef.current) {
      clientRef.current.send(type, data);
    }
  }, []);

  const subscribe = useCallback(<T = unknown>(
    type: WebSocketEventType, 
    handler: (message: WebSocketMessage<T>) => void
  ) => {
    if (clientRef.current) {
      return clientRef.current.on(type, handler);
    }
    return () => {};
  }, []);

  return {
    isConnected,
    connectionState,
    connect,
    disconnect,
    send,
    subscribe,
  };
}

/**
 * Hook for subscribing to specific WebSocket event types
 */
export function useWebSocketEvent<T = unknown>(
  type: WebSocketEventType,
  handler: (data: T) => void,
  deps: React.DependencyList = []
): void {
  const { subscribe } = useWebSocket({ autoConnect: false });

  useEffect(() => {
    const unsubscribe = subscribe<T>(type, (message) => {
      handler(message.data);
    });

    return unsubscribe;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, subscribe, ...deps]);
}

