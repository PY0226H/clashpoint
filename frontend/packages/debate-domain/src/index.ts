import { http, toApiError } from "@echoisle/api-client";

export type DebateSessionStatus =
  | "scheduled"
  | "open"
  | "running"
  | "judging"
  | "closed"
  | "canceled";
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
  reviewDecisionSync?: JudgeReviewDecisionSync | null;
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

export type JudgePublicVerificationStatus =
  | "ready"
  | "not_ready"
  | "absent"
  | "proxy_error"
  | (string & {});

export type JudgePublicVerificationReadiness = {
  ready: boolean;
  status: string;
  blockers: string[];
  externalizable?: boolean;
  [key: string]: JsonValue | undefined;
};

export type JudgePublicVerificationCacheProfile = {
  cacheable: boolean;
  ttlSeconds: number;
  staleWhileRevalidateSeconds: number;
  cacheKey?: string;
  varyBy?: string[];
  [key: string]: JsonValue | undefined;
};

export type GetDebateJudgePublicVerificationOutput = {
  sessionId: number;
  status: JudgePublicVerificationStatus;
  statusReason: string;
  caseId?: number | null;
  dispatchType: "final" | "phase" | (string & {});
  verificationReadiness: JudgePublicVerificationReadiness;
  cacheProfile: JudgePublicVerificationCacheProfile;
  publicVerify?: JsonValue;
};

export type DebateJudgePublicVerificationView = {
  state: "ready" | "not_ready" | "no_report" | "proxy_error" | "unknown";
  label: string;
  reasonCode: string;
  ready: boolean;
  cacheable: boolean;
  caseId: number | null;
  dispatchType: string;
  verificationVersion: string | null;
  hashSummary: string | null;
  blockers: string[];
};

export type JudgeChallengeEligibilityStatus =
  | "eligible"
  | "not_eligible"
  | "already_open"
  | "under_review"
  | "closed"
  | "case_absent"
  | "env_blocked"
  | "proxy_error"
  | "absent"
  | (string & {});

export type JudgeChallengeEligibility = {
  status: JudgeChallengeEligibilityStatus;
  eligible: boolean;
  requestable: boolean;
  reasonCode?: string | null;
  blockers: string[];
  [key: string]: JsonValue | undefined;
};

export type JudgeChallengeSummary = {
  state: string;
  activeChallengeId?: string | null;
  latestChallengeId?: string | null;
  latestDecision?: string | null;
  latestReasonCode?: string | null;
  totalChallenges?: number;
  [key: string]: JsonValue | undefined;
};

export type JudgeChallengeReviewSummary = {
  state: string;
  required: boolean;
  workflowStatus?: string | null;
  [key: string]: JsonValue | undefined;
};

export type JudgeChallengeCacheProfile = {
  cacheable: boolean;
  ttlSeconds: number;
  staleIfErrorSeconds?: number;
  cacheKey?: string;
  varyBy?: string[];
  [key: string]: JsonValue | undefined;
};

export type JudgeChallengePolicySummary = {
  version?: string | null;
  policyStatus?: string | null;
  policyVersion?: string | null;
  kernelHash?: string | null;
  challengeWindow?: string | null;
  maxOpenChallenges?: number;
  [key: string]: JsonValue | undefined;
};

export type JudgeReviewDecisionSync = {
  version: string;
  syncState: string;
  result: string;
  userVisibleStatus: string;
  source?: {
    originalCaseId?: number;
    originalVerdictVersion?: string;
    challengeId?: string | null;
    reviewDecisionId?: string | null;
    reviewDecisionEventSeq?: number | null;
    reviewDecidedAt?: string | null;
    decisionSource?: string;
  };
  verdictEffect?: {
    ledgerAction?: string;
    directWinnerWriteAllowed?: boolean;
    requiresVerdictLedgerSource?: boolean;
    drawVoteRequired?: boolean;
    reviewRequired?: boolean;
  };
  nextStep?: string;
};

export type GetDebateJudgeChallengeOutput = {
  sessionId: number;
  status: JudgeChallengeEligibilityStatus;
  statusReason: string;
  caseId?: number | null;
  dispatchType: "final" | "phase" | (string & {});
  eligibility: JudgeChallengeEligibility;
  challenge: JudgeChallengeSummary;
  review: JudgeChallengeReviewSummary;
  allowedActions: string[];
  blockers: string[];
  cacheProfile: JudgeChallengeCacheProfile;
  policy: JudgeChallengePolicySummary;
  reviewDecisionSync?: JudgeReviewDecisionSync;
};

