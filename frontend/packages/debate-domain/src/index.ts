import { http, toApiError } from "@echoisle/api-client";

export type DebateSessionStatus = "scheduled" | "open" | "running" | "judging" | "closed" | "canceled";
export type DebateStatusFilter = DebateSessionStatus | "all";
export type DebateSide = "pro" | "con";

export type DebateTopic = {
  id: number;
  title: string;
  description: string;
  category: string;
  stancePro: string;
  stanceCon: string;
  contextSeed?: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
};

export type DebateSessionSummary = {
  id: number;
  topicId: number;
  status: string;
  scheduledStartAt: string;
  actualStartAt?: string | null;
  endAt: string;
  maxParticipantsPerSide: number;
  proCount: number;
  conCount: number;
  hotScore: number;
  joinable: boolean;
  createdAt: string;
  updatedAt: string;
};

export type DebateMessage = {
  id: number;
  sessionId: number;
  userId: number;
  side: string;
  content: string;
  createdAt: string;
};

export type DebatePinnedMessage = {
  id: number;
  sessionId: number;
  messageId: number;
  userId: number;
  side: string;
  content: string;
  costCoins: number;
  pinSeconds: number;
  pinnedAt: string;
  expiresAt: string;
  status: string;
};

export type PinDebateMessageOutput = {
  pinId: number;
  sessionId: number;
  messageId: number;
  ledgerId: number;
  debitedCoins: number;
  walletBalance: number;
  pinSeconds: number;
  expiresAt: string;
  newlyPinned: boolean;
};

export type ListDebateTopicsOutput = {
  items: DebateTopic[];
  hasMore: boolean;
  nextCursor?: string | null;
  revision: string;
};

export type ListDebateSessionsOutput = {
  items: DebateSessionSummary[];
  hasMore: boolean;
  nextCursor?: string | null;
  revision: string;
};

export type JoinDebateSessionOutput = {
  sessionId: number;
  side: DebateSide;
  newlyJoined: boolean;
  proCount: number;
  conCount: number;
};

export type ListDebateMessagesOutput = {
  items: DebateMessage[];
  hasMore: boolean;
  nextCursor?: number | null;
  revision: string;
};

export type ListDebatePinnedMessagesOutput = {
  items: DebatePinnedMessage[];
  hasMore: boolean;
  nextCursor?: string | null;
  revision: string;
};

export type WalletBalanceOutput = {
  userId: number;
  balance: number;
  walletRevision: string;
  walletInitialized: boolean;
};

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | { [key: string]: JsonValue }
  | JsonValue[];

export type RequestDebateJudgeJobOutput = {
  accepted: boolean;
  sessionId: number;
  status: string;
  reason?: string | null;
  queuedPhaseJobs: number;
  queuedFinalJob: boolean;
  triggerMode: string;
};

export type JudgeFinalReportDetail = {
  finalReportId: number;
  finalJobId: number;
  winner: string;
  proScore: number;
  conScore: number;
  finalRationale: string;
  winnerFirst?: string | null;
  winnerSecond?: string | null;
  rejudgeTriggered: boolean;
  needsDrawVote: boolean;
  dimensionScores?: JsonValue;
  verdictEvidenceRefs?: JsonValue[];
  phaseRollupSummary?: JsonValue[];
  retrievalSnapshotRollup?: JsonValue[];
  judgeTrace?: JsonValue;
  auditAlerts?: JsonValue[];
  errorCodes?: string[];
  degradationLevel?: number;
  createdAt: string;
};

export type JudgeFinalDispatchDiagnostics = {
  finalJobId: number;
  status: string;
  phaseStartNo: number;
  phaseEndNo: number;
  dispatchAttempts: number;
  lastDispatchAt?: string | null;
  errorMessage?: string | null;
  errorCode?: string | null;
  contractFailureType?: string | null;
  contractFailureHint?: string | null;
  contractFailureAction?: string | null;
  contractViolationBlocked: boolean;
};

export type JudgeFinalDispatchFailureTypeCount = {
  failureType: string;
  count: number;
};

