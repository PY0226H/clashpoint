import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  appendObservabilityAnomalyTrendSnapshot,
  buildObservabilitySliSnapshot,
  buildObservabilityAnomalyCodeStats,
  buildObservabilityAnomalyStateKey,
  DEFAULT_OBSERVABILITY_SLO_TARGETS,
  DEFAULT_OBSERVABILITY_THRESHOLDS,
  buildJudgeObservabilityAnomalies,
  normalizeObservabilitySessionId,
  normalizeObservabilityAnomalyStateMap,
  normalizeObservabilityAnomalyTrendHistory,
  normalizeObservabilitySloTargets,
  normalizeObservabilityThresholds,
  projectObservabilityAnomalies,
  summarizeObservabilityAnomalyTrend,
} from './judge-observability-utils';

test('normalizeObservabilitySessionId should normalize valid id', () => {
  assert.equal(normalizeObservabilitySessionId('42'), 42);
  assert.equal(normalizeObservabilitySessionId(0), 0);
  assert.equal(normalizeObservabilitySessionId('x'), 0);
});

test('buildJudgeObservabilityAnomalies should report summary empty', () => {
  const ret = buildJudgeObservabilityAnomalies({ rows: [], metrics: {} });
  assert.equal(ret.some((item) => item.code === 'summary_empty'), true);
  const anomaly = ret.find((item) => item.code === 'summary_empty');
  assert.equal(anomaly.action, 'refresh_summary');
});

test('buildJudgeObservabilityAnomalies should report low success and retries', () => {
  const ret = buildJudgeObservabilityAnomalies({
    rows: [
      {
        debateSessionId: '8',
        sourceEventType: 'DebateJudgeReportReady',
        totalRuns: 12,
        successRate: 66.5,
        avgRetryCount: 1.7,
        avgCoalescedEvents: 2.6,
      },
    ],
    metrics: {
      requestTotal: 50,
      cacheHitRate: 15,
      dbErrorTotal: 3,
      avgDbLatencyMs: 1550,
    },
  });

  const codes = ret.map((item) => item.code);
  assert.equal(codes.includes('low_success_rate'), true);
  assert.equal(codes.includes('high_retry'), true);
  assert.equal(codes.includes('high_coalesced'), true);
  assert.equal(codes.includes('db_errors'), true);
  assert.equal(codes.includes('high_db_latency'), true);
  assert.equal(codes.includes('low_cache_hit_rate'), true);
  const lowSuccess = ret.find((item) => item.code === 'low_success_rate');
  assert.deepEqual(lowSuccess.sessionIds, [8]);
  assert.equal(lowSuccess.action, 'review_sessions');
});

test('buildJudgeObservabilityAnomalies should return empty for healthy rows', () => {
  const ret = buildJudgeObservabilityAnomalies({
    rows: [
      {
        debateSessionId: '100',
        sourceEventType: 'DebateJudgeReportReady',
        totalRuns: 12,
        successRate: 99.2,
        avgRetryCount: 0.1,
        avgCoalescedEvents: 0.3,
      },
    ],
    metrics: {
      requestTotal: 100,
      cacheHitRate: 90,
      dbErrorTotal: 0,
      avgDbLatencyMs: 30,
    },
  });
  assert.deepEqual(ret, []);
});

test('normalizeObservabilityThresholds should fallback and clamp', () => {
  const ret = normalizeObservabilityThresholds({
    lowSuccessRateThreshold: 0,
    highRetryThreshold: 'x',
    highCoalescedThreshold: 99,
    highDbLatencyThresholdMs: -10,
    lowCacheHitRateThreshold: 1000,
    minRequestForCacheHitCheck: 0,
  });
  assert.deepEqual(ret, {
    lowSuccessRateThreshold: 1,
    highRetryThreshold: DEFAULT_OBSERVABILITY_THRESHOLDS.highRetryThreshold,
    highCoalescedThreshold: 20,
    highDbLatencyThresholdMs: 1,
    lowCacheHitRateThreshold: 99.99,
    minRequestForCacheHitCheck: 1,
  });
});