export type RequestDebateJudgeChallengeOutput = GetDebateJudgeChallengeOutput;

export type DebateJudgeChallengeView = {
  state:
    | "eligible"
    | "blocked"
    | "open"
    | "under_review"
    | "closed"
    | "no_report"
    | "proxy_error"
    | "unknown";
  label: string;
  reasonCode: string;
  requestable: boolean;
  caseId: number | null;
  dispatchType: string;
  challengeState: string;
  reviewState: string;
  policyStatus: string | null;
  activeChallengeId: string | null;
  latestDecision: string | null;
  reviewSyncState: string;
  reviewVisibleStatus: string;
  reviewNextStep: string | null;
  totalChallenges: number;
  allowedActions: string[];
  blockers: string[];
  blockerLabels: string[];
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

export function normalizeDebateStatusFilter(
  value: string | null | undefined,
): DebateStatusFilter {
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

export function normalizeDebateSide(
  value: string | null | undefined,
): DebateSide {
  return (value || "").trim().toLowerCase() === "con" ? "con" : "pro";
}

function asJsonObject(
  value: JsonValue | null | undefined,
): Record<string, JsonValue> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value;
}

function jsonString(value: JsonValue | undefined): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function jsonStringArray(value: JsonValue | undefined): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (item): item is string =>
      typeof item === "string" && item.trim().length > 0,
  );
}

function firstPublicVerifyHash(
  publicVerify: JsonValue | null | undefined,
): string | null {
  const root = asJsonObject(publicVerify);
  const verifyPayload = asJsonObject(root?.verifyPayload);
  const candidates = [
    verifyPayload?.checksum,
    verifyPayload?.commitmentHash,
    verifyPayload?.caseHash,
    verifyPayload?.ledgerHash,
    verifyPayload?.manifestHash,
    verifyPayload?.rootHash,
    root?.verificationHash,
    root?.commitmentHash,
  ];
  for (const candidate of candidates) {
    const value = jsonString(candidate);
    if (value) {
      return value;
    }
  }
  return null;
}

function publicVerificationLabel(
  state: DebateJudgePublicVerificationView["state"],
  reasonCode: string,
): string {
  if (state === "ready") {
    return "Publicly verifiable";
  }
  if (state === "no_report") {
    return "No judge report yet";
  }
  if (state === "proxy_error") {
    return "Verification unavailable";
  }
  if (reasonCode === "env_blocked") {
    return "Verification environment blocked";
  }
  if (state === "not_ready") {
    return "Verification not ready";
  }
  return "Verification status unknown";
}

export function resolveDebateJudgePublicVerificationView(
  output: GetDebateJudgePublicVerificationOutput | null | undefined,
): DebateJudgePublicVerificationView {
  if (!output) {
    return {
      state: "unknown",
      label: "Verification status unknown",
      reasonCode: "not_loaded",
      ready: false,
      cacheable: false,
      caseId: null,
      dispatchType: "final",
      verificationVersion: null,
      hashSummary: null,
      blockers: [],
    };
  }

  const reasonCode = String(
    output.statusReason ||
      output.verificationReadiness?.status ||
      output.status ||
      "unknown",
  );
  const state =
    output.status === "ready"
      ? "ready"
      : output.status === "absent"
        ? "no_report"
        : output.status === "proxy_error"
          ? "proxy_error"
          : output.status === "not_ready"
            ? "not_ready"
            : "unknown";
  const root = asJsonObject(output.publicVerify);
  const verificationVersion =
    jsonString(root?.verificationVersion) ||
    jsonString(root?.version) ||
    jsonString(root?.contractVersion);

  return {
    state,
    label: publicVerificationLabel(state, reasonCode),
    reasonCode,
    ready: Boolean(output.verificationReadiness?.ready) && state === "ready",
    cacheable: Boolean(output.cacheProfile?.cacheable),
    caseId: Number.isFinite(Number(output.caseId))
      ? Number(output.caseId)
      : null,
    dispatchType: String(output.dispatchType || "final"),
    verificationVersion,
    hashSummary: firstPublicVerifyHash(output.publicVerify),
    blockers: jsonStringArray(output.verificationReadiness?.blockers),
  };
}

