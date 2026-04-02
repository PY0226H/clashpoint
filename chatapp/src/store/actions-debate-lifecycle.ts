type NetworkFn = (
  store: unknown,
  method: string,
  url: string,
  data?: unknown,
  headers?: Record<string, string>,
  allowRefreshRetry?: boolean,
) => Promise<{ data?: unknown } | unknown>;

type BuildQueryStringFn = (params?: Record<string, unknown>) => string;

function responseData<T = unknown>(response: unknown): T | undefined {
  const value = response as { data?: T } | undefined;
  return value?.data;
}

function bearerHeader(token?: string | null) {
  return {
    Authorization: `Bearer ${token || ''}`,
  };
}

export async function actionFetchJudgeReport({
  network,
  store,
  token,
  sessionId,
  maxStageCount = 3,
  stageOffset = 0,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  sessionId?: number | string | null;
  maxStageCount?: number | string | null;
  stageOffset?: number | string | null;
}) {
  if (!sessionId) {
    throw new Error('sessionId is required');
  }
  const query = new URLSearchParams();
  if (maxStageCount != null) {
    query.set('maxStageCount', String(maxStageCount));
  }
  if (stageOffset != null) {
    query.set('stageOffset', String(stageOffset));
  }
  const suffix = query.toString() ? `?${query.toString()}` : '';
  const response = await network(
    store,
    'get',
    `/debate/sessions/${sessionId}/judge-report${suffix}`,
    null,
    bearerHeader(token),
  );
  return responseData(response);
}

export async function actionFetchDrawVoteStatus({
  network,
  store,
  token,
  sessionId,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  sessionId?: number | string | null;
}) {
  if (!sessionId) {
    throw new Error('sessionId is required');
  }
  const response = await network(
    store,
    'get',
    `/debate/sessions/${sessionId}/draw-vote`,
    null,
    bearerHeader(token),
  );
  return responseData(response);
}

export async function actionSubmitDrawVote({
  network,
  store,
  token,
  sessionId,
  agreeDraw,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  sessionId?: number | string | null;
  agreeDraw: boolean;
}) {
  if (!sessionId) {
    throw new Error('sessionId is required');
  }
  if (typeof agreeDraw !== 'boolean') {
    throw new Error('agreeDraw must be boolean');
  }
  const response = await network(
    store,
    'post',
    `/debate/sessions/${sessionId}/draw-vote/ballots`,
    { agreeDraw },
    bearerHeader(token),
  );
  return responseData(response);
}

export async function actionRequestJudgeJob({
  network,
  store,
  token,
  sessionId,
  allowRejudge = false,
  styleMode = null,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  sessionId?: number | string | null;
  allowRejudge?: boolean;
  styleMode?: string | null;
}) {
  if (!sessionId) {
    throw new Error('sessionId is required');
  }
  const payload: Record<string, unknown> = {
    allowRejudge: !!allowRejudge,
  };
  if (styleMode != null && String(styleMode).trim()) {
    payload.styleMode = String(styleMode).trim();
  }
  const response = await network(
    store,
    'post',
    `/debate/sessions/${sessionId}/judge/jobs`,
    payload,
    bearerHeader(token),
  );
  return responseData(response);
}

export async function actionListDebateTopics({
  network,
  store,
  buildQueryString,
  token,
  payload = {},
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  token?: string | null;
  payload?: Record<string, unknown>;
}) {
  const suffix = buildQueryString({
    category: payload.category,
    activeOnly: payload.activeOnly,
    limit: payload.limit,
  });
  const response = await network(store, 'get', `/debate/topics${suffix}`, null, bearerHeader(token));
  return responseData(response) || [];
}

export async function actionListDebateSessions({
  network,
  store,
  buildQueryString,
  token,
  payload = {},
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  token?: string | null;
  payload?: Record<string, unknown>;
}) {
  const suffix = buildQueryString({
    status: payload.status,
    topicId: payload.topicId,
    from: payload.from,
    to: payload.to,
    limit: payload.limit,
  });
  const response = await network(store, 'get', `/debate/sessions${suffix}`, null, bearerHeader(token));
  return responseData(response) || [];
}

export async function actionListJudgeReviewsOps({
  network,
  store,
  buildQueryString,
  token,
  payload = {},
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  token?: string | null;
  payload?: Record<string, unknown>;
}) {
  const suffix = buildQueryString({
    from: payload.from,
    to: payload.to,
    winner: payload.winner,
    rejudgeTriggered: payload.rejudgeTriggered,
    hasVerdictEvidence: payload.hasVerdictEvidence,
    anomalyOnly: payload.anomalyOnly,
    limit: payload.limit,
  });
  const response = await network(
    store,
    'get',
    `/debate/ops/judge-reviews${suffix}`,
    null,
    bearerHeader(token),
  );
  return responseData(response) || { scannedCount: 0, returnedCount: 0, items: [] };
}

export async function actionListJudgeTraceReplayOps({
  network,
  store,
  buildQueryString,
  token,
  payload = {},
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  token?: string | null;
  payload?: Record<string, unknown>;
}) {
  const sessionId = Number(payload.sessionId || 0);
  const suffix = buildQueryString({
    from: payload.from,
    to: payload.to,
    sessionId: sessionId > 0 ? sessionId : null,
    scope: payload.scope,
    status: payload.status,
    limit: payload.limit,
  });
  const response = await network(
    store,
    'get',
    `/debate/ops/judge-trace-replay${suffix}`,
    null,
    bearerHeader(token),
  );
  return (
    responseData(response) || {
      scannedCount: 0,
      returnedCount: 0,
      phaseCount: 0,
      finalCount: 0,
      failedCount: 0,
      replayEligibleCount: 0,
      items: [],
    }
  );
}

export async function actionJoinDebateSession({
  network,
  store,
  token,
  sessionId,
  side,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  sessionId?: number | string | null;
  side?: string | null;
}) {
  if (!sessionId) {
    throw new Error('sessionId is required');
  }
  if (!side) {
    throw new Error('side is required');
  }
  const response = await network(
    store,
    'post',
    `/debate/sessions/${sessionId}/join`,
    { side },
    bearerHeader(token),
  );
  return responseData(response);
}
