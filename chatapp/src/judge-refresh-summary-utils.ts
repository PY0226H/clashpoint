export const ANALYTICS_API_BASE_URL = 'http://localhost:6690/api';

type JudgeRefreshSummaryQuery = {
  hours: number;
  limit: number;
  debateSessionId: number | null;
};

type JudgeRefreshSummaryMetrics = {
  requestTotal: number;
  cacheHitTotal: number;
  cacheMissTotal: number;
  cacheHitRate: number;
  dbQueryTotal: number;
  dbErrorTotal: number;
  avgDbLatencyMs: number;
  lastDbLatencyMs: number;
};

export function clampInt(value: unknown, min: number, max: number, fallback: number): number {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.trunc(n)));
}

export function normalizeJudgeRefreshSummaryQuery(payload: any = {}): JudgeRefreshSummaryQuery {
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

function toNumberOrFallback(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

export function normalizeJudgeRefreshSummaryMetrics(payload: any = {}): JudgeRefreshSummaryMetrics {
  return {
    requestTotal: Math.max(0, toNumberOrFallback(payload.requestTotal, 0)),
    cacheHitTotal: Math.max(0, toNumberOrFallback(payload.cacheHitTotal, 0)),
    cacheMissTotal: Math.max(0, toNumberOrFallback(payload.cacheMissTotal, 0)),
    cacheHitRate: Math.max(0, toNumberOrFallback(payload.cacheHitRate, 0)),
    dbQueryTotal: Math.max(0, toNumberOrFallback(payload.dbQueryTotal, 0)),
    dbErrorTotal: Math.max(0, toNumberOrFallback(payload.dbErrorTotal, 0)),
    avgDbLatencyMs: Math.max(0, toNumberOrFallback(payload.avgDbLatencyMs, 0)),
    lastDbLatencyMs: Math.max(0, toNumberOrFallback(payload.lastDbLatencyMs, 0)),
  };
}
