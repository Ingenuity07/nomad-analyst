import { useEffect, useState } from 'react';
import { wsClient } from '@/lib/websocket/client';
import { ConnectionStatus, MessageHandler } from '@/lib/websocket/types';

export function useWebSocket(topic?: string, onMessage?: MessageHandler) {
  const [status, setStatus] = useState<ConnectionStatus>(wsClient.getStatus());

  useEffect(() => {
    const unsubStatus = wsClient.onStatusChange(setStatus);
    return unsubStatus;
  }, []);

  useEffect(() => {
    if (!topic || !onMessage) return;
    const unsubTopic = wsClient.subscribe(topic, onMessage);
    return unsubTopic;
  }, [topic, onMessage]);

  return {
    status,
    isConnected: status === 'CONNECTED',
    send: wsClient.send.bind(wsClient),
    connect: wsClient.connect.bind(wsClient),
    disconnect: wsClient.disconnect.bind(wsClient),
  };
}