function challengeViewState(
  status: string,
  challengeState: string,
): DebateJudgeChallengeView["state"] {
  if (status === "eligible") {
    return "eligible";
  }
  if (status === "absent" || status === "case_absent") {
    return "no_report";
  }
  if (status === "proxy_error") {
    return "proxy_error";
  }
  if (
    status === "already_open" ||
    challengeState === "challenge_requested" ||
    challengeState === "challenge_accepted"
  ) {
    return "open";
  }
  if (status === "under_review" || challengeState === "under_internal_review") {
    return "under_review";
  }
  if (
    status === "closed" ||
    challengeState === "verdict_upheld" ||
    challengeState === "verdict_overturned" ||
    challengeState === "draw_after_review" ||
    challengeState === "review_retained" ||
    challengeState === "challenge_closed"
  ) {
    return "closed";
  }
  if (status === "not_eligible" || status === "env_blocked") {
    return "blocked";
  }
  return "unknown";
}

function challengeLabel(
  state: DebateJudgeChallengeView["state"],
  challengeState: string,
): string {
  if (state === "eligible") {
    return "Challenge available";
  }
  if (state === "no_report") {
    return "No judge report yet";
  }
  if (state === "proxy_error") {
    return "Challenge status unavailable";
  }
  if (state === "open") {
    return "Challenge open";
  }
  if (state === "under_review") {
    return "Review in progress";
  }
  if (challengeState === "verdict_upheld") {
    return "Verdict upheld";
  }
  if (challengeState === "verdict_overturned") {
    return "Verdict changed";
  }
  if (challengeState === "draw_after_review") {
    return "Draw after review";
  }
  if (challengeState === "review_retained") {
    return "Review retained";
  }
  if (state === "closed") {
    return "Review completed";
  }
  if (state === "blocked") {
    return "Challenge unavailable";
  }
  return "Challenge status unknown";
}

function challengeBlockerLabel(reasonCode: string): string {
  switch (reasonCode) {
    case "challenge_case_absent":
      return "Judge report is not ready";
    case "challenge_report_not_final":
      return "Final report is required";
    case "challenge_policy_disabled":
      return "Challenge policy is disabled";
    case "challenge_window_closed":
      return "Challenge window is closed";
    case "challenge_duplicate_open":
      return "A challenge is already open";
    case "challenge_review_already_closed":
      return "Review is already closed";
    case "challenge_permission_required":
    case "judge_challenge_request_forbidden":
      return "Participant access is required";
    case "challenge_env_blocked":
      return "Challenge environment is blocked";
    case "challenge_proxy_failed":
    case "challenge_contract_violation":
      return "Challenge status cannot be loaded";
    default:
      return reasonCode;
  }
}

function jsonNumber(value: JsonValue | undefined): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function resolveDebateJudgeChallengeView(
  output: GetDebateJudgeChallengeOutput | null | undefined,
): DebateJudgeChallengeView {
  if (!output) {
    return {
      state: "unknown",
      label: "Challenge status unknown",
      reasonCode: "not_loaded",
      requestable: false,
      caseId: null,
      dispatchType: "final",
      challengeState: "unknown",
      reviewState: "unknown",
      policyStatus: null,
      activeChallengeId: null,
      latestDecision: null,
      reviewSyncState: "not_available",
      reviewVisibleStatus: "not_available",
      reviewNextStep: null,
      totalChallenges: 0,
      allowedActions: [],
      blockers: [],
      blockerLabels: [],
    };
  }

  const eligibilityStatus = String(output.eligibility?.status || output.status);
  const challengeState = String(output.challenge?.state || output.status);
  const state = challengeViewState(eligibilityStatus, challengeState);
  const blockers = [
    ...new Set([
      ...jsonStringArray(output.eligibility?.blockers),
      ...jsonStringArray(output.blockers as JsonValue),
    ]),
  ];
  const reasonCode =
    jsonString(output.eligibility?.reasonCode) ||
    blockers[0] ||
    output.statusReason ||
    eligibilityStatus ||
    "unknown";
  const allowedActions = jsonStringArray(output.allowedActions as JsonValue);
  const requestable =
    state === "eligible" &&
    Boolean(output.eligibility?.requestable) &&
    allowedActions.includes("challenge.request");
  const reviewDecisionSync = output.reviewDecisionSync;

  return {
    state,
    label: challengeLabel(state, challengeState),
    reasonCode,
    requestable,
    caseId: Number.isFinite(Number(output.caseId))
      ? Number(output.caseId)
      : null,
    dispatchType: String(output.dispatchType || "final"),
    challengeState,
    reviewState: String(output.review?.state || "unknown"),
    policyStatus: jsonString(output.policy?.policyStatus),
    activeChallengeId: jsonString(output.challenge?.activeChallengeId),
    latestDecision: jsonString(output.challenge?.latestDecision),
    reviewSyncState: String(reviewDecisionSync?.syncState || "not_available"),
    reviewVisibleStatus: String(
      reviewDecisionSync?.userVisibleStatus || "not_available",
    ),
    reviewNextStep: jsonString(reviewDecisionSync?.nextStep),
    totalChallenges: jsonNumber(output.challenge?.totalChallenges) ?? 0,
    allowedActions,
    blockers,
    blockerLabels: blockers.slice(0, 3).map(challengeBlockerLabel),
  };
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
      limit: input?.limit ?? 8,
    },
  });
  return response.data;
}

