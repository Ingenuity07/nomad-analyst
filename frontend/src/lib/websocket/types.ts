export type ConnectionStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED' | 'RECONNECTING';

export interface WebSocketMessage<T = any> {
  topic: string;
  action?: 'subscribe' | 'unsubscribe' | 'update';
  data?: T;
  timestamp?: string;
}

export type MessageHandler<T = any> = (message: WebSocketMessage<T>) => void;
