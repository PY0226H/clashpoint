export function parseSseAppEventData(raw) {
  if (typeof raw !== 'string' || raw.trim() === '') {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return null;
    }
    const event = typeof parsed.event === 'string' ? parsed.event : '';
    const payload = { ...parsed };
    delete payload.event;
    return { event, payload };
  } catch (_) {
    return null;
  }
}

export function parseNamedSseEventData(raw, expectedEvent) {
  const parsed = parseSseAppEventData(raw);
  if (!parsed) {
    return null;
  }
  if (parsed.event !== expectedEvent) {
    return null;
  }
  return parsed.payload;
}
