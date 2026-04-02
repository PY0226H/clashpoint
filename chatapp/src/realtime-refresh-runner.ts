import {
  AUTO_REFRESH_MAX_ATTEMPTS,
  calcAutoRefreshDelayMs,
  shouldRetryAutoRefresh,
} from './realtime-refresh-utils';

type AutoRefreshRetryEvent = {
  attempt: number;
  delayMs: number;
  sourceEventType: string;
};

type AutoRefreshSuccessResult = {
  ok: true;
  attempt: number;
  sourceEventType: string;
  at: number;
};

type AutoRefreshFailureResult = {
  ok: false;
  attempt: number;
  sourceEventType: string;
  at: number;
  error: unknown;
};

type AutoRefreshResult = AutoRefreshSuccessResult | AutoRefreshFailureResult;

type RunAutoRefreshWithRetryOptions = {
  fetchOnce: () => Promise<unknown>;
  sourceEventType?: string;
  maxAttempts?: number;
  calcDelayMs?: (attempt: number) => number;
  shouldRetry?: (err: unknown) => boolean;
  sleep?: (ms: number) => Promise<unknown>;
  now?: () => number;
  onRetry?: (event: AutoRefreshRetryEvent) => void;
  onSuccess?: (result: AutoRefreshSuccessResult) => void;
  onFailure?: (result: AutoRefreshFailureResult) => void;
};

function defaultSleep(ms: number): Promise<void> {
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
  onRetry = (_event: AutoRefreshRetryEvent) => {},
  onSuccess = (_result: AutoRefreshSuccessResult) => {},
  onFailure = (_result: AutoRefreshFailureResult) => {},
}: RunAutoRefreshWithRetryOptions): Promise<AutoRefreshResult> {
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
      const result: AutoRefreshSuccessResult = {
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
        const result: AutoRefreshFailureResult = {
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

  const result: AutoRefreshFailureResult = {
    ok: false,
    attempt: attempts,
    sourceEventType,
    at: now(),
    error: lastError,
  };
  onFailure(result);
  return result;
}
