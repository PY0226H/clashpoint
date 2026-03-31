import assert from 'node:assert/strict';
import {
  advanceDebateAckSeq,
  buildDebateRoomAckMessage,
  buildDebateRoomWsUrl,
  canSubmitDrawVote,
  computeWsReconnectDelayMs,
  getDrawVoteRemainingMs,
  getOldestDebateMessageId,
  extractDebateRoomEvent,
  mergeDebateRoomMessages,
  normalizeDebateRoomMessage,
  normalizeDrawVoteStatus,
  judgeAutomationHintText,
  normalizeJudgeReportStatus,
  parseDebateRoomWsMessage,
  shouldShowManualJudgeTrigger,
  shouldPollJudgeReportStatus,
  toNonNegativeInt,
} from './debate-room-utils.js';

const wsUrl = buildDebateRoomWsUrl({
  notifyBase: 'http://localhost:6687/events',
  sessionId: 123,
  notifyTicket: 'abc',
});
assert.equal(wsUrl, 'ws://localhost:6687/ws/debate/123?token=abc');

const wsUrlWithPrefix = buildDebateRoomWsUrl({
  notifyBase: 'https://example.com/notify/events',
  sessionId: 88,
  notifyTicket: 't-1',
  lastAckSeq: 10,
});
assert.equal(wsUrlWithPrefix, 'wss://example.com/notify/ws/debate/88?token=t-1&lastAckSeq=10');

assert.throws(
  () => buildDebateRoomWsUrl({ notifyBase: 'http://localhost:6687/events', sessionId: 1 }),
  /notifyTicket is required/,
);

const welcome = parseDebateRoomWsMessage(
  JSON.stringify({ type: 'welcome', sessionId: 12, userId: 7 }),
);
assert.deepEqual(welcome, { type: 'welcome', sessionId: 12, userId: 7 });

const roomEvent = parseDebateRoomWsMessage(
  JSON.stringify({
    type: 'roomEvent',
    eventName: 'DebateMessageCreated',
    payload: { event: 'DebateMessageCreated', messageId: 9, sessionId: 12 },
  }),
);
assert.equal(roomEvent?.type, 'roomEvent');
assert.deepEqual(extractDebateRoomEvent(roomEvent), {
  event: 'DebateMessageCreated',
  messageId: 9,
  sessionId: 12,
});
assert.deepEqual(extractDebateRoomEvent(roomEvent, 'DebateMessageCreated'), {
  event: 'DebateMessageCreated',
  messageId: 9,
  sessionId: 12,
});
assert.equal(extractDebateRoomEvent(roomEvent, 'DebateMessagePinned'), null);

assert.equal(parseDebateRoomWsMessage('{'), null);
assert.equal(parseDebateRoomWsMessage(''), null);
assert.equal(parseDebateRoomWsMessage('[]'), null);
assert.equal(toNonNegativeInt('11'), 11);
assert.equal(toNonNegativeInt('11.9'), 11);
assert.equal(toNonNegativeInt('-1', 7), 7);
assert.equal(toNonNegativeInt(undefined, 5), 5);
assert.equal(advanceDebateAckSeq(4, 6), 6);
assert.equal(advanceDebateAckSeq(6, 4), 6);
assert.equal(advanceDebateAckSeq(6, 4, { force: true }), 4);
assert.equal(advanceDebateAckSeq(6, 'x', { force: true }), 6);
assert.equal(buildDebateRoomAckMessage(9), '{"type":"ack","eventSeq":9}');
assert.equal(buildDebateRoomAckMessage(-1), null);

