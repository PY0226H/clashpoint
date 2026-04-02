import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildNotificationCenterItems,
  countNotificationCenterItems,
} from './notification-center-utils';

test('buildNotificationCenterItems should include judge and draw events sorted by time', () => {
  const items = buildNotificationCenterItems({
    latestJudgeReportEvent: {
      sessionId: 17,
      reportId: 55,
      winner: 'pro',
      receivedAt: 1700000000000,
    },
    latestDrawVoteResolvedEvent: {
      sessionId: 17,
      voteId: 89,
      resolution: 'rematch_started',
      decisionSource: 'vote_timeout',
      rematchSessionId: 23,
      decidedAt: '2024-01-01T00:00:00.000Z',
    },
  });

  assert.equal(items.length, 2);
  const judge = items.find((item) => item.kind === 'judge_report_ready');
  const draw = items.find((item) => item.kind === 'draw_vote_resolved');
  assert.ok(judge);
  assert.ok(draw);
  assert.equal(judge.path, '/judge-report');
  assert.deepEqual(judge.query, { sessionId: '17' });
  assert.equal(draw.path, '/debate/sessions/23');
  assert.equal(draw.subtitle, '场次 #17 · resolution=rematch_started · source=vote_timeout');
  assert.ok(items[0].createdAtMs >= items[1].createdAtMs);
});

test('buildNotificationCenterItems should ignore invalid payload and use fallback routing', () => {
  const items = buildNotificationCenterItems({
    latestJudgeReportEvent: { sessionId: 0 },
    latestDrawVoteResolvedEvent: {
      sessionId: 9,
      resolution: 'draw_confirmed',
      decisionSource: 'unexpected',
      rematchSessionId: null,
    },
  }, { nowMs: 99 });

  assert.equal(items.length, 1);
  assert.equal(items[0].key, 'draw:9');
  assert.equal(items[0].path, '/debate/sessions/9');
  assert.equal(items[0].subtitle, '场次 #9 · resolution=draw_confirmed · source=-');
  assert.equal(items[0].createdAtMs, 99);
});

test('countNotificationCenterItems should return array length only', () => {
  assert.equal(countNotificationCenterItems([{ key: 'a' }, { key: 'b' }]), 2);
  assert.equal(countNotificationCenterItems(null), 0);
});
