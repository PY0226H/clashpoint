type CommitFn = (type: string, payload?: unknown) => void;

type NetworkFn = (
  store: unknown,
  method: string,
  url: string,
  data?: unknown,
  headers?: Record<string, string>,
  allowRefreshRetry?: boolean,
) => Promise<{ data?: unknown } | unknown>;

type LoadStateFn = (
  response: unknown,
  store: unknown,
  commit: CommitFn,
) => Promise<unknown>;

function responseData<T = unknown>(response: unknown): T | undefined {
  const value = response as { data?: T } | undefined;
  return value?.data;
}

export async function actionSendSmsCodeV2({
  network,
  store,
  phone,
  scene,
}: {
  network: NetworkFn;
  store: unknown;
  phone: string;
  scene: string;
}) {
  const response = await network(store, 'post', '/auth/v2/sms/send', {
    phone,
    scene,
  });
  return responseData(response);
}

export async function actionSignupPhoneV2({
  network,
  store,
  loadState,
  commit,
  phone,
  smsCode,
  password,
  fullname,
}: {
  network: NetworkFn;
  store: unknown;
  loadState: LoadStateFn;
  commit: CommitFn;
  phone: string;
  smsCode: string;
  password: string;
  fullname: string;
}) {
  const response = await network(store, 'post', '/auth/v2/signup/phone', {
    phone,
    smsCode,
    password,
    fullname,
  });
  return loadState(response, store, commit);
}

export async function actionSignupEmailV2({
  network,
  store,
  loadState,
  commit,
  email,
  phone,
  smsCode,
  password,
  fullname,
}: {
  network: NetworkFn;
  store: unknown;
  loadState: LoadStateFn;
  commit: CommitFn;
  email: string;
  phone: string;
  smsCode: string;
  password: string;
  fullname: string;
}) {
  const response = await network(store, 'post', '/auth/v2/signup/email', {
    email,
    phone,
    smsCode,
    password,
    fullname,
  });
  return loadState(response, store, commit);
}

export async function actionSigninPasswordV2({
  network,
  store,
  loadState,
  commit,
  account,
  accountType,
  password,
}: {
  network: NetworkFn;
  store: unknown;
  loadState: LoadStateFn;
  commit: CommitFn;
  account: string;
  accountType: string;
  password: string;
}) {
  const response = await network(store, 'post', '/auth/v2/signin/password', {
    account,
    accountType,
    password,
  });
  return loadState(response, store, commit);
}

export async function actionSigninOtpV2({
  network,
  store,
  loadState,
  commit,
  phone,
  smsCode,
}: {
  network: NetworkFn;
  store: unknown;
  loadState: LoadStateFn;
  commit: CommitFn;
  phone: string;
  smsCode: string;
}) {
  const response = await network(store, 'post', '/auth/v2/signin/otp', {
    phone,
    smsCode,
  });
  return loadState(response, store, commit);
}

export async function actionWechatChallengeV2({
  network,
  store,
}: {
  network: NetworkFn;
  store: unknown;
}) {
  const response = await network(store, 'post', '/auth/v2/wechat/challenge');
  return responseData(response);
}

export async function actionWechatSigninV2({
  network,
  store,
  loadState,
  commit,
  state,
  code,
}: {
  network: NetworkFn;
  store: unknown;
  loadState: LoadStateFn;
  commit: CommitFn;
  state: string;
  code: string;
}) {
  const response = await network(store, 'post', '/auth/v2/wechat/signin', {
    state,
    code,
  });
  const data = (responseData<Record<string, unknown>>(response) || {}) as Record<string, unknown>;
  if (data.bindRequired) {
    return data;
  }
  const authLike = {
    data: {
      accessToken: data.accessToken,
      tokenType: data.tokenType,
      expiresInSecs: data.expiresInSecs,
      user: data.user,
    },
  };
  const user = await loadState(authLike, store, commit);
  return {
    bindRequired: false,
    user,
  };
}