export type JudgeFinalDispatchFailureStats = {
  totalFailedJobs: number;
  unknownFailedJobs: number;
  byType: JudgeFinalDispatchFailureTypeCount[];
};

export type GetDebateJudgeReportOutput = {
  sessionId: number;
  status: string;
  finalDispatchDiagnostics?: JudgeFinalDispatchDiagnostics | null;
  finalDispatchFailureStats?: JudgeFinalDispatchFailureStats | null;
  finalReport?: JudgeFinalReportDetail | null;
};

export type DrawVoteDetail = {
  voteId: number;
  finalReportId: number;
  status: string;
  resolution: string;
  decisionSource: string;
  thresholdPercent: number;
  eligibleVoters: number;
  requiredVoters: number;
  participatedVoters: number;
  agreeVotes: number;
  disagreeVotes: number;
  votingEndsAt: string;
  decidedAt?: string | null;
  myVote?: boolean | null;
  rematchSessionId?: number | null;
};

export type GetDebateDrawVoteOutput = {
  sessionId: number;
  status: string;
  vote?: DrawVoteDetail | null;
};

export type SubmitDebateDrawVoteOutput = {
  sessionId: number;
  status: string;
  vote: DrawVoteDetail;
  newlySubmitted: boolean;
};

export function normalizeDebateStatusFilter(value: string | null | undefined): DebateStatusFilter {
  switch ((value || "").trim().toLowerCase()) {
    case "scheduled":
      return "scheduled";
    case "open":
      return "open";
    case "running":
      return "running";
    case "judging":
      return "judging";
    case "closed":
      return "closed";
    case "canceled":
      return "canceled";
    default:
      return "all";
  }
}

export function normalizeDebateSide(value: string | null | undefined): DebateSide {
  return (value || "").trim().toLowerCase() === "con" ? "con" : "pro";
}

export function toDebateDomainError(error: unknown): string {
  return toApiError(error);
}

export async function listDebateTopics(input?: {
  category?: string;
  activeOnly?: boolean;
  limit?: number;
}): Promise<ListDebateTopicsOutput> {
  const response = await http.get<ListDebateTopicsOutput>("/debate/topics", {
    params: {
      category: input?.category,
      activeOnly: input?.activeOnly ?? true,
      limit: input?.limit ?? 8
    }
  });
  return response.data;
}

export async function listDebateSessions(input?: {
  status?: DebateStatusFilter;
  topicId?: number;
  limit?: number;
}): Promise<ListDebateSessionsOutput> {
  const status = normalizeDebateStatusFilter(input?.status);
  const response = await http.get<ListDebateSessionsOutput>("/debate/sessions", {
    params: {
      status: status === "all" ? undefined : status,
      topicId: input?.topicId,
      limit: input?.limit ?? 20
    }
  });
  return response.data;
}

export async function joinDebateSession(
  sessionId: number,
  side: DebateSide
): Promise<JoinDebateSessionOutput> {
  const response = await http.post<JoinDebateSessionOutput>(`/debate/sessions/${sessionId}/join`, {
    side: normalizeDebateSide(side)
  });
  return response.data;
}

export async function listDebateMessages(
  sessionId: number,
  input?: { lastId?: number; limit?: number }
): Promise<ListDebateMessagesOutput> {
  const response = await http.get<ListDebateMessagesOutput>(`/debate/sessions/${sessionId}/messages`, {
    params: {
      lastId: input?.lastId,
      limit: input?.limit ?? 80
    }
  });
  return response.data;
}

export async function listDebatePinnedMessages(
  sessionId: number,
  input?: { activeOnly?: boolean; cursor?: string; limit?: number }
): Promise<ListDebatePinnedMessagesOutput> {
  const response = await http.get<ListDebatePinnedMessagesOutput>(`/debate/sessions/${sessionId}/pins`, {
    params: {
      activeOnly: input?.activeOnly ?? true,
      cursor: input?.cursor,
      limit: input?.limit ?? 20
    }
  });
  return response.data;
}

export async function createDebateMessage(
  sessionId: number,
  content: string
): Promise<DebateMessage> {
  const response = await http.post<DebateMessage>(`/debate/sessions/${sessionId}/messages`, {
    content: String(content || "").trim()
  });
  return response.data;
}

