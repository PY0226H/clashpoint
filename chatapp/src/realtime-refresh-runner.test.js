import assert from 'node:assert/strict';
import { runAutoRefreshWithRetry } from './realtime-refresh-runner.js';

const noSleep = async () => {};

let firstCall = 0;
const firstSuccess = await runAutoRefreshWithRetry({
  fetchOnce: async () => {
    firstCall += 1;
  },
  sleep: noSleep,
});
assert.equal(firstSuccess.ok, true);
assert.equal(firstSuccess.attempt, 1);
assert.equal(firstCall, 1);

let callTimes = 0;
const retryLogs = [];
const secondSuccess = await runAutoRefreshWithRetry({
  fetchOnce: async () => {
    callTimes += 1;
    if (callTimes === 1) {
      const err = new Error('rate limited');
      err.response = { status: 429 };
      throw err;
    }
  },
  sleep: noSleep,
  onRetry: (v) => retryLogs.push(v),
});
assert.equal(secondSuccess.ok, true);
assert.equal(secondSuccess.attempt, 2);
assert.equal(callTimes, 2);
assert.equal(retryLogs.length, 1);
assert.equal(retryLogs[0].attempt, 2);
assert.equal(retryLogs[0].delayMs, 600);

let failCall = 0;
const failFast = await runAutoRefreshWithRetry({
  fetchOnce: async () => {
    failCall += 1;
    const err = new Error('bad request');
    err.response = { status: 400 };
    throw err;
  },
  sleep: noSleep,
});
assert.equal(failFast.ok, false);
assert.equal(failFast.attempt, 1);
assert.equal(failCall, 1);

let exhaustedCall = 0;
const exhaustedRetryLogs = [];
const exhausted = await runAutoRefreshWithRetry({
  fetchOnce: async () => {
    exhaustedCall += 1;
    const err = new Error('server error');
    err.response = { status: 500 };
    throw err;
  },
  sleep: noSleep,
  onRetry: (v) => exhaustedRetryLogs.push(v),
});
assert.equal(exhausted.ok, false);
assert.equal(exhausted.attempt, 3);
assert.equal(exhaustedCall, 3);
assert.equal(exhaustedRetryLogs.length, 2);
assert.equal(exhaustedRetryLogs[0].delayMs, 600);
assert.equal(exhaustedRetryLogs[1].delayMs, 1800);