export async function actionWechatBindPhoneV2({
  network,
  store,
  loadState,
  commit,
  wechatTicket,
  phone,
  smsCode,
  password,
  fullname,
}: {
  network: NetworkFn;
  store: unknown;
  loadState: LoadStateFn;
  commit: CommitFn;
  wechatTicket: string;
  phone: string;
  smsCode: string;
  password?: string | null;
  fullname?: string | null;
}) {
  const payload: Record<string, unknown> = {
    wechatTicket,
    phone,
    smsCode,
    fullname,
  };
  if (password && String(password).trim()) {
    payload.password = String(password).trim();
  }
  const response = await network(store, 'post', '/auth/v2/wechat/bind-phone', payload);
  const data = (responseData<Record<string, unknown>>(response) || {}) as Record<string, unknown>;
  const authLike = {
    data: {
      accessToken: data.accessToken,
      tokenType: data.tokenType,
      expiresInSecs: data.expiresInSecs,
      user: data.user,
    },
  };
  const user = await loadState(authLike, store, commit);
  return {
    bindRequired: false,
    user,
  };
}

export async function actionBindPhoneV2({
  network,
  store,
  commit,
  token,
  phone,
  smsCode,
}: {
  network: NetworkFn;
  store: unknown;
  commit: CommitFn;
  token?: string | null;
  phone: string;
  smsCode: string;
}) {
  const response = await network(
    store,
    'post',
    '/auth/v2/phone/bind',
    {
      phone,
      smsCode,
    },
    token ? { Authorization: `Bearer ${token}` } : {},
  );
  const ret = (responseData<Record<string, unknown>>(response) || {}) as Record<string, unknown>;
  if (ret?.user) {
    localStorage.setItem('user', JSON.stringify(ret.user));
    commit('setUser', ret.user);
  }
  return ret;
}

export async function actionSetPasswordV2({
  network,
  store,
  password,
  smsCode,
}: {
  network: NetworkFn;
  store: unknown;
  password: string;
  smsCode: string;
}) {
  const payload = {
    password: String(password || '').trim(),
    smsCode: String(smsCode || '').trim(),
  };
  const response = await network(store, 'post', '/auth/v2/password/set', payload);
  return responseData<Record<string, unknown>>(response) || { updated: false };
}

export async function actionListOpsRoleAssignments({
  network,
  store,
  token,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
}) {
  const response = await network(store, 'get', '/debate/ops/rbac/roles', null, {
    Authorization: `Bearer ${token || ''}`,
  });
  return responseData<Record<string, unknown>>(response) || { items: [] };
}

export async function actionGetOpsRbacMe({
  network,
  store,
  commit,
  token,
}: {
  network: NetworkFn;
  store: unknown;
  commit: CommitFn;
  token?: string | null;
}) {
  const response = await network(store, 'get', '/debate/ops/rbac/me', null, {
    Authorization: `Bearer ${token || ''}`,
  });
  const payload = responseData(response) || null;
  commit('setOpsRbacMe', payload);
  return payload;
}

export async function actionUpsertOpsRoleAssignment({
  network,
  store,
  token,
  userId,
  role,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  userId: number;
  role: string;
}) {
  if (!userId) {
    throw new Error('userId is required');
  }
  if (!role || !String(role).trim()) {
    throw new Error('role is required');
  }
  const response = await network(
    store,
    'put',
    `/debate/ops/rbac/roles/${Number(userId)}`,
    { role: String(role).trim() },
    {
      Authorization: `Bearer ${token || ''}`,
    },
  );
  return responseData(response);
}

export async function actionRevokeOpsRoleAssignment({
  network,
  store,
  token,
  userId,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  userId: number;
}) {
  if (!userId) {
    throw new Error('userId is required');
  }
  const response = await network(
    store,
    'delete',
    `/debate/ops/rbac/roles/${Number(userId)}`,
    null,
    {
      Authorization: `Bearer ${token || ''}`,
    },
  );
  return responseData(response);
}

export async function actionRequestJudgeRejudgeOps({
  network,
  store,
  token,
  sessionId,
}: {
  network: NetworkFn;
  store: unknown;
  token?: string | null;
  sessionId: number;
}) {
  if (!sessionId) {
    throw new Error('sessionId is required');
  }
  const response = await network(
    store,
    'post',
    `/debate/ops/sessions/${Number(sessionId)}/judge/rejudge`,
    {},
    {
      Authorization: `Bearer ${token || ''}`,
    },
  );
  return responseData(response);
}