export async function listDebateSessions(input?: {
  status?: DebateStatusFilter;
  topicId?: number;
  limit?: number;
}): Promise<ListDebateSessionsOutput> {
  const status = normalizeDebateStatusFilter(input?.status);
  const response = await http.get<ListDebateSessionsOutput>(
    "/debate/sessions",
    {
      params: {
        status: status === "all" ? undefined : status,
        topicId: input?.topicId,
        limit: input?.limit ?? 20,
      },
    },
  );
  return response.data;
}

export async function joinDebateSession(
  sessionId: number,
  side: DebateSide,
): Promise<JoinDebateSessionOutput> {
  const response = await http.post<JoinDebateSessionOutput>(
    `/debate/sessions/${sessionId}/join`,
    {
      side: normalizeDebateSide(side),
    },
  );
  return response.data;
}

export async function listDebateMessages(
  sessionId: number,
  input?: { lastId?: number; limit?: number },
): Promise<ListDebateMessagesOutput> {
  const response = await http.get<ListDebateMessagesOutput>(
    `/debate/sessions/${sessionId}/messages`,
    {
      params: {
        lastId: input?.lastId,
        limit: input?.limit ?? 80,
      },
    },
  );
  return response.data;
}

export async function listDebatePinnedMessages(
  sessionId: number,
  input?: { activeOnly?: boolean; cursor?: string; limit?: number },
): Promise<ListDebatePinnedMessagesOutput> {
  const response = await http.get<ListDebatePinnedMessagesOutput>(
    `/debate/sessions/${sessionId}/pins`,
    {
      params: {
        activeOnly: input?.activeOnly ?? true,
        cursor: input?.cursor,
        limit: input?.limit ?? 20,
      },
    },
  );
  return response.data;
}

export async function createDebateMessage(
  sessionId: number,
  content: string,
): Promise<DebateMessage> {
  const response = await http.post<DebateMessage>(
    `/debate/sessions/${sessionId}/messages`,
    {
      content: String(content || "").trim(),
    },
  );
  return response.data;
}

