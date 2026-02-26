export function formatMessageDateForStore(timestamp) {
  const date = new Date(timestamp);
  const now = new Date();
  const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
  const timeString = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  if (diffDays === 0) {
    return timeString;
  }
  if (diffDays < 30) {
    return `${timeString}, ${diffDays} ${diffDays === 1 ? 'day' : 'days'} ago`;
  }
  return `${timeString}, ${date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}`;
}

export function toDisplayMessage(message) {
  if (!message) {
    return message;
  }
  return {
    ...message,
    formattedCreatedAt: formatMessageDateForStore(message.createdAt),
  };
}

export function upsertMessage(messages = [], rawMessage) {
  const next = Array.isArray(messages) ? [...messages] : [];
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
