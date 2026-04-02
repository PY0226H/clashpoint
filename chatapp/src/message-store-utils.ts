type StoreMessage = {
  id?: unknown;
  createdAt?: unknown;
  [key: string]: unknown;
};

export function formatMessageDateForStore(timestamp: unknown): string {
  const date = timestamp instanceof Date ? timestamp : new Date((timestamp as string | number) ?? '');
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  const timeString = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  if (diffDays === 0) {
    return timeString;
  }
  if (diffDays < 30) {
    return `${timeString}, ${diffDays} ${diffDays === 1 ? 'day' : 'days'} ago`;
  }
  return `${timeString}, ${date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}`;
}

export function toDisplayMessage(
  message: StoreMessage | null | undefined,
): StoreMessage | null | undefined {
  if (!message) {
    return message;
  }
  return {
    ...message,
    formattedCreatedAt: formatMessageDateForStore(message.createdAt),
  };
}

export function upsertMessage(
  messages: StoreMessage[] = [],
  rawMessage: StoreMessage | null | undefined,
): StoreMessage[] {
  const next: StoreMessage[] = Array.isArray(messages) ? [...messages] : [];
  const message = toDisplayMessage(rawMessage);
  if (!message) {
    return next;
  }

  const idx = next.findIndex((item) => item && item.id === message.id);
  if (idx >= 0) {
    next[idx] = { ...next[idx], ...message };
    return next;
  }

  next.push(message);
  return next;
}
