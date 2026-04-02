const STATUS_ORDER = ['scheduled', 'open', 'running', 'judging', 'closed', 'canceled'];
const JOINABLE_STATUS = new Set(['open', 'running']);

export function normalizeOpsSessionStatus(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (STATUS_ORDER.includes(normalized)) {
    return normalized;
  }
  return 'scheduled';
}

export function nextQuickStatusActions(currentStatus) {
  const status = normalizeOpsSessionStatus(currentStatus);
  if (status === 'scheduled') {
    return ['open', 'canceled'];
  }
  if (status === 'open') {
    return ['running', 'canceled'];
  }
  if (status === 'running') {
    return ['judging', 'closed', 'canceled'];
  }
  if (status === 'judging') {
    return ['closed', 'canceled'];
  }
  return [];
}

function toTimeMs(value) {
  const ms = Date.parse(String(value || '').trim());
  return Number.isFinite(ms) ? ms : null;
}

function resolveSessionTime(session, camelKey, snakeKey) {
  return (
    String(session?.[camelKey] || '').trim() ||
    String(session?.[snakeKey] || '').trim()
  );
}

export function getOpsSessionWindowState(session, nowMs = Date.now()) {
  const scheduledStartAt = resolveSessionTime(
    session,
    'scheduledStartAt',
    'scheduled_start_at',
  );
  const endAt = resolveSessionTime(session, 'endAt', 'end_at');
  const startMs = toTimeMs(scheduledStartAt);
  const endMs = toTimeMs(endAt);
  if (startMs == null || endMs == null || endMs <= startMs) {
    return 'invalid';
  }
  if (nowMs < startMs) {
    return 'upcoming';
  }
  if (nowMs >= endMs) {
    return 'expired';
  }
  return 'active';
}

export function getOpsSessionJoinability(session, nowMs = Date.now()) {
  if (session?.joinable) {
    return {
      joinable: true,
      code: 'ready',
      text: '可参与（joinable）',
    };
  }

  const status = normalizeOpsSessionStatus(session?.status);
  const windowState = getOpsSessionWindowState(session, nowMs);
  if (windowState === 'invalid') {
    return {
      joinable: false,
      code: 'invalid_schedule',
      text: '时间窗口配置无效',
    };
  }
  if (windowState === 'upcoming') {
    return {
      joinable: false,
      code: 'not_started',
      text: '未到开始时间',
    };
  }
  if (windowState === 'expired') {
    return {
      joinable: false,
      code: 'ended',
      text: '已超过结束时间',
    };
  }
  if (!JOINABLE_STATUS.has(status)) {
    return {
      joinable: false,
      code: 'status_blocked',
      text: `状态 ${status} 不允许加入`,
    };
  }
  return {
    joinable: false,
    code: 'unavailable',
    text: '当前不可参与',
  };
}

export function getOpsSessionRecommendedAction(session, nowMs = Date.now()) {
  const status = normalizeOpsSessionStatus(session?.status);
  const windowState = getOpsSessionWindowState(session, nowMs);
  if (windowState === 'invalid') {
    return {
      targetStatus: null,
      label: '修正时间窗口',
      reason: '开始/结束时间配置无效',
    };
  }
  if (windowState === 'upcoming' && (status === 'open' || status === 'running')) {
    return {
      targetStatus: 'scheduled',
      label: '设为 scheduled',
      reason: '未到开始时间，建议保持待开启',
    };
  }
  if (windowState === 'active' && status === 'scheduled') {
    return {
      targetStatus: 'open',
      label: '设为 open',
      reason: '已到开始时间，建议开放加入',
    };
  }
  if (windowState === 'expired' && (status === 'open' || status === 'running')) {
    return {
      targetStatus: 'judging',
      label: '设为 judging',
      reason: '已过结束时间，建议进入裁决',
    };
  }
  return null;
}

export function buildQuickUpdateSessionPayload(session, nextStatus) {
  const id = Number(session?.id);
  if (!Number.isFinite(id) || id <= 0) {
    throw new Error('invalid session id');
  }

  const targetStatus = normalizeOpsSessionStatus(nextStatus);
  const maxParticipantsPerSide = Number(session?.maxParticipantsPerSide);
  if (!Number.isFinite(maxParticipantsPerSide) || maxParticipantsPerSide <= 0) {
    throw new Error('invalid maxParticipantsPerSide');
  }

  const scheduledStartAt = String(session?.scheduledStartAt || '').trim();
  const endAt = String(session?.endAt || '').trim();
  if (!scheduledStartAt || !endAt) {
    throw new Error('missing session schedule');
  }

  return {
    sessionId: id,
    status: targetStatus,
    scheduledStartAt,
    endAt,
    maxParticipantsPerSide,
  };
}
