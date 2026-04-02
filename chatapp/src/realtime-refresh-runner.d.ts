export interface AutoRefreshRetryInfo {
  attempt: number;
  delayMs: number;
  sourceEventType: string;
}

export interface AutoRefreshSuccessResult {
  ok: true;
  attempt: number;
  sourceEventType: string;
  at: number;
}

export interface AutoRefreshFailureResult {
  ok: false;
  attempt: number;
  sourceEventType: string;
  at: number;
  error: unknown;
}

export type AutoRefreshResult = AutoRefreshSuccessResult | AutoRefreshFailureResult;

export interface RunAutoRefreshWithRetryInput {
  fetchOnce: () => Promise<unknown>;
  sourceEventType?: string;
  maxAttempts?: number;
  calcDelayMs?: (attempt: number) => number;
  shouldRetry?: (err: unknown) => boolean;
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
  onRetry?: (info: AutoRefreshRetryInfo) => void;
  onSuccess?: (result: AutoRefreshSuccessResult) => void;
  onFailure?: (result: AutoRefreshFailureResult) => void;
}

export function runAutoRefreshWithRetry(input: RunAutoRefreshWithRetryInput): Promise<AutoRefreshResult>;
