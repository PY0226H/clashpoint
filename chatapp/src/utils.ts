import { invoke } from '@tauri-apps/api/core';

const URL_BASE = 'http://localhost:6688/api';
const SSE_URL = 'http://localhost:6687/events';

type AppRuntimeConfig = {
  server?: {
    chat?: string;
    notification?: string;
  };
};

type StoreLike = {
  commit: (type: string, payload?: unknown) => void;
};

type InitSseHandlers = {
  onOpen?: ((event: Event) => void) | null;
  onError?: ((error: unknown) => void) | null;
};

let config: AppRuntimeConfig | null = null;
try {
  if (invoke) {
    invoke('get_config').then((c: unknown) => {
      config = (c as AppRuntimeConfig) || null;
      console.log('config:', c);
    });
  }
} catch (error) {
  console.warn('failed to get config: fallback');
}

const getUrlBase = (): string => {
  if (config && config.server.chat) {
    return config.server.chat;
  }
  return URL_BASE;
};

const getNotifyBase = (): string => {
  if (config && config.server.notification) {
    return config.server.notification;
  }
  return SSE_URL;
};

const initSSE = (store: StoreLike, notifyTicket: string, handlers: InitSseHandlers = {}) => {
  const {
    onOpen = null,
    onError = null,
  } = handlers;
  const sseBase = getNotifyBase();
  const url = `${sseBase}?token=${notifyTicket}`;
  const sse = new EventSource(url);

  sse.onopen = (event) => {
    console.log('EventSource connected');
    if (onOpen) {
      onOpen(event);
    }
  };

  sse.addEventListener('NewMessage', (e) => {
    const event = e as MessageEvent<string>;
    const data = JSON.parse(event.data || '{}') as Record<string, unknown>;
    console.log('message:', e.data);
    delete data.event;
    store.commit('addMessage', { channelId: data.chatId, message: data });
  });

  sse.onmessage = (event) => {
    console.log('got event:', event);
    // const data = JSON.parse(event.data);
    // commit('addMessage', data);
  };

  sse.onerror = (error) => {
    console.error('EventSource failed:', error);
    sse.close();
    if (onError) {
      onError(error);
    }
  };

  return sse;
};

export {
  getUrlBase,
  getNotifyBase,
  initSSE,
};

export function formatMessageDate(timestamp: unknown): string {
  const date = timestamp instanceof Date ? timestamp : new Date((timestamp as string | number) ?? '');
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  const timeString = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  if (diffDays === 0) {
    return timeString;
  } else if (diffDays < 30) {
    return `${timeString}, ${diffDays} ${diffDays === 1 ? 'day' : 'days'} ago`;
  } else {
    return `${timeString}, ${date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}`;
  }
}
