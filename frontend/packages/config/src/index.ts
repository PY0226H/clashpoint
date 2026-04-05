export type RuntimeConfig = {
  server: {
    chat: string;
    notification: string;
  };
};

const DEFAULT_CONFIG: RuntimeConfig = {
  server: {
    chat: "http://localhost:6688/api",
    notification: "http://localhost:6687/events"
  }
};

function trimSlash(value: string): string {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

export function getRuntimeConfig(): RuntimeConfig {
  const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
  const chat = env.VITE_CHAT_API_BASE
    ? trimSlash(env.VITE_CHAT_API_BASE)
    : DEFAULT_CONFIG.server.chat;
  const notification = env.VITE_NOTIFY_EVENTS_BASE
    ? trimSlash(env.VITE_NOTIFY_EVENTS_BASE)
    : DEFAULT_CONFIG.server.notification;

  return {
    server: {
      chat,
      notification
    }
  };
}
