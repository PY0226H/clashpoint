const DEFAULT_NOTIFY_BASE = 'http://localhost:6687/events';
const KNOWN_JUDGE_REPORT_STATUS = new Set(['ready', 'pending', 'failed', 'absent']);
const KNOWN_DRAW_VOTE_STATUS = new Set(['open', 'decided', 'expired', 'absent']);

function toWsProtocol(protocol) {
  if (protocol === 'https:') {
    return 'wss:';
  }
  if (protocol === 'http:') {
    return 'ws:';
  }
  if (protocol === 'wss:' || protocol === 'ws:') {
    return protocol;
  }
  return 'ws:';
}

function normalizeNotifyBasePath(pathname) {
  if (!pathname || pathname === '/') {
    return '';
  }
  const trimmed = pathname.endsWith('/') ? pathname.slice(0, -1) : pathname;
  if (trimmed.endsWith('/events')) {
    return trimmed.slice(0, -'/events'.length);
  }
  return trimmed;
}

export function buildDebateRoomWsUrl({ notifyBase, sessionId, notifyTicket }) {
  if (!sessionId) {
    throw new Error('sessionId is required');
  }
  if (!notifyTicket || !String(notifyTicket).trim()) {
    throw new Error('notifyTicket is required');
  }
  const base = String(notifyBase || DEFAULT_NOTIFY_BASE);
  const parsed = new URL(base);
  parsed.protocol = toWsProtocol(parsed.protocol);
  const basePath = normalizeNotifyBasePath(parsed.pathname);
  parsed.pathname = `${basePath}/ws/debate/${sessionId}`;
  parsed.search = '';
  parsed.searchParams.set('token', String(notifyTicket).trim());
  return parsed.toString();
}

export function parseDebateRoomWsMessage(raw) {
  if (typeof raw !== 'string' || raw.trim() === '') {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return null;
    }
    const type = typeof parsed.type === 'string' ? parsed.type : '';
    if (!type) {
      return null;
    }
    return parsed;
  } catch (_) {
    return null;
  }
}

export function extractDebateRoomEvent(message, expectedEventName = '') {
  if (!message || message.type !== 'roomEvent') {
    return null;
  }
  if (typeof message.eventName !== 'string' || !message.eventName) {
    return null;
  }
  if (expectedEventName && message.eventName !== expectedEventName) {
    return null;
  }
  const payload = message.payload;
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return null;
  }
  return payload;
}

export function normalizeJudgeReportStatus(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (!KNOWN_JUDGE_REPORT_STATUS.has(normalized)) {
    return 'absent';
  }
  return normalized;
}

export function shouldPollJudgeReportStatus(status) {
  return normalizeJudgeReportStatus(status) === 'pending';
}

export function normalizeDrawVoteStatus(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (!KNOWN_DRAW_VOTE_STATUS.has(normalized)) {
    return 'absent';
  }
  return normalized;
}

export function canSubmitDrawVote(vote, nowMs = Date.now()) {
  if (!vote) {
    return false;
  }
  if (normalizeDrawVoteStatus(vote.status) !== 'open') {
    return false;
  }
  const endsAtMs = new Date(vote.votingEndsAt || '').getTime();
  if (!Number.isFinite(endsAtMs)) {
    return true;
  }
  return nowMs < endsAtMs;
}

export function normalizeDebateRoomMessage(raw) {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const id = raw.id ?? raw.messageId;
  if (!id) {
    return null;
  }
  return {
    id,
    sessionId: raw.sessionId,
    userId: raw.userId,
    side: raw.side || 'unknown',
    content: raw.content || '',
    createdAt: raw.createdAt || new Date().toISOString(),
  };
}

export function mergeDebateRoomMessages(currentMessages = [], incomingMessages = []) {
  const map = new Map();
  for (const item of currentMessages) {
    const normalized = normalizeDebateRoomMessage(item);
    if (!normalized) {
      continue;
    }
    map.set(String(normalized.id), normalized);
  }
  for (const item of incomingMessages) {
    const normalized = normalizeDebateRoomMessage(item);
    if (!normalized) {
      continue;
    }
    map.set(String(normalized.id), normalized);
  }
  return Array.from(map.values()).sort((a, b) => Number(a.id) - Number(b.id));
}

export function getOldestDebateMessageId(messages = []) {
  if (!Array.isArray(messages) || messages.length === 0) {
    return null;
  }
  let oldest = null;
  for (const item of messages) {
    const id = Number(item?.id);
    if (!Number.isFinite(id) || id <= 0) {
      continue;
    }
    if (oldest == null || id < oldest) {
      oldest = id;
    }
  }
  return oldest;
}