assert.equal(normalizeJudgeReportStatus('ready'), 'ready');
assert.equal(normalizeJudgeReportStatus('PENDING'), 'pending');
assert.equal(normalizeJudgeReportStatus('unknown-status'), 'absent');
assert.equal(normalizeJudgeReportStatus(null), 'absent');
assert.equal(shouldPollJudgeReportStatus('pending'), true);
assert.equal(shouldPollJudgeReportStatus('ready'), false);
assert.equal(shouldShowManualJudgeTrigger('failed'), true);
assert.equal(shouldShowManualJudgeTrigger('pending'), false);
assert.equal(shouldShowManualJudgeTrigger('absent'), false);
assert.equal(judgeAutomationHintText('ready'), '系统已自动完成本场判决。');
assert.equal(judgeAutomationHintText('pending'), '系统已自动触发裁判，正在生成判决结果。');
assert.equal(judgeAutomationHintText('failed'), '自动触发或执行失败，可使用兜底重试。');
assert.equal(
  judgeAutomationHintText('absent'),
  '辩论结束后系统会自动触发裁判，无需手动发起。',
);

assert.equal(normalizeDrawVoteStatus('open'), 'open');
assert.equal(normalizeDrawVoteStatus('DECIDED'), 'decided');
assert.equal(normalizeDrawVoteStatus('invalid'), 'absent');
assert.equal(
  canSubmitDrawVote({ status: 'open', votingEndsAt: '2026-02-26T00:00:00Z' }, Date.parse('2026-02-25T00:00:00Z')),
  true,
);
assert.equal(
  canSubmitDrawVote({ status: 'open', votingEndsAt: '2026-02-24T00:00:00Z' }, Date.parse('2026-02-25T00:00:00Z')),
  false,
);
assert.equal(canSubmitDrawVote({ status: 'decided' }), false);
assert.equal(
  getDrawVoteRemainingMs({ status: 'open', votingEndsAt: '2026-02-26T00:00:00Z' }, Date.parse('2026-02-25T23:59:30Z')),
  30 * 1000,
);
assert.equal(
  getDrawVoteRemainingMs({ status: 'open', votingEndsAt: '2026-02-25T00:00:00Z' }, Date.parse('2026-02-25T00:01:00Z')),
  0,
);
assert.equal(getDrawVoteRemainingMs({ status: 'open', votingEndsAt: '' }), null);

const normalized = normalizeDebateRoomMessage({
  messageId: 12,
  sessionId: 7,
  userId: 3,
  side: 'pro',
  content: 'hello',
  createdAt: '2026-02-25T00:00:00Z',
});
assert.deepEqual(normalized, {
  id: 12,
  sessionId: 7,
  userId: 3,
  side: 'pro',
  content: 'hello',
  createdAt: '2026-02-25T00:00:00Z',
});
assert.equal(normalizeDebateRoomMessage({}), null);

const mergedMessages = mergeDebateRoomMessages(
  [
    { id: 2, content: 'old2', side: 'pro' },
    { id: 4, content: 'old4', side: 'con' },
  ],
  [
    { id: 1, content: 'old1', side: 'pro' },
    { id: 4, content: 'new4', side: 'con' },
    { id: 5, content: 'new5', side: 'pro' },
  ],
);
assert.deepEqual(mergedMessages.map((item) => item.id), [1, 2, 4, 5]);
assert.equal(mergedMessages.find((item) => item.id === 4)?.content, 'new4');
assert.equal(getOldestDebateMessageId(mergedMessages), 1);
assert.equal(getOldestDebateMessageId([]), null);

assert.equal(
  computeWsReconnectDelayMs(1, { baseMs: 1000, maxMs: 15000, jitterRatio: 0 }),
  1000,
);
assert.equal(
  computeWsReconnectDelayMs(2, { baseMs: 1000, maxMs: 15000, jitterRatio: 0 }),
  2000,
);
assert.equal(
  computeWsReconnectDelayMs(20, { baseMs: 1000, maxMs: 15000, jitterRatio: 0 }),
  15000,
);
assert.equal(
  computeWsReconnectDelayMs(3, {
    baseMs: 1000,
    maxMs: 15000,
    jitterRatio: 0.25,
    randomValue: 0,
  }),
  3000,
);
assert.equal(
  computeWsReconnectDelayMs(3, {
    baseMs: 1000,
    maxMs: 15000,
    jitterRatio: 0.25,
    randomValue: 1,
  }),
  5001,
);
