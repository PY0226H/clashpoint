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

function responseData<T = unknown>(response: unknown): T | undefined {
  const value = response as { data?: T } | undefined;
  return value?.data;
}

type AccessTickets = {
  fileToken?: string;
  notifyToken?: string;
  expiresInSecs?: number;
  expireAt?: number;
};

export async function actionLoadUserState({
  commit,
  dispatch,
  getUser,
}: {
  commit: CommitFn;
  dispatch: DispatchFn;
  getUser: () => unknown;
}) {
  commit('loadUserState');
  if (!getUser()) {
    return;
  }
  try {
    await dispatch('refreshSession');
    await dispatch('initSSE');
  } catch (_error) {
    await dispatch('logout', { skipRemote: true });
  }
}

export async function actionRefreshSession({
  network,
  store,
  commit,
  dispatch,
}: {
  network: NetworkFn;
  store: unknown;
  commit: CommitFn;
  dispatch: DispatchFn;
}) {
  const response = await network(store, 'post', '/auth/refresh', null, {}, false);
  const accessToken = responseData<{ accessToken?: string }>(response)?.accessToken;
  if (!accessToken) {
    throw new Error('missing accessToken from refresh response');
  }
  commit('setToken', accessToken);
  await dispatch('refreshAccessTickets');
  return accessToken;
}

export async function actionRefreshAccessTickets({
  network,
  store,
  commit,
  token,
  accessTickets,
}: {
  network: NetworkFn;
  store: unknown;
  commit: CommitFn;
  token?: string | null;
  accessTickets?: AccessTickets | null;
}) {
  if (!token) {
    commit('setAccessTickets', null);
    return null;
  }
  const now = Date.now();
  const expireAt = accessTickets?.expireAt || 0;
  if (expireAt > now + 30_000) {
    return accessTickets;
  }

  const response = await network(store, 'post', '/tickets', null, {
    Authorization: `Bearer ${token}`,
  });
  const data = responseData<{
    fileToken: string;
    notifyToken: string;
    expiresInSecs: number;
  }>(response);
  const tickets = {
    fileToken: data?.fileToken,
    notifyToken: data?.notifyToken,
    expiresInSecs: data?.expiresInSecs,
    expireAt: now + (data?.expiresInSecs || 0) * 1000,
  };
  commit('setAccessTickets', tickets);
  return tickets;
}
