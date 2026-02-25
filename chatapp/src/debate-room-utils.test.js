import assert from 'node:assert/strict';
import {
  buildDebateRoomWsUrl,
  canSubmitDrawVote,
  getOldestDebateMessageId,
  extractDebateRoomEvent,
  mergeDebateRoomMessages,
  normalizeDebateRoomMessage,
  normalizeDrawVoteStatus,
  normalizeJudgeReportStatus,
  parseDebateRoomWsMessage,
  shouldPollJudgeReportStatus,
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
});
assert.equal(wsUrlWithPrefix, 'wss://example.com/notify/ws/debate/88?token=t-1');

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

assert.equal(normalizeJudgeReportStatus('ready'), 'ready');
assert.equal(normalizeJudgeReportStatus('PENDING'), 'pending');
assert.equal(normalizeJudgeReportStatus('unknown-status'), 'absent');
assert.equal(normalizeJudgeReportStatus(null), 'absent');
assert.equal(shouldPollJudgeReportStatus('pending'), true);
assert.equal(shouldPollJudgeReportStatus('ready'), false);

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
