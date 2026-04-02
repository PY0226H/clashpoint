import assert from 'node:assert/strict';
import {
  AUTO_REFRESH_MAX_ATTEMPTS,
  calcAutoRefreshDelayMs,
  shouldRetryAutoRefresh,
} from './realtime-refresh-utils';

assert.equal(AUTO_REFRESH_MAX_ATTEMPTS, 3);
assert.equal(calcAutoRefreshDelayMs(1), 0);
assert.equal(calcAutoRefreshDelayMs(2), 600);
assert.equal(calcAutoRefreshDelayMs(3), 1800);
assert.equal(calcAutoRefreshDelayMs(100), 1800);
assert.equal(calcAutoRefreshDelayMs(0), 0);

assert.equal(shouldRetryAutoRefresh({ response: { status: 500 } }), true);
assert.equal(shouldRetryAutoRefresh({ response: { status: 429 } }), true);
assert.equal(shouldRetryAutoRefresh({ response: { status: 400 } }), false);
assert.equal(shouldRetryAutoRefresh({ response: { status: 403 } }), false);
assert.equal(shouldRetryAutoRefresh({ response: { status: 0 } }), true);
assert.equal(shouldRetryAutoRefresh(new Error('network')), true);