function buildPinIdempotencyKey(): string {
  if (
    typeof globalThis !== "undefined" &&
    typeof globalThis.crypto?.randomUUID === "function"
  ) {
    return `pin_${globalThis.crypto.randomUUID()}`;
  }
  return `pin_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export async function pinDebateMessage(
  messageId: number,
  pinSeconds: number,
  input?: { idempotencyKey?: string },
): Promise<PinDebateMessageOutput> {
  const normalizedPinSeconds = Math.max(
    1,
    Math.floor(Number(pinSeconds) || 60),
  );
  const response = await http.post<PinDebateMessageOutput>(
    `/debate/messages/${messageId}/pin`,
    {
      pinSeconds: normalizedPinSeconds,
      idempotencyKey:
        String(input?.idempotencyKey || "").trim() || buildPinIdempotencyKey(),
    },
  );
  return response.data;
}

export async function getWalletBalance(): Promise<WalletBalanceOutput> {
  const response = await http.get<WalletBalanceOutput>("/pay/wallet");
  return response.data;
}

export async function requestDebateJudgeJob(
  sessionId: number,
  input?: { allowRejudge?: boolean },
): Promise<RequestDebateJudgeJobOutput> {
  const response = await http.post<RequestDebateJudgeJobOutput>(
    `/debate/sessions/${sessionId}/judge/jobs`,
    {
      allowRejudge: Boolean(input?.allowRejudge),
    },
  );
  return response.data;
}

export async function getDebateJudgeReport(
  sessionId: number,
  input?: { maxStageCount?: number; stageOffset?: number },
): Promise<GetDebateJudgeReportOutput> {
  const response = await http.get<GetDebateJudgeReportOutput>(
    `/debate/sessions/${sessionId}/judge-report`,
    {
      params: {
        maxStageCount: input?.maxStageCount,
        stageOffset: input?.stageOffset,
      },
    },
  );
  return response.data;
}

export async function getDebateJudgePublicVerification(
  sessionId: number,
  input?: { rejudgeRunNo?: number; dispatchType?: "final" | "phase" },
): Promise<GetDebateJudgePublicVerificationOutput> {
  const response = await http.get<GetDebateJudgePublicVerificationOutput>(
    `/debate/sessions/${sessionId}/judge-report/public-verify`,
    {
      params: {
        rejudgeRunNo: input?.rejudgeRunNo,
        dispatchType: input?.dispatchType || "final",
      },
    },
  );
  return response.data;
}

export async function getDebateJudgeChallenge(
  sessionId: number,
  input?: { rejudgeRunNo?: number; dispatchType?: "final" | "phase" },
): Promise<GetDebateJudgeChallengeOutput> {
  const response = await http.get<GetDebateJudgeChallengeOutput>(
    `/debate/sessions/${sessionId}/judge-report/challenge`,
    {
      params: {
        rejudgeRunNo: input?.rejudgeRunNo,
        dispatchType: input?.dispatchType || "final",
      },
    },
  );
  return response.data;
}

function buildJudgeChallengeIdempotencyKey(): string {
  if (
    typeof globalThis !== "undefined" &&
    typeof globalThis.crypto?.randomUUID === "function"
  ) {
    return `judge_challenge_${globalThis.crypto.randomUUID()}`;
  }
  return `judge_challenge_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export async function requestDebateJudgeChallenge(
  sessionId: number,
  input?: {
    rejudgeRunNo?: number;
    dispatchType?: "final" | "phase";
    idempotencyKey?: string;
    reasonCode?: string;
    userReason?: string;
  },
): Promise<RequestDebateJudgeChallengeOutput> {
  const response = await http.post<RequestDebateJudgeChallengeOutput>(
    `/debate/sessions/${sessionId}/judge-report/challenge/request`,
    {
      idempotencyKey:
        String(input?.idempotencyKey || "").trim() ||
        buildJudgeChallengeIdempotencyKey(),
      reasonCode: String(input?.reasonCode || "manual_challenge").trim(),
      userReason: String(input?.userReason || "").trim() || undefined,
    },
    {
      params: {
        rejudgeRunNo: input?.rejudgeRunNo,
        dispatchType: input?.dispatchType || "final",
      },
    },
  );
  return response.data;
}

export async function getDebateDrawVoteStatus(
  sessionId: number,
): Promise<GetDebateDrawVoteOutput> {
  const response = await http.get<GetDebateDrawVoteOutput>(
    `/debate/sessions/${sessionId}/draw-vote`,
  );
  return response.data;
}

export async function submitDebateDrawVote(
  sessionId: number,
  agreeDraw: boolean,
): Promise<SubmitDebateDrawVoteOutput> {
  const response = await http.post<SubmitDebateDrawVoteOutput>(
    `/debate/sessions/${sessionId}/draw-vote/ballots`,
    {
      agreeDraw: Boolean(agreeDraw),
    },
  );
  return response.data;
}

export function normalizeDebateMessage(
  raw: Partial<DebateMessage> | null | undefined,
): DebateMessage | null {
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
    createdAt: String(raw.createdAt || new Date().toISOString()),
  };
}

export function mergeDebateMessages(
  currentMessages: DebateMessage[],
  incomingMessages: Array<Partial<DebateMessage> | null | undefined>,
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

export function getOldestDebateMessageId(
  messages: DebateMessage[],
): number | null {
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
