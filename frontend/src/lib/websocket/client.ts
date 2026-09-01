import { ConnectionStatus, MessageHandler, WebSocketMessage } from './types';

export class MarketWebSocketClient {
  private url: string;
  private ws: WebSocket | null = null;
  private status: ConnectionStatus = 'DISCONNECTED';
  private subscriptions: Set<string> = new Set();
  private handlers: Map<string, Set<MessageHandler>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectTimer: any = null;
  private statusListeners: Set<(status: ConnectionStatus) => void> = new Set();

  constructor(url?: string) {
    const defaultWsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/market/`;
    this.url = url || (import.meta.env.VITE_WS_URL || defaultWsUrl);
  }

  public connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.setStatus('CONNECTING');
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.setStatus('CONNECTED');
        this.reconnectAttempts = 0;
        this.resubscribe();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.dispatchMessage(message);
        } catch {
          // Ignore invalid non-JSON messages
        }
      };

      this.ws.onclose = () => {
        this.setStatus('DISCONNECTED');
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.setStatus('DISCONNECTED');
      };
    } catch {
      this.setStatus('DISCONNECTED');
      this.scheduleReconnect();
    }
  }

  public disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('DISCONNECTED');
  }

  public subscribe(topic: string, handler: MessageHandler): () => void {
    this.subscriptions.add(topic);
    if (!this.handlers.has(topic)) {
      this.handlers.set(topic, new Set());
    }
    this.handlers.get(topic)!.add(handler);

    if (this.status === 'CONNECTED' && this.ws) {
      this.send({ topic, action: 'subscribe' });
    }

    return () => {
      const topicHandlers = this.handlers.get(topic);
      if (topicHandlers) {
        topicHandlers.delete(handler);
        if (topicHandlers.size === 0) {
          this.handlers.delete(topic);
          this.subscriptions.delete(topic);
          if (this.status === 'CONNECTED' && this.ws) {
            this.send({ topic, action: 'unsubscribe' });
          }
        }
      }
    };
  }

  public send(message: WebSocketMessage): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  public onStatusChange(listener: (status: ConnectionStatus) => void): () => void {
    this.statusListeners.add(listener);
    listener(this.status);
    return () => this.statusListeners.delete(listener);
  }

  public getStatus(): ConnectionStatus {
    return this.status;
  }

  private setStatus(status: ConnectionStatus) {
    this.status = status;
    this.statusListeners.forEach((l) => l(status));
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
    this.reconnectAttempts++;
    this.setStatus('RECONNECTING');
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  private resubscribe() {
    this.subscriptions.forEach((topic) => {
      this.send({ topic, action: 'subscribe' });
    });
  }

  private dispatchMessage(message: WebSocketMessage) {
    const topicHandlers = this.handlers.get(message.topic);
    if (topicHandlers) {
      topicHandlers.forEach((handler) => handler(message));
    }
  }
}

export const wsClient = new MarketWebSocketClient();
