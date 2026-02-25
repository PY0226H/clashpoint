import {
  AUTO_REFRESH_MAX_ATTEMPTS,
  calcAutoRefreshDelayMs,
  shouldRetryAutoRefresh,
} from './realtime-refresh-utils.js';

function defaultSleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export async function runAutoRefreshWithRetry({
  fetchOnce,
  sourceEventType = '',
  maxAttempts = AUTO_REFRESH_MAX_ATTEMPTS,
  calcDelayMs = calcAutoRefreshDelayMs,
  shouldRetry = shouldRetryAutoRefresh,
  sleep = defaultSleep,
  now = () => Date.now(),
  onRetry = () => {},
  onSuccess = () => {},
  onFailure = () => {},
}) {
  if (typeof fetchOnce !== 'function') {
    throw new Error('fetchOnce is required');
  }
  const attempts = Math.max(1, Number(maxAttempts) || 1);
  let lastError = null;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const delayMs = Math.max(0, Number(calcDelayMs(attempt)) || 0);
    if (delayMs > 0) {
      onRetry({ attempt, delayMs, sourceEventType });
      await sleep(delayMs);
    }
    try {
      await fetchOnce();
      const result = {
        ok: true,
        attempt,
        sourceEventType,
        at: now(),
      };
      onSuccess(result);
      return result;
    } catch (err) {
      lastError = err;
      if (attempt >= attempts || !shouldRetry(err)) {
        const result = {
          ok: false,
          attempt,
          sourceEventType,
          at: now(),
          error: err,
        };
        onFailure(result);
        return result;
      }
    }
  }

  const result = {
    ok: false,
    attempt: attempts,
    sourceEventType,
    at: now(),
    error: lastError,
  };
  onFailure(result);
  return result;
}
