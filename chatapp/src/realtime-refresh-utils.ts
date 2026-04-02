const RETRY_DELAYS_MS = [0, 600, 1800];

export const AUTO_REFRESH_MAX_ATTEMPTS = RETRY_DELAYS_MS.length;

export function calcAutoRefreshDelayMs(attempt) {
  const index = Number(attempt) - 1;
  if (!Number.isInteger(index) || index < 0) {
    return RETRY_DELAYS_MS[0];
  }
  if (index >= RETRY_DELAYS_MS.length) {
    return RETRY_DELAYS_MS[RETRY_DELAYS_MS.length - 1];
  }
  return RETRY_DELAYS_MS[index];
}

export function shouldRetryAutoRefresh(err) {
  const status = Number(err?.response?.status || 0);
  if (status >= 400 && status < 500 && status !== 429) {
    return false;
  }
  return true;
}