test('buildObservabilityAnomalyStateKey should include sorted session ids', () => {
  const key = buildObservabilityAnomalyStateKey({
    code: 'low_success_rate',
    sessionIds: ['3', '1', 'x', 3],
  });
  assert.equal(key, 'low_success_rate:1,3');
  assert.equal(
    buildObservabilityAnomalyStateKey({ code: 'summary_empty', sessionIds: [] }),
    'summary_empty',
  );
});

test('normalizeObservabilityAnomalyStateMap should drop expired suppression', () => {
  const now = 1_000_000;
  const ret = normalizeObservabilityAnomalyStateMap({
    keep_ack: {
      acknowledgedAtMs: now - 10,
      suppressUntilMs: now - 1,
    },
    keep_suppress: {
      suppressUntilMs: now + 1000,
    },
    drop_empty: {
      suppressUntilMs: now - 1,
    },
  }, now);
  assert.deepEqual(ret, {
    keep_ack: {
      acknowledgedAtMs: now - 10,
      suppressUntilMs: 0,
    },
    keep_suppress: {
      acknowledgedAtMs: 0,
      suppressUntilMs: now + 1000,
    },
  });
});

test('projectObservabilityAnomalies should filter suppressed anomalies', () => {
  const now = 2_000_000;
  const anomalies = [
    { code: 'db_errors', text: 'x', action: 'refresh_metrics', sessionIds: [] },
    { code: 'low_success_rate', text: 'y', action: 'review_sessions', sessionIds: [12] },
  ];
  const state = {
    db_errors: { suppressUntilMs: now + 10_000 },
    'low_success_rate:12': { acknowledgedAtMs: now - 5_000 },
  };
  const ret = projectObservabilityAnomalies(anomalies, state, now);
  assert.equal(ret.suppressedCount, 1);
  assert.equal(ret.all.length, 2);
  assert.equal(ret.visible.length, 1);
  assert.equal(ret.visible[0].code, 'low_success_rate');
  assert.equal(ret.visible[0].acknowledgedAtMs, now - 5_000);
});

test('buildObservabilityAnomalyCodeStats should count anomaly codes', () => {
  const ret = buildObservabilityAnomalyCodeStats([
    { code: 'a' },
    { code: 'a' },
    { code: 'b' },
    {},
  ]);
  assert.equal(ret.total, 4);
  assert.deepEqual(ret.counts, {
    a: 2,
    b: 1,
    unknown: 1,
  });
  assert.deepEqual(ret.rows[0], { code: 'a', count: 2 });
});

test('normalizeObservabilityAnomalyTrendHistory should keep valid points in window', () => {
  const now = 100 * 60 * 60 * 1000;
  const ret = normalizeObservabilityAnomalyTrendHistory([
    { atMs: now - (49 * 60 * 60 * 1000), counts: { a: 2 } },
    { atMs: now - (2 * 60 * 60 * 1000), counts: { a: 1, b: -2 } },
    { atMs: now - (1 * 60 * 60 * 1000), counts: { b: 3 } },
    { atMs: now + 1, counts: { c: 1 } },
  ], now);
  assert.equal(ret.length, 2);
  assert.deepEqual(ret[0], {
    atMs: now - (2 * 60 * 60 * 1000),
    counts: { a: 1 },
  });
  assert.deepEqual(ret[1], {
    atMs: now - (1 * 60 * 60 * 1000),
    counts: { b: 3 },
  });
});

test('appendObservabilityAnomalyTrendSnapshot should append one normalized snapshot', () => {
  const now = 8_000_000;
  const ret = appendObservabilityAnomalyTrendSnapshot([
    { atMs: now - 1000, counts: { old: 1 } },
  ], [
    { code: 'low_success_rate' },
    { code: 'low_success_rate' },
    { code: 'db_errors' },
  ], now);
  assert.equal(ret.length, 2);
  assert.equal(ret[1].atMs, now);
  assert.deepEqual(ret[1].counts, {
    low_success_rate: 2,
    db_errors: 1,
  });
});

