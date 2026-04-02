import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  clampInt,
  normalizeJudgeRefreshSummaryMetrics,
  normalizeJudgeRefreshSummaryQuery,
} from './judge-refresh-summary-utils';

test('clampInt should fallback when value is invalid', () => {
  assert.equal(clampInt(undefined, 1, 10, 3), 3);
  assert.equal(clampInt('abc', 1, 10, 4), 4);
});

test('clampInt should clamp into range', () => {
  assert.equal(clampInt(0, 1, 10, 3), 1);
  assert.equal(clampInt(11, 1, 10, 3), 10);
  assert.equal(clampInt(6.9, 1, 10, 3), 6);
});

test('normalizeJudgeRefreshSummaryQuery should return defaults', () => {
  assert.deepEqual(normalizeJudgeRefreshSummaryQuery(), {
    hours: 24,
    limit: 20,
    debateSessionId: null,
  });
});

test('normalizeJudgeRefreshSummaryQuery should clamp payload values', () => {
  assert.deepEqual(normalizeJudgeRefreshSummaryQuery({
    hours: 999,
    limit: 0,
    debateSessionId: '42',
  }), {
    hours: 168,
    limit: 1,
    debateSessionId: 42,
  });
});

test('normalizeJudgeRefreshSummaryQuery should ignore invalid session id', () => {
  assert.equal(normalizeJudgeRefreshSummaryQuery({ debateSessionId: 'x' }).debateSessionId, null);
  assert.equal(normalizeJudgeRefreshSummaryQuery({ debateSessionId: 0 }).debateSessionId, null);
});

test('normalizeJudgeRefreshSummaryMetrics should normalize invalid fields', () => {
  assert.deepEqual(normalizeJudgeRefreshSummaryMetrics({
    requestTotal: '100',
    cacheHitTotal: 80,
    cacheMissTotal: '20',
    cacheHitRate: '80.5',
    dbQueryTotal: '20',
    dbErrorTotal: -1,
    avgDbLatencyMs: '14.2',
    lastDbLatencyMs: 'x',
  }), {
    requestTotal: 100,
    cacheHitTotal: 80,
    cacheMissTotal: 20,
    cacheHitRate: 80.5,
    dbQueryTotal: 20,
    dbErrorTotal: 0,
    avgDbLatencyMs: 14.2,
    lastDbLatencyMs: 0,
  });
});
