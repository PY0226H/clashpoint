import test from 'node:test';
import assert from 'node:assert/strict';
import { upsertMessage } from './message-store-utils';

test('upsertMessage should append new message', () => {
  const ret = upsertMessage([], {
    id: 1,
    content: 'hello',
    createdAt: '2026-02-26T00:00:00Z',
  });
  assert.equal(ret.length, 1);
  assert.equal(ret[0].id, 1);
  assert.equal(ret[0].content, 'hello');
  assert.equal(typeof ret[0].formattedCreatedAt, 'string');
});

test('upsertMessage should replace duplicate message by id', () => {
  const first = {
    id: 8,
    content: 'old',
    createdAt: '2026-02-26T00:00:00Z',
  };
  const second = {
    id: 8,
    content: 'new',
    createdAt: '2026-02-26T00:00:01Z',
  };
  const ret = upsertMessage([first], second);
  assert.equal(ret.length, 1);
  assert.equal(ret[0].content, 'new');
});
