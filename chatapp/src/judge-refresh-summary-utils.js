export const ANALYTICS_API_BASE_URL = 'http://localhost:6690/api';

export function clampInt(value, min, max, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.trunc(n)));
}

export function normalizeJudgeRefreshSummaryQuery(payload = {}) {
  const hours = clampInt(payload.hours, 1, 168, 24);
  const limit = clampInt(payload.limit, 1, 200, 20);
  let debateSessionId = null;
  if (payload.debateSessionId != null && payload.debateSessionId !== '') {
    const session = Number(payload.debateSessionId);
    if (Number.isFinite(session)) {
      const normalized = Math.trunc(session);
      if (normalized >= 1 && normalized <= Number.MAX_SAFE_INTEGER) {
        debateSessionId = normalized;
      }
    }
  }
  return {
    hours,
    limit,
    debateSessionId,
  };
}
