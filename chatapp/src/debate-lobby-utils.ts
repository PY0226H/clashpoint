import type { DebateSessionDTO, LobbyLane, LobbyLaneFilter, SessionStatus } from './types/api';

const STATUS_OPEN = 'open';
const STATUS_RUNNING = 'running';
const STATUS_SCHEDULED = 'scheduled';
const STATUS_JUDGING = 'judging';
const STATUS_CLOSED = 'closed';
const STATUS_CANCELED = 'canceled';
const LANE_ALL: LobbyLaneFilter = 'all';
const LANE_LIVE: LobbyLane = 'live';
const LANE_UPCOMING: LobbyLane = 'upcoming';
const LANE_ENDED: LobbyLane = 'ended';

export function normalizeSessionStatus(status: SessionStatus | null | undefined): string {
  return String(status || '').trim().toLowerCase();
}

export function normalizeSessionTopicId(session: DebateSessionDTO | null | undefined): number | null {
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

export function isSessionEnded(status: SessionStatus | null | undefined): boolean {
  const normalized = normalizeSessionStatus(status);
  return (
    normalized === STATUS_JUDGING ||
    normalized === STATUS_CLOSED ||
    normalized === STATUS_CANCELED
  );
}

export function isSessionLive(status: SessionStatus | null | undefined): boolean {
  const normalized = normalizeSessionStatus(status);
  return normalized === STATUS_RUNNING;
}

export function isSessionJoinOpen(status: SessionStatus | null | undefined): boolean {
  const normalized = normalizeSessionStatus(status);
  return normalized === STATUS_OPEN || normalized === STATUS_SCHEDULED;
}

export function classifyLobbySessionLane(session: DebateSessionDTO | null | undefined): LobbyLane | 'unknown' {
  const status = normalizeSessionStatus(session?.status);
  if (isSessionLive(status)) {
    return LANE_LIVE;
  }
  if (status === STATUS_OPEN || status === STATUS_SCHEDULED) {
    return LANE_UPCOMING;
  }
  if (isSessionEnded(status)) {
    return LANE_ENDED;
  }
  return 'unknown';
}

export function splitLobbySessionsByLane(sessions: DebateSessionDTO[] = []): Record<LobbyLane | 'unknown', DebateSessionDTO[]> {
  const lanes: Record<LobbyLane | 'unknown', DebateSessionDTO[]> = {
    live: [],
    upcoming: [],
    ended: [],
    unknown: [],
  };
  for (const session of sessions) {
    const lane = classifyLobbySessionLane(session);
    lanes[lane].push(session);
  }
  return lanes;
}

export function normalizeLobbyLane(lane: LobbyLaneFilter | string | null | undefined): LobbyLaneFilter {
  const normalized = String(lane || '').trim().toLowerCase();
  if (
    normalized === LANE_LIVE ||
    normalized === LANE_UPCOMING ||
    normalized === LANE_ENDED
  ) {
    return normalized as LobbyLane;
  }
  return LANE_ALL;
}

export function matchesLaneFilter(session: DebateSessionDTO, laneFilter: LobbyLaneFilter | string | null | undefined): boolean {
  const lane = normalizeLobbyLane(laneFilter);
  if (lane === LANE_ALL) {
    return true;
  }
  return classifyLobbySessionLane(session) === lane;
}

function toTimeMs(value: string | null | undefined): number | null {
  const ms = Date.parse(value || '');
  return Number.isFinite(ms) ? ms : null;
}

export function compareLobbySessions(a: DebateSessionDTO, b: DebateSessionDTO): number {
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

  const aStart = toTimeMs(a?.scheduledStartAt || null) ?? -1;
  const bStart = toTimeMs(b?.scheduledStartAt || null) ?? -1;
  if (aStart !== bStart) {
    return bStart - aStart;
  }

  return Number(b?.id || 0) - Number(a?.id || 0);
}

export function matchesStatusFilter(session: DebateSessionDTO, statusFilter: string | null | undefined): boolean {
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

type FilterDebateSessionsOptions = {
  selectedTopicId?: string | number | null;
  statusFilter?: string;
  laneFilter?: LobbyLaneFilter | string;
  joinableOnly?: boolean;
  keyword?: string;
  topicTitleById?: (topicId: number | null) => string;
};

export function filterDebateSessions(
  sessions: DebateSessionDTO[] = [],
  {
    selectedTopicId = '',
    statusFilter = 'all',
    laneFilter = LANE_ALL,
    joinableOnly = false,
    keyword = '',
    topicTitleById = () => '',
  }: FilterDebateSessionsOptions = {},
): DebateSessionDTO[] {
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

      if (!matchesLaneFilter(session, laneFilter)) {
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
