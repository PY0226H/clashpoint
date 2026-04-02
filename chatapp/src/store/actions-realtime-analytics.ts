type CommitFn = (type: string, payload?: unknown) => void;
type DispatchFn = (action: string, payload?: unknown) => Promise<unknown>;

type NetworkFn = (
  store: unknown,
  method: string,
  url: string,
  data?: unknown,
  headers?: Record<string, string>,
  allowRefreshRetry?: boolean,
) => Promise<{ data?: unknown } | unknown>;

type BuildQueryStringFn = (params?: Record<string, unknown>) => string;
type NormalizeJudgeRefreshSummaryQueryFn = (
  payload?: Record<string, unknown>,
) => { hours: number; limit: number; debateSessionId?: number | null };
type NormalizeJudgeRefreshSummaryMetricsFn = (payload?: Record<string, unknown>) => unknown;
type GetUrlBaseFn = () => string;
type GetAccessTicketTokenFn = () => string | null | undefined;

type SendMessagePayload = {
  chatId?: number | string | null;
  [key: string]: unknown;
};

function responseData<T = unknown>(response: unknown): T | undefined {
  const value = response as { data?: T } | undefined;
  return value?.data;
}

function bearerHeader(token?: string | null) {
  return {
    Authorization: `Bearer ${token || ''}`,
  };
}

export async function actionListDebateMessages({
  network,
  store,
  buildQueryString,
  token,
  sessionId,
  lastId = null,
  limit = 80,
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  token?: string | null;
  sessionId?: number | string | null;
  lastId?: number | string | null;
  limit?: number | string | null;
}) {
  if (!sessionId) {
    throw new Error('sessionId is required');
  }
  const suffix = buildQueryString({
    lastId,
    limit,
  });
  const response = await network(
    store,
    'get',
    `/debate/sessions/${sessionId}/messages${suffix}`,
    null,
    bearerHeader(token),
  );
  return responseData(response) || [];
}

export async function actionListDebatePinnedMessages({
  network,
  store,
  buildQueryString,
  token,
  sessionId,
  activeOnly = true,
  limit = 20,
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  token?: string | null;
  sessionId?: number | string | null;
  activeOnly?: boolean;
  limit?: number | string | null;
}) {
  if (!sessionId) {
    throw new Error('sessionId is required');
  }
  const suffix = buildQueryString({
    activeOnly,
    limit,
  });
  const response = await network(
    store,
    'get',
    `/debate/sessions/${sessionId}/pins${suffix}`,
    null,
    bearerHeader(token),
  );
  return responseData(response) || [];
}

export async function actionCreateDebateMessage({
  network,
  store,
  token,
  sessionId,
  content,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  sessionId?: number | string | null;
  content?: string | null;
}) {
  if (!sessionId) {
    throw new Error('sessionId is required');
  }
  if (!content || !String(content).trim()) {
    throw new Error('content is required');
  }
  const response = await network(
    store,
    'post',
    `/debate/sessions/${sessionId}/messages`,
    { content: String(content).trim() },
    bearerHeader(token),
  );
  return responseData(response);
}

export async function actionUploadFiles({
  network,
  store,
  dispatch,
  token,
  files,
  getUrlBase,
  getAccessTicketToken,
}: {
  network: NetworkFn;
  store: unknown;
  dispatch: DispatchFn;
  token?: string | null;
  files: File[];
  getUrlBase: GetUrlBaseFn;
  getAccessTicketToken: GetAccessTicketTokenFn;
}) {
  await dispatch('refreshAccessTickets');
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });

  const response = await network(store, 'post', '/upload', formData, {
    Authorization: `Bearer ${token || ''}`,
    'Content-Type': 'multipart/form-data',
  });

  const uploadedPaths = (responseData<string[]>(response) || []) as string[];
  return uploadedPaths.map((path) => ({
    path,
    fullUrl: `${getUrlBase()}${path}?token=${getAccessTicketToken() || ''}`,
  }));
}

export async function actionSendMessage({
  network,
  store,
  commit,
  token,
  payload,
}: {
  network: NetworkFn;
  store: unknown;
  commit: CommitFn;
  token?: string | null;
  payload: SendMessagePayload;
}) {
  if (!payload.chatId) {
    throw new Error('active channel is required before sending message');
  }
  const response = await network(store, 'post', `/chats/${payload.chatId}`, payload, bearerHeader(token));
  const message = responseData(response);
  commit('addMessage', { channelId: payload.chatId, message });
  return message;
}

export async function actionFetchJudgeRefreshSummary({
  network,
  store,
  buildQueryString,
  normalizeJudgeRefreshSummaryQuery,
  token,
  payload = {},
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  normalizeJudgeRefreshSummaryQuery: NormalizeJudgeRefreshSummaryQueryFn;
  token?: string | null;
  payload?: Record<string, unknown>;
}) {
  const { hours, limit, debateSessionId } = normalizeJudgeRefreshSummaryQuery(payload);
  const params: Record<string, unknown> = {
    hours,
    limit,
  };
  if (debateSessionId != null) {
    params.debateSessionId = debateSessionId;
  }
  const response = await network(
    store,
    'get',
    `/analytics/judge-refresh/summary${buildQueryString(params)}`,
    null,
    token ? bearerHeader(token) : {},
  );
  return responseData(response);
}

export async function actionFetchJudgeRefreshSummaryMetrics({
  network,
  store,
  normalizeJudgeRefreshSummaryMetrics,
  token,
}: {
  network: NetworkFn;
  store: unknown;
  normalizeJudgeRefreshSummaryMetrics: NormalizeJudgeRefreshSummaryMetricsFn;
  token?: string | null;
}) {
  const response = await network(
    store,
    'get',
    '/analytics/judge-refresh/summary/metrics',
    null,
    token ? bearerHeader(token) : {},
  );
  return normalizeJudgeRefreshSummaryMetrics(responseData(response) || {});
}