function buildPinIdempotencyKey(): string {
  if (typeof globalThis !== "undefined" && typeof globalThis.crypto?.randomUUID === "function") {
    return `pin_${globalThis.crypto.randomUUID()}`;
  }
  return `pin_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export async function pinDebateMessage(
  messageId: number,
  pinSeconds: number,
  input?: { idempotencyKey?: string }
): Promise<PinDebateMessageOutput> {
  const normalizedPinSeconds = Math.max(1, Math.floor(Number(pinSeconds) || 60));
  const response = await http.post<PinDebateMessageOutput>(`/debate/messages/${messageId}/pin`, {
    pinSeconds: normalizedPinSeconds,
    idempotencyKey: String(input?.idempotencyKey || "").trim() || buildPinIdempotencyKey()
  });
  return response.data;
}

export async function getWalletBalance(): Promise<WalletBalanceOutput> {
  const response = await http.get<WalletBalanceOutput>("/pay/wallet");
  return response.data;
}

export async function requestDebateJudgeJob(
  sessionId: number,
  input?: { allowRejudge?: boolean }
): Promise<RequestDebateJudgeJobOutput> {
  const response = await http.post<RequestDebateJudgeJobOutput>(`/debate/sessions/${sessionId}/judge/jobs`, {
    allowRejudge: Boolean(input?.allowRejudge)
  });
  return response.data;
}

export async function getDebateJudgeReport(
  sessionId: number,
  input?: { maxStageCount?: number; stageOffset?: number }
): Promise<GetDebateJudgeReportOutput> {
  const response = await http.get<GetDebateJudgeReportOutput>(`/debate/sessions/${sessionId}/judge-report`, {
    params: {
      maxStageCount: input?.maxStageCount,
      stageOffset: input?.stageOffset
    }
  });
  return response.data;
}

export async function getDebateDrawVoteStatus(sessionId: number): Promise<GetDebateDrawVoteOutput> {
  const response = await http.get<GetDebateDrawVoteOutput>(`/debate/sessions/${sessionId}/draw-vote`);
  return response.data;
}

export async function submitDebateDrawVote(
  sessionId: number,
  agreeDraw: boolean
): Promise<SubmitDebateDrawVoteOutput> {
  const response = await http.post<SubmitDebateDrawVoteOutput>(`/debate/sessions/${sessionId}/draw-vote/ballots`, {
    agreeDraw: Boolean(agreeDraw)
  });
  return response.data;
}

export function normalizeDebateMessage(raw: Partial<DebateMessage> | null | undefined): DebateMessage | null {
  if (!raw) {
    return null;
  }
  const id = Number(raw.id);
  if (!Number.isFinite(id) || id <= 0) {
    return null;
  }
  return {
    id,
    sessionId: Number(raw.sessionId || 0),
    userId: Number(raw.userId || 0),
    side: String(raw.side || "unknown"),
    content: String(raw.content || ""),
    createdAt: String(raw.createdAt || new Date().toISOString())
  };
}

export function mergeDebateMessages(
  currentMessages: DebateMessage[],
  incomingMessages: Array<Partial<DebateMessage> | null | undefined>
): DebateMessage[] {
  const map = new Map<number, DebateMessage>();
  for (const item of currentMessages) {
    const normalized = normalizeDebateMessage(item);
    if (!normalized) {
      continue;
    }
    map.set(normalized.id, normalized);
  }
  for (const item of incomingMessages) {
    const normalized = normalizeDebateMessage(item);
    if (!normalized) {
      continue;
    }
    map.set(normalized.id, normalized);
  }
  return [...map.values()].sort((a, b) => a.id - b.id);
}

export function getOldestDebateMessageId(messages: DebateMessage[]): number | null {
  let oldest: number | null = null;
  for (const message of messages) {
    if (!Number.isFinite(message.id) || message.id <= 0) {
      continue;
    }
    if (oldest === null || message.id < oldest) {
      oldest = message.id;
    }
  }
  return oldest;
}
