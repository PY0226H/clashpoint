type HomeChannel = {
  id?: unknown;
  type?: unknown;
  name?: unknown;
};

type HomeTopic = {
  id?: unknown;
  title?: unknown;
  category?: unknown;
};

type HomeSession = {
  id?: unknown;
  topicId?: unknown;
  status?: unknown;
  joinable?: unknown;
};

type HomeSearchItem = {
  key: string;
  kind: 'chat' | 'topic' | 'session';
  title: string;
  subtitle: string;
  path: string;
  query: Record<string, string> | null;
  keywords: string[];
};

type BuildHomeSearchIndexInput = {
  channels?: HomeChannel[];
  topics?: HomeTopic[];
  sessions?: HomeSession[];
  topicTitleById?: (topicId: unknown) => string;
};

type FilterHomeSearchItemsOptions = {
  limit?: number;
};

export function normalizeHomeSearchQuery(raw: unknown): string {
  return String(raw ?? '').trim().toLowerCase();
}

export function summarizeDebateSessionStats(sessions: HomeSession[] = []) {
  const stats = {
    total: 0,
    joinable: 0,
    live: 0,
    upcoming: 0,
    ended: 0,
  };
  for (const session of sessions) {
    stats.total += 1;
    if (session?.joinable) {
      stats.joinable += 1;
    }
    const status = String(session?.status || '').trim().toLowerCase();
    if (status === 'running') {
      stats.live += 1;
    } else if (status === 'scheduled' || status === 'open') {
      stats.upcoming += 1;
    } else if (status === 'judging' || status === 'closed') {
      stats.ended += 1;
    }
  }
  return stats;
}

function toSearchKeywords(parts: unknown[] = []): string[] {
  return parts
    .map((part) => normalizeHomeSearchQuery(part))
    .filter((part) => part.length > 0);
}

export function buildHomeSearchIndex({
  channels = [],
  topics = [],
  sessions = [],
  topicTitleById = (_topicId: unknown) => '',
}: BuildHomeSearchIndexInput = {}): HomeSearchItem[] {
  const items: HomeSearchItem[] = [];

  for (const channel of channels) {
    const id = channel?.id;
    if (!id) {
      continue;
    }
    const type = String(channel?.type || '').trim().toLowerCase() || 'group';
    const name = String(channel?.name || '').trim() || `chat#${id}`;
    const label = type === 'single' ? '私聊会话' : '群聊会话';
    items.push({
      key: `chat:${id}`,
      kind: 'chat',
      title: name,
      subtitle: `${label} · chat#${id}`,
      path: '/chat',
      query: null,
      keywords: toSearchKeywords([name, label, type, `chat ${id}`]),
    });
  }

  for (const topic of topics) {
    const id = topic?.id;
    if (!id) {
      continue;
    }
    const title = String(topic?.title || '').trim() || `topic#${id}`;
    const category = String(topic?.category || '').trim() || 'debate';
    items.push({
      key: `topic:${id}`,
      kind: 'topic',
      title,
      subtitle: `辩题 · ${category}`,
      path: '/debate',
      query: { topic: String(id) },
      keywords: toSearchKeywords([title, category, `topic ${id}`]),
    });
  }

  for (const session of sessions) {
    const id = session?.id;
    if (!id) {
      continue;
    }
    const status = String(session?.status || '').trim() || 'unknown';
    const topicId = session?.topicId;
    const topicTitle = topicTitleById(topicId) || `topic#${topicId || '-'}`;
    items.push({
      key: `session:${id}`,
      kind: 'session',
      title: `Session ${id} · ${topicTitle}`,
      subtitle: `辩论场次 · ${status}`,
      path: `/debate/sessions/${id}`,
      query: null,
      keywords: toSearchKeywords([topicTitle, status, `session ${id}`]),
    });
  }

  return items;
}

export function filterHomeSearchItems(
  items: HomeSearchItem[] = [],
  query: unknown = '',
  { limit = 12 }: FilterHomeSearchItemsOptions = {},
): HomeSearchItem[] {
  const safeLimit = Number.isFinite(Number(limit)) ? Math.max(1, Number(limit)) : 12;
  const normalizedQuery = normalizeHomeSearchQuery(query);
  if (!normalizedQuery) {
    return items.slice(0, safeLimit);
  }

  return items
    .filter((item) => {
      const text = normalizeHomeSearchQuery(`${item?.title || ''} ${item?.subtitle || ''}`);
      if (text.includes(normalizedQuery)) {
        return true;
      }
      const keywords = Array.isArray(item?.keywords) ? item.keywords : [];
      return keywords.some((keyword) => keyword.includes(normalizedQuery));
    })
    .slice(0, safeLimit);
}
