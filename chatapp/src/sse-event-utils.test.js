import assert from 'node:assert/strict';
import { parseNamedSseEventData, parseSseAppEventData } from './sse-event-utils';

const raw = JSON.stringify({
  event: 'DebateJudgeReportReady',
  sessionId: 12,
  reportId: 33,
});
const parsed = parseSseAppEventData(raw);
assert.deepEqual(parsed, {
  event: 'DebateJudgeReportReady',
  payload: {
    sessionId: 12,
    reportId: 33,
  },
});

assert.equal(parseSseAppEventData('{'), null);
assert.equal(parseSseAppEventData(''), null);
assert.equal(parseSseAppEventData('[]'), null);

const matched = parseNamedSseEventData(raw, 'DebateJudgeReportReady');
assert.deepEqual(matched, { sessionId: 12, reportId: 33 });
assert.equal(parseNamedSseEventData(raw, 'DebateDrawVoteResolved'), null);
