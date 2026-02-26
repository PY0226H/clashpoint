import test from 'node:test';
import assert from 'node:assert/strict';
import { pickActiveChannelId, pickDefaultPeerUserId } from './channel-utils.js';

test('pickDefaultPeerUserId should return first non-self user id', () => {
  const users = {
    1: { id: 1, fullname: 'A' },
    2: { id: 2, fullname: 'B' },
  };
  assert.equal(pickDefaultPeerUserId(users, 1), 2);
});

test('pickDefaultPeerUserId should return null when no peer user', () => {
  const users = {
    1: { id: 1, fullname: 'A' },
  };
  assert.equal(pickDefaultPeerUserId(users, 1), null);
});

test('pickActiveChannelId should prefer stored id when exists', () => {
  const channels = [{ id: 10 }, { id: 11 }];
  assert.equal(pickActiveChannelId(channels, 11), 11);
});

test('pickActiveChannelId should fallback to first channel', () => {
  const channels = [{ id: 10 }, { id: 11 }];
  assert.equal(pickActiveChannelId(channels, 999), 10);
});

test('pickActiveChannelId should return null for empty channels', () => {
  assert.equal(pickActiveChannelId([], 1), null);
});

