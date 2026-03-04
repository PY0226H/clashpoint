import assert from 'node:assert/strict';
import {
  buildQuickUpdateSessionPayload,
  getOpsSessionJoinability,
  getOpsSessionRecommendedAction,
  getOpsSessionWindowState,
  nextQuickStatusActions,
  normalizeOpsSessionStatus,
} from './debate-ops-utils.js';

assert.equal(normalizeOpsSessionStatus(' running '), 'running');
assert.equal(normalizeOpsSessionStatus('INVALID'), 'scheduled');

assert.deepEqual(nextQuickStatusActions('scheduled'), ['open', 'canceled']);
assert.deepEqual(nextQuickStatusActions('open'), ['running', 'canceled']);
assert.deepEqual(nextQuickStatusActions('running'), ['judging', 'closed', 'canceled']);
assert.deepEqual(nextQuickStatusActions('judging'), ['closed', 'canceled']);
assert.deepEqual(nextQuickStatusActions('closed'), []);

const nowMs = Date.parse('2026-03-04T00:30:00.000Z');
assert.equal(
  getOpsSessionWindowState(
    {
      scheduledStartAt: '2026-03-04T01:00:00.000Z',
      endAt: '2026-03-04T02:00:00.000Z',
    },
    nowMs,
  ),
  'upcoming',
);
assert.equal(
  getOpsSessionWindowState(
    {
      scheduledStartAt: '2026-03-04T00:00:00.000Z',
      endAt: '2026-03-04T02:00:00.000Z',
    },
    nowMs,
  ),
  'active',
);
assert.equal(
  getOpsSessionWindowState(
    {
      scheduledStartAt: '2026-03-03T00:00:00.000Z',
      endAt: '2026-03-04T00:00:00.000Z',
    },
    nowMs,
  ),
  'expired',
);
assert.equal(
  getOpsSessionWindowState(
    {
      scheduledStartAt: '2026-03-04T03:00:00.000Z',
      endAt: '2026-03-04T01:00:00.000Z',
    },
    nowMs,
  ),
  'invalid',
);

assert.deepEqual(
  getOpsSessionJoinability(
    {
      status: 'open',
      joinable: false,
      scheduledStartAt: '2026-03-04T01:00:00.000Z',
      endAt: '2026-03-04T02:00:00.000Z',
    },
    nowMs,
  ),
  {
    joinable: false,
    code: 'not_started',
    text: '未到开始时间',
  },
);
assert.deepEqual(
  getOpsSessionJoinability(
    {
      status: 'scheduled',
      joinable: false,
      scheduledStartAt: '2026-03-04T00:00:00.000Z',
      endAt: '2026-03-04T02:00:00.000Z',
    },
    nowMs,
  ),
  {
    joinable: false,
    code: 'status_blocked',
    text: '状态 scheduled 不允许加入',
  },
);
assert.deepEqual(
  getOpsSessionJoinability(
    {
      status: 'open',
      joinable: true,
      scheduledStartAt: '2026-03-04T00:00:00.000Z',
      endAt: '2026-03-04T02:00:00.000Z',
    },
    nowMs,
  ),
  {
    joinable: true,
    code: 'ready',
    text: '可参与（joinable）',
  },
);

assert.deepEqual(
  getOpsSessionRecommendedAction(
    {
      status: 'open',
      scheduledStartAt: '2026-03-04T01:00:00.000Z',
      endAt: '2026-03-04T02:00:00.000Z',
    },
    nowMs,
  ),
  {
    targetStatus: 'scheduled',
    label: '设为 scheduled',
    reason: '未到开始时间，建议保持待开启',
  },
);
assert.deepEqual(
  getOpsSessionRecommendedAction(
    {
      status: 'scheduled',
      scheduledStartAt: '2026-03-04T00:00:00.000Z',
      endAt: '2026-03-04T02:00:00.000Z',
    },
    nowMs,
  ),
  {
    targetStatus: 'open',
    label: '设为 open',
    reason: '已到开始时间，建议开放加入',
  },
);
assert.deepEqual(
  getOpsSessionRecommendedAction(
    {
      status: 'running',
      scheduledStartAt: '2026-03-03T00:00:00.000Z',
      endAt: '2026-03-04T00:00:00.000Z',
    },
    nowMs,
  ),
  {
    targetStatus: 'judging',
    label: '设为 judging',
    reason: '已过结束时间，建议进入裁决',
  },
);

const payload = buildQuickUpdateSessionPayload(
  {
    id: 8,
    maxParticipantsPerSide: 500,
    scheduledStartAt: '2026-02-26T01:00:00.000Z',
    endAt: '2026-02-26T02:00:00.000Z',
  },
  'running',
);
assert.deepEqual(payload, {
  sessionId: 8,
  status: 'running',
  scheduledStartAt: '2026-02-26T01:00:00.000Z',
  endAt: '2026-02-26T02:00:00.000Z',
  maxParticipantsPerSide: 500,
});

assert.throws(
  () => buildQuickUpdateSessionPayload({ id: 0 }, 'open'),
  /invalid session id/,
);

assert.throws(
  () =>
    buildQuickUpdateSessionPayload(
      {
        id: 1,
        maxParticipantsPerSide: 0,
        scheduledStartAt: '2026-02-26T01:00:00.000Z',
        endAt: '2026-02-26T02:00:00.000Z',
      },
      'open',
    ),
  /invalid maxParticipantsPerSide/,
);

assert.throws(
  () =>
    buildQuickUpdateSessionPayload(
      {
        id: 1,
        maxParticipantsPerSide: 200,
        scheduledStartAt: '',
        endAt: '2026-02-26T02:00:00.000Z',
      },
      'open',
    ),
  /missing session schedule/,
);
