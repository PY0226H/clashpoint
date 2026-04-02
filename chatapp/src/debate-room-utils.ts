const DEFAULT_NOTIFY_BASE = 'http://localhost:6687/events';
const KNOWN_JUDGE_REPORT_STATUS = new Set(['ready', 'pending', 'failed', 'absent']);
const KNOWN_DRAW_VOTE_STATUS = new Set(['open', 'decided', 'expired', 'absent']);
const DEFAULT_WS_RECONNECT_BASE_MS = 1200;
const DEFAULT_WS_RECONNECT_MAX_MS = 15000;
const DEFAULT_WS_RECONNECT_JITTER_RATIO = 0.2;

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

export function buildDebateRoomWsUrl({ notifyBase, sessionId, notifyTicket, lastAckSeq = null }) {
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
  const normalizedLastAckSeq = Number(lastAckSeq);
  if (lastAckSeq != null && Number.isFinite(normalizedLastAckSeq) && normalizedLastAckSeq >= 0) {
    parsed.searchParams.set('lastAckSeq', String(Math.floor(normalizedLastAckSeq)));
  }
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

export function toNonNegativeInt(value, fallback = null) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return fallback;
  }
  return Math.floor(parsed);
}

export function advanceDebateAckSeq(currentSeq, nextSeq, { force = false } = {}) {
  const current = toNonNegativeInt(currentSeq, 0);
  const next = toNonNegativeInt(nextSeq, null);
  if (next == null) {
    return current;
  }
  if (force) {
    return next;
  }
  return next > current ? next : current;
}

export function buildDebateRoomAckMessage(eventSeq) {
  const normalized = toNonNegativeInt(eventSeq, null);
  if (normalized == null) {
    return null;
  }
  return JSON.stringify({
    type: 'ack',
    eventSeq: normalized,
  });
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

export function shouldShowManualJudgeTrigger(status) {
  return normalizeJudgeReportStatus(status) === 'failed';
}

export function judgeAutomationHintText(status) {
  const normalized = normalizeJudgeReportStatus(status);
  if (normalized === 'ready') {
    return '系统已自动完成本场判决。';
  }
  if (normalized === 'pending') {
    return '系统已自动触发裁判，正在生成判决结果。';
  }
  if (normalized === 'failed') {
    return '自动触发或执行失败，可使用兜底重试。';
  }
  return '辩论结束后系统会自动触发裁判，无需手动发起。';
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

export function getDrawVoteRemainingMs(vote, nowMs = Date.now()) {
  if (!vote) {
    return null;
  }
  const endsAtMs = new Date(vote.votingEndsAt || '').getTime();
  if (!Number.isFinite(endsAtMs)) {
    return null;
  }
  return Math.max(0, endsAtMs - nowMs);
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

export function computeWsReconnectDelayMs(
  attempt,
  {
    baseMs = DEFAULT_WS_RECONNECT_BASE_MS,
    maxMs = DEFAULT_WS_RECONNECT_MAX_MS,
    jitterRatio = DEFAULT_WS_RECONNECT_JITTER_RATIO,
    randomValue = Math.random(),
  } = {},
) {
  const normalizedBaseMs = Math.max(1, Number(baseMs) || DEFAULT_WS_RECONNECT_BASE_MS);
  const normalizedMaxMs = Math.max(normalizedBaseMs, Number(maxMs) || DEFAULT_WS_RECONNECT_MAX_MS);
  const normalizedAttempt = Math.max(1, Number(attempt) || 1);
  const normalizedJitterRatio = Math.max(0, Number(jitterRatio) || 0);

  const expDelay = Math.min(
    normalizedMaxMs,
    normalizedBaseMs * Math.pow(2, normalizedAttempt - 1),
  );
  const jitterWindow = Math.floor(expDelay * normalizedJitterRatio);
  if (jitterWindow <= 0) {
    return Math.floor(expDelay);
  }

  const random = Math.max(0, Math.min(1, Number(randomValue) || 0));
  const offset = Math.floor(random * (jitterWindow * 2 + 1)) - jitterWindow;
  return Math.max(
    normalizedBaseMs,
    Math.min(normalizedMaxMs, Math.floor(expDelay + offset)),
  );
}
