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

export async function actionGetOpsObservabilityConfig({
  network,
  store,
  token,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
}) {
  const response = await network(store, 'get', '/debate/ops/observability/config', null, bearerHeader(token));
  return responseData(response) || null;
}

export async function actionUpsertOpsObservabilityThresholds({
  network,
  store,
  token,
  payload,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  payload: Record<string, unknown>;
}) {
  const response = await network(
    store,
    'put',
    '/debate/ops/observability/thresholds',
    payload,
    bearerHeader(token),
  );
  return responseData(response) || null;
}

export async function actionUpsertOpsObservabilityAnomalyState({
  network,
  store,
  token,
  payload,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  payload: Record<string, unknown>;
}) {
  const response = await network(
    store,
    'put',
    '/debate/ops/observability/anomaly-state',
    payload,
    bearerHeader(token),
  );
  return responseData(response) || null;
}

export async function actionListJudgeReplayActionsOps({
  network,
  store,
  buildQueryString,
  token,
  payload,
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  token?: string | null;
  payload: Record<string, unknown>;
}) {
  const sessionId = Number(payload.sessionId || 0);
  const jobId = Number(payload.jobId || 0);
  const requestedBy = Number(payload.requestedBy || 0);
  const offset = Number(payload.offset || 0);
  const suffix = buildQueryString({
    from: payload.from,
    to: payload.to,
    scope: payload.scope,
    sessionId: sessionId > 0 ? sessionId : null,
    jobId: jobId > 0 ? jobId : null,
    requestedBy: requestedBy > 0 ? requestedBy : null,
    previousStatus: payload.previousStatus,
    newStatus: payload.newStatus,
    reasonKeyword: payload.reasonKeyword,
    traceKeyword: payload.traceKeyword,
    limit: payload.limit,
    offset: offset >= 0 ? offset : 0,
  });
  const response = await network(
    store,
    'get',
    `/debate/ops/judge-replay/actions${suffix}`,
    null,
    bearerHeader(token),
  );
  return (
    responseData(response) || {
      scannedCount: 0,
      returnedCount: 0,
      hasMore: false,
      items: [],
    }
  );
}

export async function actionGetJudgeReplayPreviewOps({
  network,
  store,
  buildQueryString,
  token,
  scope,
  jobId,
}: {
  network: NetworkFn;
  store: unknown;
  buildQueryString: BuildQueryStringFn;
  token?: string | null;
  scope?: string | null;
  jobId?: number | string | null;
}) {
  const normalizedScope = String(scope || '').trim();
  const normalizedJobId = Number(jobId || 0);
  if (!normalizedScope) {
    throw new Error('scope is required');
  }
  if (!normalizedJobId) {
    throw new Error('jobId is required');
  }
  const suffix = buildQueryString({
    scope: normalizedScope,
    jobId: normalizedJobId,
  });
  const response = await network(
    store,
    'get',
    `/debate/ops/judge-replay/preview${suffix}`,
    null,
    bearerHeader(token),
  );
  return responseData(response) || null;
}

export async function actionExecuteJudgeReplayOps({
  network,
  store,
  token,
  scope,
  jobId,
  reason = null,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  scope?: string | null;
  jobId?: number | string | null;
  reason?: string | null;
}) {
  const normalizedScope = String(scope || '').trim();
  const normalizedJobId = Number(jobId || 0);
  if (!normalizedScope) {
    throw new Error('scope is required');
  }
  if (!normalizedJobId) {
    throw new Error('jobId is required');
  }
  const response = await network(
    store,
    'post',
    '/debate/ops/judge-replay/execute',
    {
      scope: normalizedScope,
      jobId: normalizedJobId,
      reason: reason == null ? null : String(reason).trim() || null,
    },
    bearerHeader(token),
  );
  return responseData(response) || null;
}

