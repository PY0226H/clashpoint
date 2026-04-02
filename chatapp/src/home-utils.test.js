import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildHomeSearchIndex,
  filterHomeSearchItems,
  normalizeHomeSearchQuery,
  summarizeDebateSessionStats,
} from './home-utils';

test('normalizeHomeSearchQuery should trim and lowercase', () => {
  assert.equal(normalizeHomeSearchQuery('  Pro Duel  '), 'pro duel');
  assert.equal(normalizeHomeSearchQuery(null), '');
});

test('summarizeDebateSessionStats should aggregate status counters', () => {
  const stats = summarizeDebateSessionStats([
    { status: 'running', joinable: false },
    { status: 'open', joinable: true },
    { status: 'scheduled', joinable: true },
    { status: 'closed', joinable: false },
  ]);
  assert.deepEqual(stats, {
    total: 4,
    joinable: 2,
    live: 1,
    upcoming: 2,
    ended: 1,
  });
});

test('buildHomeSearchIndex should include chat/topic/session entries', () => {
  const items = buildHomeSearchIndex({
    channels: [{ id: 1, type: 'group', name: 'General' }],
    topics: [{ id: 9, title: '云顶之弈平衡', category: 'game' }],
    sessions: [{ id: 33, topicId: 9, status: 'running' }],
    topicTitleById: (id) => (id === 9 ? '云顶之弈平衡' : ''),
  });
  assert.equal(items.length, 3);
  assert.equal(items[0].kind, 'chat');
  assert.equal(items[1].kind, 'topic');
  assert.equal(items[2].kind, 'session');
});

test('filterHomeSearchItems should return matched items only', () => {
  const items = buildHomeSearchIndex({
    channels: [{ id: 1, type: 'group', name: 'General' }],
    topics: [{ id: 9, title: '云顶之弈平衡', category: 'game' }],
    sessions: [{ id: 33, topicId: 9, status: 'running' }],
    topicTitleById: (id) => (id === 9 ? '云顶之弈平衡' : ''),
  });
  const matched = filterHomeSearchItems(items, '平衡', { limit: 10 });
  assert.equal(matched.length, 2);
  assert.ok(matched.every((item) => item.kind === 'topic' || item.kind === 'session'));
});
