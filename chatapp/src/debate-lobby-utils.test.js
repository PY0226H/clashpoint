import assert from 'node:assert/strict';
import {
  classifyLobbySessionLane,
  compareLobbySessions,
  filterDebateSessions,
  isSessionEnded,
  isSessionJoinOpen,
  matchesLaneFilter,
  matchesStatusFilter,
  normalizeLobbyLane,
  normalizeSessionStatus,
  normalizeSessionTopicId,
  splitLobbySessionsByLane,
} from './debate-lobby-utils';

assert.equal(normalizeSessionStatus(' Running '), 'running');
assert.equal(normalizeSessionStatus(null), '');

assert.equal(normalizeSessionTopicId({ topicId: 7 }), 7);
assert.equal(normalizeSessionTopicId({ topic_id: '9' }), 9);
assert.equal(normalizeSessionTopicId({}), null);

assert.equal(isSessionEnded('judging'), true);
assert.equal(isSessionEnded('closed'), true);
assert.equal(isSessionEnded('canceled'), true);
assert.equal(isSessionEnded('running'), false);
assert.equal(isSessionJoinOpen('open'), true);
assert.equal(isSessionJoinOpen('scheduled'), true);
assert.equal(isSessionJoinOpen('running'), false);
assert.equal(classifyLobbySessionLane({ status: 'running' }), 'live');
assert.equal(classifyLobbySessionLane({ status: 'open' }), 'upcoming');
assert.equal(classifyLobbySessionLane({ status: 'closed' }), 'ended');
assert.equal(normalizeLobbyLane(' LIVE '), 'live');
assert.equal(normalizeLobbyLane('unknown'), 'all');
assert.equal(matchesLaneFilter({ status: 'running' }, 'live'), true);
assert.equal(matchesLaneFilter({ status: 'open' }, 'live'), false);

assert.equal(matchesStatusFilter({ status: 'closed' }, 'ended'), true);
assert.equal(matchesStatusFilter({ status: 'judging' }, 'ended'), true);
assert.equal(matchesStatusFilter({ status: 'running' }, 'live'), true);
assert.equal(matchesStatusFilter({ status: 'open', joinable: true }, 'joinable'), true);
assert.equal(matchesStatusFilter({ status: 'scheduled' }, 'upcoming'), true);
assert.equal(matchesStatusFilter({ status: 'open' }, 'all'), true);
assert.equal(matchesStatusFilter({ status: 'open' }, 'running'), false);

const sorted = [
  {
    id: 1,
    status: 'scheduled',
    joinable: false,
    scheduledStartAt: '2026-02-26T01:00:00Z',
  },
  {
    id: 2,
    status: 'running',
    joinable: true,
    scheduledStartAt: '2026-02-26T00:00:00Z',
  },
  {
    id: 3,
    status: 'open',
    joinable: true,
    scheduledStartAt: '2026-02-27T00:00:00Z',
  },
].sort(compareLobbySessions);
assert.deepEqual(
  sorted.map((item) => item.id),
  [2, 3, 1],
);

const sessions = [
  { id: 1, topicId: 7, status: 'open', joinable: true, scheduledStartAt: '2026-02-26T00:00:00Z' },
  { id: 2, topicId: 9, status: 'closed', joinable: false, scheduledStartAt: '2026-02-25T00:00:00Z' },
  { id: 3, topicId: 7, status: 'running', joinable: true, scheduledStartAt: '2026-02-27T00:00:00Z' },
];

const filteredTopic = filterDebateSessions(sessions, {
  selectedTopicId: '7',
  statusFilter: 'all',
});
assert.deepEqual(
  filteredTopic.map((item) => item.id),
  [3, 1],
);

const filteredEnded = filterDebateSessions(sessions, {
  statusFilter: 'ended',
});
assert.deepEqual(
  filteredEnded.map((item) => item.id),
  [2],
);

const filteredKeyword = filterDebateSessions(sessions, {
  statusFilter: 'all',
  keyword: '云顶',
  topicTitleById: (topicId) => (topicId === 7 ? '云顶之弈版本争论' : '其他'),
});
assert.deepEqual(
  filteredKeyword.map((item) => item.id),
  [3, 1],
);

const filteredJoinableOnly = filterDebateSessions(sessions, {
  statusFilter: 'all',
  joinableOnly: true,
});
assert.deepEqual(
  filteredJoinableOnly.map((item) => item.id),
  [3, 1],
);

const filteredLane = filterDebateSessions(sessions, {
  statusFilter: 'all',
  laneFilter: 'upcoming',
});
assert.deepEqual(
  filteredLane.map((item) => item.id),
  [1],
);

const lanes = splitLobbySessionsByLane([
  { id: 11, status: 'running' },
  { id: 12, status: 'open' },
  { id: 13, status: 'scheduled' },
  { id: 14, status: 'closed' },
]);
assert.deepEqual(lanes.live.map((item) => item.id), [11]);
assert.deepEqual(lanes.upcoming.map((item) => item.id), [12, 13]);
assert.deepEqual(lanes.ended.map((item) => item.id), [14]);
