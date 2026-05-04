export type DebateRoomClientMessage =
  | { type: "ping" }
  | { type: "pong" }
  | { type: "ack"; eventSeq: number };

export const DEBATE_NPC_ACTION_CREATED_EVENT = "DebateNpcActionCreated" as const;

export type DebateRoomKnownEventName =
  | "DebateParticipantJoined"
  | "DebateSessionStatusChanged"
  | "DebateMessageCreated"
  | "DebateMessagePinned"
  | typeof DEBATE_NPC_ACTION_CREATED_EVENT
  | "DebateJudgeReportReady"
  | "DebateDrawVoteResolved";

export type DebateRoomEventName = DebateRoomKnownEventName | (string & {});

export type DebateNpcActionCreatedRoomPayload = {
  event: typeof DEBATE_NPC_ACTION_CREATED_EVENT;
  actionId: number;
  actionUid: string;
  sessionId: number;
  npcId: string;
  displayName: string;
  actionType:
    | "speak"
    | "praise"
    | "effect"
    | "pause_suggestion"
    | "state_changed";
  publicText?: string | null;
  targetMessageId?: number | null;
  targetUserId?: number | null;
  targetSide?: "pro" | "con" | null;
  effectKind?: string | null;
  npcStatus?: string | null;
  reasonCode?: string | null;
  createdAt: string;
};

export type DebateRoomKnownEventPayload = DebateNpcActionCreatedRoomPayload;

export type DebateRoomWelcomeMessage = {
  type: "welcome";
  sessionId: number;
  userId: number;
  baselineAckSeq: number;
  lastEventSeq: number;
  replayCount: number;
  heartbeatIntervalMs: number;
  heartbeatTimeoutMs: number;
};

export type DebateRoomEventMessage = {
  type: "roomEvent";
  eventSeq: number;
  eventAtMs: number;
  eventName: DebateRoomEventName;
  payload: DebateRoomKnownEventPayload | Record<string, unknown>;
};

export type DebateRoomSyncRequiredMessage = {
  type: "syncRequired";
  reason: string;
  skipped: number;
  expectedFromSeq?: number;
  gapFromSeq?: number;
  gapToSeq?: number;
  suggestedLastAckSeq: number;
  latestEventSeq?: number;
  mustSnapshot: boolean;
  reconnectAfterMs: number;
  strategy: string;
};

export type DebateRoomPingPongMessage = {
  type: "ping" | "pong";
  ts?: number;
};

export type DebateRoomServerMessage =
  | DebateRoomWelcomeMessage
  | DebateRoomEventMessage
  | DebateRoomSyncRequiredMessage
  | DebateRoomPingPongMessage;

export const DEFAULT_NOTIFY_BASE = "http://localhost:6687/events";
const DEFAULT_WS_RECONNECT_BASE_MS = 1200;
const DEFAULT_WS_RECONNECT_MAX_MS = 15000;
const DEFAULT_WS_RECONNECT_JITTER_RATIO = 0.2;

function toWsProtocol(protocol: string): string {
  if (protocol === "https:") {
    return "wss:";
  }
  if (protocol === "http:") {
    return "ws:";
  }
  if (protocol === "wss:" || protocol === "ws:") {
    return protocol;
  }
  return "ws:";
}

function trimSlash(value: string): string {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

function normalizeNotifyBasePath(pathname: string): string {
  if (!pathname || pathname === "/") {
    return "";
  }
  const trimmed = trimSlash(pathname);
  if (trimmed.endsWith("/events")) {
    return trimmed.slice(0, -"/events".length);
  }
  return trimmed;
}

export function buildNotifyTicketProtocol(notifyTicket: string): string {
  const normalized = String(notifyTicket || "").trim();
  if (!normalized) {
    throw new Error("notifyTicket is required");
  }
  return `notify-ticket.${normalized}`;
}

export function buildDebateRoomWsUrl(input: {
  notifyBase?: string;
  sessionId: number;
  lastAckSeq?: number | null;
}): string {
  if (!input.sessionId) {
    throw new Error("sessionId is required");
  }
  const base = String(input.notifyBase || DEFAULT_NOTIFY_BASE).trim() || DEFAULT_NOTIFY_BASE;
  const parsed = new URL(base);
  parsed.protocol = toWsProtocol(parsed.protocol);
  const basePath = normalizeNotifyBasePath(parsed.pathname);
  parsed.pathname = `${basePath}/ws/debate/${input.sessionId}`;
  parsed.search = "";
  const normalizedLastAckSeq = Number(input.lastAckSeq);
  if (input.lastAckSeq != null && Number.isFinite(normalizedLastAckSeq) && normalizedLastAckSeq >= 0) {
    parsed.searchParams.set("lastAckSeq", String(Math.floor(normalizedLastAckSeq)));
  }
  return parsed.toString();
}

function toNonNegativeInt(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return fallback;
  }
  return Math.floor(parsed);
}

