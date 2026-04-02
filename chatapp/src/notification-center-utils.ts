function toPositiveInt(value) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

function toTimestampMs(value, fallbackMs) {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
    return Math.floor(value);
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return fallbackMs;
}

function normalizeDecisionSource(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (
    normalized === 'threshold_reached' ||
    normalized === 'vote_timeout' ||
    normalized === 'pending'
  ) {
    return normalized;
  }
  return '-';
}

export function buildNotificationCenterItems(
  { latestJudgeReportEvent = null, latestDrawVoteResolvedEvent = null } = {},
  { nowMs = Date.now() } = {},
) {
  const items = [];

  const judgeSessionId = toPositiveInt(latestJudgeReportEvent?.sessionId);
  if (judgeSessionId) {
    const winner = String(latestJudgeReportEvent?.winner || '').trim().toLowerCase() || '-';
    const reportId = toPositiveInt(latestJudgeReportEvent?.reportId) || judgeSessionId;
    items.push({
      key: `judge:${reportId}`,
      kind: 'judge_report_ready',
      title: 'AI 判决已生成',
      subtitle: `场次 #${judgeSessionId} · winner=${winner}`,
      path: '/judge-report',
      query: { sessionId: String(judgeSessionId) },
      createdAtMs: toTimestampMs(latestJudgeReportEvent?.receivedAt, nowMs),
    });
  }

  const drawSessionId = toPositiveInt(latestDrawVoteResolvedEvent?.sessionId);
  if (drawSessionId) {
    const voteId = toPositiveInt(latestDrawVoteResolvedEvent?.voteId) || drawSessionId;
    const resolution = String(latestDrawVoteResolvedEvent?.resolution || '').trim().toLowerCase() || '-';
    const decisionSource = normalizeDecisionSource(latestDrawVoteResolvedEvent?.decisionSource);
    const rematchSessionId = toPositiveInt(latestDrawVoteResolvedEvent?.rematchSessionId);
    const targetPath = rematchSessionId ? `/debate/sessions/${rematchSessionId}` : `/debate/sessions/${drawSessionId}`;

    items.push({
      key: `draw:${voteId}`,
      kind: 'draw_vote_resolved',
      title: '平局投票已决议',
      subtitle: `场次 #${drawSessionId} · resolution=${resolution} · source=${decisionSource}`,
      path: targetPath,
      query: null,
      createdAtMs: toTimestampMs(
        latestDrawVoteResolvedEvent?.decidedAt || latestDrawVoteResolvedEvent?.receivedAt,
        nowMs,
      ),
    });
  }

  return items.sort((a, b) => b.createdAtMs - a.createdAtMs);
}

export function countNotificationCenterItems(items = []) {
  if (!Array.isArray(items)) {
    return 0;
  }
  return items.length;
}
