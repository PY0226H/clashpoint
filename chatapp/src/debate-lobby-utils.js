const STATUS_OPEN = 'open';
const STATUS_RUNNING = 'running';
const STATUS_SCHEDULED = 'scheduled';
const STATUS_JUDGING = 'judging';
const STATUS_CLOSED = 'closed';
const STATUS_CANCELED = 'canceled';

export function normalizeSessionStatus(status) {
  return String(status || '').trim().toLowerCase();
}

export function normalizeSessionTopicId(session) {
  const fromCamel = session?.topicId;
  if (Number.isFinite(Number(fromCamel))) {
    return Number(fromCamel);
  }
  const fromSnake = session?.topic_id;
  if (Number.isFinite(Number(fromSnake))) {
    return Number(fromSnake);
  }
  return null;
}

export function isSessionEnded(status) {
  const normalized = normalizeSessionStatus(status);
  return (
    normalized === STATUS_JUDGING ||
    normalized === STATUS_CLOSED ||
    normalized === STATUS_CANCELED
  );
}

export function isSessionLive(status) {
  const normalized = normalizeSessionStatus(status);
  return normalized === STATUS_RUNNING;
}

export function isSessionJoinOpen(status) {
  const normalized = normalizeSessionStatus(status);
  return normalized === STATUS_OPEN || normalized === STATUS_SCHEDULED;
}

export function classifyLobbySessionLane(session) {
  const status = normalizeSessionStatus(session?.status);
  if (isSessionLive(status)) {
    return 'live';
  }
  if (status === STATUS_OPEN || status === STATUS_SCHEDULED) {
    return 'upcoming';
  }
  if (isSessionEnded(status)) {
    return 'ended';
  }
  return 'unknown';
}

export function splitLobbySessionsByLane(sessions = []) {
  const lanes = {
    live: [],
    upcoming: [],
    ended: [],
    unknown: [],
  };
  for (const session of sessions) {
    const lane = classifyLobbySessionLane(session);
    if (!lanes[lane]) {
      lanes.unknown.push(session);
      continue;
    }
    lanes[lane].push(session);
  }
  return lanes;
}

function toTimeMs(value) {
  const ms = Date.parse(value || '');
  return Number.isFinite(ms) ? ms : null;
}

export function compareLobbySessions(a, b) {
  const aJoinable = a?.joinable ? 1 : 0;
  const bJoinable = b?.joinable ? 1 : 0;
  if (aJoinable !== bJoinable) {
    return bJoinable - aJoinable;
  }

  const aLive = isSessionLive(a?.status) ? 1 : 0;
  const bLive = isSessionLive(b?.status) ? 1 : 0;
  if (aLive !== bLive) {
    return bLive - aLive;
  }

  const aStart = toTimeMs(a?.scheduledStartAt) ?? -1;
  const bStart = toTimeMs(b?.scheduledStartAt) ?? -1;
  if (aStart !== bStart) {
    return bStart - aStart;
  }

  return Number(b?.id || 0) - Number(a?.id || 0);
}

export function matchesStatusFilter(session, statusFilter) {
  const filter = String(statusFilter || 'all').toLowerCase();
  if (filter === 'all') {
    return true;
  }

  const status = normalizeSessionStatus(session?.status);
  if (filter === 'ended') {
    return isSessionEnded(status);
  }
  if (filter === 'live') {
    return isSessionLive(status);
  }
  if (filter === 'joinable') {
    return !!session?.joinable || status === STATUS_OPEN || status === STATUS_SCHEDULED;
  }
  if (filter === 'upcoming') {
    return status === STATUS_SCHEDULED;
  }
  return status === filter;
}

export function filterDebateSessions(
  sessions = [],
  {
    selectedTopicId = '',
    statusFilter = 'all',
    joinableOnly = false,
    keyword = '',
    topicTitleById = () => '',
  } = {},
) {
  const topicIdFilter = String(selectedTopicId || '').trim();
  const kw = String(keyword || '').trim().toLowerCase();

  return sessions
    .filter((session) => {
      if (topicIdFilter) {
        const sessionTopicId = normalizeSessionTopicId(session);
        if (String(sessionTopicId) !== topicIdFilter) {
          return false;
        }
      }

      if (!matchesStatusFilter(session, statusFilter)) {
        return false;
      }

      if (joinableOnly && !session?.joinable) {
        return false;
      }

      if (!kw) {
        return true;
      }
      const title = String(topicTitleById(normalizeSessionTopicId(session)) || '').toLowerCase();
      return title.includes(kw);
    })
    .sort(compareLobbySessions);
}