export function parseDebateRoomServerMessage(raw: string): DebateRoomServerMessage | null {
  if (!raw || !String(raw).trim()) {
    return null;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return null;
  }
  const record = parsed as Record<string, unknown>;
  const type = String(record.type || "").trim();
  if (!type) {
    return null;
  }

  if (type === "welcome") {
    return {
      type,
      sessionId: toNonNegativeInt(record.sessionId ?? record.session_id),
      userId: toNonNegativeInt(record.userId ?? record.user_id),
      baselineAckSeq: toNonNegativeInt(record.baselineAckSeq ?? record.baseline_ack_seq),
      lastEventSeq: toNonNegativeInt(record.lastEventSeq ?? record.last_event_seq),
      replayCount: toNonNegativeInt(record.replayCount ?? record.replay_count),
      heartbeatIntervalMs: toNonNegativeInt(record.heartbeatIntervalMs ?? record.heartbeat_interval_ms),
      heartbeatTimeoutMs: toNonNegativeInt(record.heartbeatTimeoutMs ?? record.heartbeat_timeout_ms)
    };
  }

  if (type === "roomEvent") {
    const payload = record.payload;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      return null;
    }
    return {
      type,
      eventSeq: toNonNegativeInt(record.eventSeq ?? record.event_seq),
      eventAtMs: Number(record.eventAtMs ?? record.event_at_ms) || 0,
      eventName: String(record.eventName ?? record.event_name ?? ""),
      payload: payload as Record<string, unknown>
    };
  }

  if (type === "syncRequired") {
    return {
      type,
      reason: String(record.reason || ""),
      skipped: toNonNegativeInt(record.skipped),
      expectedFromSeq: toOptionalNonNegativeInt(record.expectedFromSeq ?? record.expected_from_seq),
      gapFromSeq: toOptionalNonNegativeInt(record.gapFromSeq ?? record.gap_from_seq),
      gapToSeq: toOptionalNonNegativeInt(record.gapToSeq ?? record.gap_to_seq),
      suggestedLastAckSeq: toNonNegativeInt(record.suggestedLastAckSeq ?? record.suggested_last_ack_seq),
      latestEventSeq: toOptionalNonNegativeInt(record.latestEventSeq ?? record.latest_event_seq),
      mustSnapshot: record.mustSnapshot !== false && record.must_snapshot !== false,
      reconnectAfterMs: toNonNegativeInt(record.reconnectAfterMs ?? record.reconnect_after_ms),
      strategy: String(record.strategy || "snapshot_then_reconnect")
    };
  }

  if (type === "ping" || type === "pong") {
    return {
      type,
      ts: Number(record.ts) || undefined
    };
  }

  return null;
}

function toOptionalNonNegativeInt(value: unknown): number | undefined {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return undefined;
  }
  return Math.floor(parsed);
}

export function buildDebateRoomClientMessage(message: DebateRoomClientMessage): string {
  return JSON.stringify(message);
}

export function buildDebateRoomAckMessage(eventSeq: number | null | undefined): string | null {
  const normalized = toOptionalNonNegativeInt(eventSeq);
  if (normalized == null) {
    return null;
  }
  return buildDebateRoomClientMessage({
    type: "ack",
    eventSeq: normalized
  });
}

export function computeWsReconnectDelayMs(
  attempt: number,
  input?: {
    baseMs?: number;
    maxMs?: number;
    jitterRatio?: number;
    randomValue?: number;
  }
): number {
  const normalizedBaseMs = Math.max(1, Number(input?.baseMs) || DEFAULT_WS_RECONNECT_BASE_MS);
  const normalizedMaxMs = Math.max(normalizedBaseMs, Number(input?.maxMs) || DEFAULT_WS_RECONNECT_MAX_MS);
  const normalizedAttempt = Math.max(1, Number(attempt) || 1);
  const normalizedJitterRatio = Math.max(0, Number(input?.jitterRatio) || DEFAULT_WS_RECONNECT_JITTER_RATIO);
  const random = Math.max(0, Math.min(1, Number(input?.randomValue) || Math.random()));

  const expDelay = Math.min(normalizedMaxMs, normalizedBaseMs * 2 ** (normalizedAttempt - 1));
  const jitterWindow = Math.floor(expDelay * normalizedJitterRatio);
  if (jitterWindow <= 0) {
    return Math.floor(expDelay);
  }
  const offset = Math.floor(random * (jitterWindow * 2 + 1)) - jitterWindow;
  return Math.max(normalizedBaseMs, Math.min(normalizedMaxMs, Math.floor(expDelay + offset)));
}