export async function actionCreateDebateTopicOps({
  network,
  store,
  token,
  title,
  description,
  category,
  stancePro,
  stanceCon,
  contextSeed = null,
  isActive = true,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  title?: string | null;
  description?: string | null;
  category?: string | null;
  stancePro?: string | null;
  stanceCon?: string | null;
  contextSeed?: string | null;
  isActive?: boolean;
}) {
  if (!title || !String(title).trim()) {
    throw new Error('title is required');
  }
  if (!description || !String(description).trim()) {
    throw new Error('description is required');
  }
  if (!category || !String(category).trim()) {
    throw new Error('category is required');
  }
  if (!stancePro || !String(stancePro).trim()) {
    throw new Error('stancePro is required');
  }
  if (!stanceCon || !String(stanceCon).trim()) {
    throw new Error('stanceCon is required');
  }

  const response = await network(
    store,
    'post',
    '/debate/ops/topics',
    {
      title: String(title).trim(),
      description: String(description).trim(),
      category: String(category).trim(),
      stancePro: String(stancePro).trim(),
      stanceCon: String(stanceCon).trim(),
      contextSeed: contextSeed == null ? null : String(contextSeed).trim() || null,
      isActive: !!isActive,
    },
    bearerHeader(token),
  );
  return responseData(response);
}

export async function actionUpdateDebateTopicOps({
  network,
  store,
  token,
  topicId,
  title,
  description,
  category,
  stancePro,
  stanceCon,
  contextSeed = null,
  isActive = true,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  topicId?: number | string | null;
  title?: string | null;
  description?: string | null;
  category?: string | null;
  stancePro?: string | null;
  stanceCon?: string | null;
  contextSeed?: string | null;
  isActive?: boolean;
}) {
  if (!topicId) {
    throw new Error('topicId is required');
  }
  if (!title || !String(title).trim()) {
    throw new Error('title is required');
  }
  if (!description || !String(description).trim()) {
    throw new Error('description is required');
  }
  if (!category || !String(category).trim()) {
    throw new Error('category is required');
  }
  if (!stancePro || !String(stancePro).trim()) {
    throw new Error('stancePro is required');
  }
  if (!stanceCon || !String(stanceCon).trim()) {
    throw new Error('stanceCon is required');
  }
  const response = await network(
    store,
    'put',
    `/debate/ops/topics/${Number(topicId)}`,
    {
      title: String(title).trim(),
      description: String(description).trim(),
      category: String(category).trim(),
      stancePro: String(stancePro).trim(),
      stanceCon: String(stanceCon).trim(),
      contextSeed: contextSeed == null ? null : String(contextSeed).trim() || null,
      isActive: !!isActive,
    },
    bearerHeader(token),
  );
  return responseData(response);
}

export async function actionCreateDebateSessionOps({
  network,
  store,
  token,
  topicId,
  status = 'scheduled',
  scheduledStartAt,
  endAt,
  maxParticipantsPerSide = 500,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  topicId?: number | string | null;
  status?: string | null;
  scheduledStartAt?: string | null;
  endAt?: string | null;
  maxParticipantsPerSide?: number | string | null;
}) {
  if (!topicId) {
    throw new Error('topicId is required');
  }
  if (!scheduledStartAt || !String(scheduledStartAt).trim()) {
    throw new Error('scheduledStartAt is required');
  }
  if (!endAt || !String(endAt).trim()) {
    throw new Error('endAt is required');
  }
  const response = await network(
    store,
    'post',
    '/debate/ops/sessions',
    {
      topicId: Number(topicId),
      status: String(status || 'scheduled').trim(),
      scheduledStartAt: String(scheduledStartAt).trim(),
      endAt: String(endAt).trim(),
      maxParticipantsPerSide: Number(maxParticipantsPerSide),
    },
    bearerHeader(token),
  );
  return responseData(response);
}

export async function actionUpdateDebateSessionOps({
  network,
  store,
  token,
  sessionId,
  status = null,
  scheduledStartAt = null,
  endAt = null,
  maxParticipantsPerSide = null,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  sessionId?: number | string | null;
  status?: string | null;
  scheduledStartAt?: string | null;
  endAt?: string | null;
  maxParticipantsPerSide?: number | string | null;
}) {
  if (!sessionId) {
    throw new Error('sessionId is required');
  }
  const payload: Record<string, unknown> = {};
  if (status != null && String(status).trim()) {
    payload.status = String(status).trim();
  }
  if (scheduledStartAt != null && String(scheduledStartAt).trim()) {
    payload.scheduledStartAt = String(scheduledStartAt).trim();
  }
  if (endAt != null && String(endAt).trim()) {
    payload.endAt = String(endAt).trim();
  }
  if (maxParticipantsPerSide != null) {
    payload.maxParticipantsPerSide = Number(maxParticipantsPerSide);
  }
  const response = await network(
    store,
    'put',
    `/debate/ops/sessions/${Number(sessionId)}`,
    payload,
    bearerHeader(token),
  );
  return responseData(response);
}