test('summarizeObservabilityAnomalyTrend should compare recent and previous windows', () => {
  const now = 10 * 24 * 60 * 60 * 1000;
  const oneHour = 60 * 60 * 1000;
  const history = [
    { atMs: now - (30 * oneHour), counts: { high_retry: 3 } },
    { atMs: now - (26 * oneHour), counts: { high_retry: 1, db_errors: 1 } },
    { atMs: now - (6 * oneHour), counts: { high_retry: 6, db_errors: 2 } },
    { atMs: now - (2 * oneHour), counts: { high_retry: 2 } },
  ];
  const ret = summarizeObservabilityAnomalyTrend(history, now);
  assert.equal(ret.recentSamples, 2);
  assert.equal(ret.previousSamples, 2);
  const highRetry = ret.rows.find((item) => item.code === 'high_retry');
  assert.equal(highRetry.recentAvg, 4);
  assert.equal(highRetry.previousAvg, 2);
  assert.equal(highRetry.trend, 'up');
  const dbErrors = ret.rows.find((item) => item.code === 'db_errors');
  assert.equal(dbErrors.recentAvg, 1);
  assert.equal(dbErrors.previousAvg, 0.5);
  assert.equal(dbErrors.trend, 'up');
});

test('normalizeObservabilitySloTargets should fallback and clamp', () => {
  const ret = normalizeObservabilitySloTargets({
    refreshSuccessRateMin: 0,
    cacheHitRateMin: 101,
    dbErrorRateMax: -1,
    avgDbLatencyMaxMs: 0,
  });
  assert.deepEqual(ret, {
    refreshSuccessRateMin: 1,
    cacheHitRateMin: 99.99,
    dbErrorRateMax: 0,
    avgDbLatencyMaxMs: 1,
  });
  assert.equal(
    normalizeObservabilitySloTargets({}).refreshSuccessRateMin,
    DEFAULT_OBSERVABILITY_SLO_TARGETS.refreshSuccessRateMin,
  );
});

test('buildObservabilitySliSnapshot should evaluate indicator statuses', () => {
  const ret = buildObservabilitySliSnapshot({
    rows: [
      {
        totalRuns: 10,
        successRate: 90,
      },
      {
        totalRuns: 10,
        successRate: 70,
      },
    ],
    metrics: {
      cacheHitRate: 60,
      dbQueryTotal: 100,
      dbErrorTotal: 2,
      avgDbLatencyMs: 1300,
    },
  }, {
    refreshSuccessRateMin: 95,
    cacheHitRateMin: 70,
    dbErrorRateMax: 1.5,
    avgDbLatencyMaxMs: 1000,
  });
  const byCode = Object.fromEntries(ret.indicators.map((item) => [item.code, item]));
  assert.equal(byCode.refresh_success_rate.status, 'warning');
  assert.equal(byCode.cache_hit_rate.status, 'warning');
  assert.equal(byCode.db_error_rate.status, 'warning');
  assert.equal(byCode.avg_db_latency.status, 'warning');
  assert.equal(ret.dangerCount, 0);
  assert.equal(ret.warningCount, 4);
});

test('buildObservabilitySliSnapshot should mark danger when far from target', () => {
  const ret = buildObservabilitySliSnapshot({
    rows: [
      {
        totalRuns: 10,
        successRate: 20,
      },
    ],
    metrics: {
      cacheHitRate: 10,
      dbQueryTotal: 10,
      dbErrorTotal: 9,
      avgDbLatencyMs: 5000,
    },
  }, {
    refreshSuccessRateMin: 90,
    cacheHitRateMin: 80,
    dbErrorRateMax: 5,
    avgDbLatencyMaxMs: 1000,
  });
  assert.equal(ret.dangerCount, 4);
  assert.equal(ret.warningCount, 0);
});
