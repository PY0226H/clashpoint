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
  viewerRole?: "participant" | "spectator" | string;
  viewerSide?: DebateSide | null;
  canSendMessage?: boolean;
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

export const DEBATE_NPC_ACTION_CREATED_EVENT = "DebateNpcActionCreated" as const;

export type DebateNpcActionType =
  | "speak"
  | "praise"
  | "effect"
  | "state_changed";

export type DebateNpcActionCreatedPayload = {
  event: typeof DEBATE_NPC_ACTION_CREATED_EVENT;
  actionId: number;
  actionUid: string;
  sessionId: number;
  npcId: string;
  displayName: string;
  actionType: DebateNpcActionType;
  publicText?: string | null;
  targetMessageId?: number | null;
  targetUserId?: number | null;
  targetSide?: DebateSide | null;
  effectKind?: string | null;
  npcStatus?: string | null;
  reasonCode?: string | null;
  createdAt: string;
};

export type JudgeAssistantAgentKind = "npc_coach" | "room_qa" | (string & {});

export type JudgeAssistantAdvisoryStatus =
  | "ok"
  | "not_ready"
  | "proxy_error"
  | "contract_violation"
  | "rate_limited"
  | (string & {});

export type RequestNpcCoachAdviceInput = {
  query: string;
  traceId?: string;
  side?: DebateSide;
  caseId?: number;
};

export type RequestRoomQaAnswerInput = {
  question: string;
  traceId?: string;
  caseId?: number;
};

export type AssistantCapabilityBoundary = {
  mode?: string;
  advisoryOnly?: boolean;
  officialVerdictAuthority?: boolean;
  writesVerdictLedger?: boolean;
  writesJudgeTrace?: boolean;
  [key: string]: JsonValue | undefined;
};

export type JudgeAssistantAdvisoryCacheProfile = {
  cacheable?: boolean;
  ttlSeconds?: number;
  staleWhileRevalidateSeconds?: number;
  cacheKey?: string;
  varyBy?: string[];
  [key: string]: JsonValue | undefined;
};

export type AssistantRoomContextSnapshot = {
  sessionId: number;
  scopeId: number;
  caseId?: number | null;
  workflowStatus?: string | null;
  latestDispatchType?: "phase" | "final" | null | (string & {});
  topicDomain?: string | null;
  phaseReceiptCount: number;
  finalReceiptCount: number;
  updatedAt?: string | null;
  officialVerdictFieldsRedacted: boolean;
};

export type AssistantStageSummary = {
  stage:
    | "room_context_only"
    | "phase_context_available"
    | "final_context_available"
    | (string & {});
  workflowStatus?: string | null;
  latestDispatchType?: "phase" | "final" | null | (string & {});
  hasPhaseReceipt: boolean;
  hasFinalReceipt: boolean;
  officialVerdictFieldsRedacted: boolean;
};

export type JudgeAssistantAdvisoryOutput = {
  version: string;
  agentKind: JudgeAssistantAgentKind;
  sessionId: number;
  caseId?: number | null;
  advisoryOnly: boolean;
  status: JudgeAssistantAdvisoryStatus;
  statusReason: string;
  accepted: boolean;
  errorCode?: string | null;
  errorMessage?: string | null;
  capabilityBoundary: AssistantCapabilityBoundary;
  sharedContext: JsonValue;
  advisoryContext: JsonValue;
  output: JsonValue;
  cacheProfile: JudgeAssistantAdvisoryCacheProfile;
};

export type JudgeAssistantAdvisoryView = {
  state: "ready" | "not_ready" | "proxy_error" | "contract_violation" | "unknown";
  agentKind: string;
  label: string;
  reasonCode: string;
  advisoryOnly: boolean;
  accepted: boolean;
  caseId: number | null;
  message: string | null;
  items: string[];
  contextStage: string;
  contextLabel: string;
  workflowStatus: string | null;
  latestDispatchType: string | null;
  receiptSummary: string;
  updatedAt: string | null;
};

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

const DEBATE_NPC_ALLOWED_ACTION_TYPES = new Set<DebateNpcActionType>([
  "speak",
  "praise",
  "effect",
  "state_changed",
]);

const DEBATE_NPC_FORBIDDEN_VISIBLE_FIELDS = new Set([
  "policyVersion",
  "executorVersion",
  "traceId",
  "trace",
  "winner",
  "proScore",
  "conScore",
  "finalRationale",
  "judgeTrace",
  "verdictEvidenceRefs",
  "dimensionScores",
]);

function hasForbiddenDebateNpcVisibleField(
  value: Record<string, unknown>,
): boolean {
  return Object.keys(value).some((key) =>
    DEBATE_NPC_FORBIDDEN_VISIBLE_FIELDS.has(key),
  );
}

function isNonNegativeFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function isOptionalStringOrNull(value: unknown): boolean {
  return value == null || typeof value === "string";
}

function isOptionalNonNegativeNumberOrNull(value: unknown): boolean {
  return value == null || isNonNegativeFiniteNumber(value);
}

function isOptionalDebateSideOrNull(value: unknown): value is DebateSide | null | undefined {
  return value == null || value === "pro" || value === "con";
}

export function isDebateNpcActionCreatedPayload(
  value: unknown,
): value is DebateNpcActionCreatedPayload {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }

  const payload = value as Record<string, unknown>;
  if (hasForbiddenDebateNpcVisibleField(payload)) {
    return false;
  }

  if (payload.event !== DEBATE_NPC_ACTION_CREATED_EVENT) {
    return false;
  }

  if (
    !isNonNegativeFiniteNumber(payload.actionId) ||
    !isNonNegativeFiniteNumber(payload.sessionId) ||
    typeof payload.actionUid !== "string" ||
    !payload.actionUid.trim() ||
    typeof payload.npcId !== "string" ||
    !payload.npcId.trim() ||
    typeof payload.displayName !== "string" ||
    !payload.displayName.trim() ||
    typeof payload.createdAt !== "string" ||
    !payload.createdAt.trim()
  ) {
    return false;
  }

  if (
    typeof payload.actionType !== "string" ||
    !DEBATE_NPC_ALLOWED_ACTION_TYPES.has(payload.actionType as DebateNpcActionType)
  ) {
    return false;
  }

  return (
    isOptionalStringOrNull(payload.publicText) &&
    isOptionalNonNegativeNumberOrNull(payload.targetMessageId) &&
    isOptionalNonNegativeNumberOrNull(payload.targetUserId) &&
    isOptionalDebateSideOrNull(payload.targetSide) &&
    isOptionalStringOrNull(payload.effectKind) &&
    isOptionalStringOrNull(payload.npcStatus) &&
    isOptionalStringOrNull(payload.reasonCode)
  );
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

function jsonBoolean(value: JsonValue | undefined): boolean | null {
  return typeof value === "boolean" ? value : null;
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

const ASSISTANT_ADVISORY_CONTRACT_VERSION = "assistant_advisory_contract_v1";

const ASSISTANT_ROOM_CONTEXT_KEYS = [
  "sessionId",
  "scopeId",
  "caseId",
  "workflowStatus",
  "latestDispatchType",
  "topicDomain",
  "phaseReceiptCount",
  "finalReceiptCount",
  "updatedAt",
  "officialVerdictFieldsRedacted",
] as const;

const ASSISTANT_STAGE_SUMMARY_KEYS = [
  "stage",
  "workflowStatus",
  "latestDispatchType",
  "hasPhaseReceipt",
  "hasFinalReceipt",
  "officialVerdictFieldsRedacted",
] as const;

const ASSISTANT_FORBIDDEN_FIELD_KEYS = new Set([
  "winner",
  "proscore",
  "conscore",
  "dimensionscores",
  "debatesummary",
  "sideanalysis",
  "verdictreason",
  "verdictledger",
  "fairnessgate",
  "trustattestation",
  "judgetrace",
  "rawprompt",
  "rawtrace",
  "artifactref",
  "artifactrefs",
  "providerconfig",
  "secret",
  "credential",
  "officialverdictauthority",
  "writesverdictledger",
  "writesjudgetrace",
]);

function normalizeAssistantFieldKey(key: string): string {
  return key.replace(/[\s_.-]/g, "").toLowerCase();
}

function hasForbiddenAssistantField(value: JsonValue): boolean {
  if (!value || typeof value !== "object") {
    return false;
  }
  if (Array.isArray(value)) {
    return value.some((item) => hasForbiddenAssistantField(item));
  }
  return Object.entries(value).some(
    ([key, nested]) =>
      ASSISTANT_FORBIDDEN_FIELD_KEYS.has(normalizeAssistantFieldKey(key)) ||
      hasForbiddenAssistantField(nested),
  );
}

function assistantBoundaryIsSafe(
  boundary: AssistantCapabilityBoundary | null | undefined,
): boolean {
  if (!boundary || typeof boundary !== "object" || Array.isArray(boundary)) {
    return false;
  }
  return (
    jsonString(boundary.mode) === "advisory_only" &&
    jsonBoolean(boundary.advisoryOnly) === true &&
    jsonBoolean(boundary.officialVerdictAuthority) === false &&
    jsonBoolean(boundary.writesVerdictLedger) === false &&
    jsonBoolean(boundary.writesJudgeTrace) === false
  );
}

function objectHasExactKeys(
  value: JsonValue | null | undefined,
  keys: readonly string[],
): value is Record<string, JsonValue> {
  const root = asJsonObject(value);
  if (!root) {
    return false;
  }
  const actualKeys = Object.keys(root);
  return (
    actualKeys.length === keys.length &&
    keys.every((key) => Object.prototype.hasOwnProperty.call(root, key))
  );
}

function jsonNonNegativeNumber(value: JsonValue | undefined): boolean {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function jsonOptionalStringOrNull(value: JsonValue | undefined): boolean {
  return value == null || typeof value === "string";
}

function jsonOptionalDispatchType(value: JsonValue | undefined): boolean {
  return value == null || value === "phase" || value === "final";
}

function stableJsonValue(value: JsonValue | undefined): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableJsonValue(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    const entries = Object.keys(value)
      .sort()
      .map((key) => {
        const objectValue = value as Record<string, JsonValue>;
        return `${JSON.stringify(key)}:${stableJsonValue(objectValue[key])}`;
      });
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value);
}

function isAssistantRoomContextSnapshot(
  value: JsonValue | null | undefined,
  expectedSessionId: number,
): boolean {
  if (!objectHasExactKeys(value, ASSISTANT_ROOM_CONTEXT_KEYS)) {
    return false;
  }
  return (
    value.sessionId === expectedSessionId &&
    jsonNonNegativeNumber(value.scopeId) &&
    (value.caseId == null || jsonNonNegativeNumber(value.caseId)) &&
    jsonOptionalStringOrNull(value.workflowStatus) &&
    jsonOptionalDispatchType(value.latestDispatchType) &&
    jsonOptionalStringOrNull(value.topicDomain) &&
    jsonNonNegativeNumber(value.phaseReceiptCount) &&
    jsonNonNegativeNumber(value.finalReceiptCount) &&
    jsonOptionalStringOrNull(value.updatedAt) &&
    value.officialVerdictFieldsRedacted === true
  );
}

function isAssistantStageSummary(
  value: JsonValue | null | undefined,
): boolean {
  if (!objectHasExactKeys(value, ASSISTANT_STAGE_SUMMARY_KEYS)) {
    return false;
  }
  return (
    (value.stage === "room_context_only" ||
      value.stage === "phase_context_available" ||
      value.stage === "final_context_available") &&
    jsonOptionalStringOrNull(value.workflowStatus) &&
    jsonOptionalDispatchType(value.latestDispatchType) &&
    typeof value.hasPhaseReceipt === "boolean" &&
    typeof value.hasFinalReceipt === "boolean" &&
    value.officialVerdictFieldsRedacted === true
  );
}

export function assertJudgeAssistantAdvisoryOutput(
  output: JudgeAssistantAdvisoryOutput,
  expectedAgentKind: "npc_coach" | "room_qa",
): JudgeAssistantAdvisoryOutput {
  if (!output || typeof output !== "object") {
    throw new Error("assistant advisory response is invalid");
  }
  if (output.version !== ASSISTANT_ADVISORY_CONTRACT_VERSION) {
    throw new Error("assistant advisory contract version is invalid");
  }
  if (output.agentKind !== expectedAgentKind) {
    throw new Error("assistant advisory agent kind is invalid");
  }
  if (output.advisoryOnly !== true) {
    throw new Error("assistant advisory response is not advisory-only");
  }
  if (!assistantBoundaryIsSafe(output.capabilityBoundary)) {
    throw new Error("assistant advisory capability boundary is invalid");
  }
  if (
    !isAssistantRoomContextSnapshot(output.sharedContext, output.sessionId)
  ) {
    throw new Error("assistant advisory room context snapshot is invalid");
  }
  const advisoryContext = asJsonObject(output.advisoryContext);
  const roomContextSnapshot = advisoryContext?.roomContextSnapshot;
  const stageSummary = advisoryContext?.stageSummary;
  if (
    !isAssistantRoomContextSnapshot(roomContextSnapshot, output.sessionId) ||
    stableJsonValue(roomContextSnapshot) !== stableJsonValue(output.sharedContext)
  ) {
    throw new Error("assistant advisory advisory context snapshot is invalid");
  }
  if (!isAssistantStageSummary(stageSummary)) {
    throw new Error("assistant advisory stage summary is invalid");
  }
  if (output.status === "not_ready" && output.accepted) {
    throw new Error("assistant advisory not_ready response cannot be accepted");
  }
  if (
    hasForbiddenAssistantField(output.output) ||
    hasForbiddenAssistantField(output.sharedContext) ||
    hasForbiddenAssistantField(output.advisoryContext)
  ) {
    throw new Error("assistant advisory output contains forbidden official fields");
  }
  return output;
}

function assistantAdvisoryViewState(
  output: JudgeAssistantAdvisoryOutput,
): JudgeAssistantAdvisoryView["state"] {
  if (output.status === "ok" && output.accepted) {
    return "ready";
  }
  if (output.status === "not_ready") {
    return "not_ready";
  }
  if (output.status === "proxy_error") {
    return "proxy_error";
  }
  if (
    output.status === "contract_violation" ||
    output.statusReason === "assistant_advisory_contract_violation"
  ) {
    return "contract_violation";
  }
  return "unknown";
}

function assistantAdvisoryLabel(
  state: JudgeAssistantAdvisoryView["state"],
  reasonCode: string,
): string {
  if (state === "ready") {
    return "辅助建议已生成";
  }
  if (state === "not_ready") {
    return "辅助功能未启用";
  }
  if (state === "proxy_error") {
    return "辅助建议暂不可用";
  }
  if (state === "contract_violation") {
    return "辅助建议合同校验失败";
  }
  if (reasonCode === "rate_limited") {
    return "辅助建议请求过快";
  }
  return "辅助建议状态未知";
}

function firstAssistantOutputText(output: JsonValue): string | null {
  const root = asJsonObject(output);
  const candidates = [
    root?.advice,
    root?.answer,
    root?.message,
    root?.summary,
    root?.guidance,
    root?.safeGuidanceSummary,
  ];
  for (const candidate of candidates) {
    const value = jsonString(candidate);
    if (value) {
      return value;
    }
  }
  return null;
}

function assistantOutputItems(output: JsonValue): string[] {
  const root = asJsonObject(output);
  const candidates = [
    root?.suggestions,
    root?.points,
    root?.questions,
    root?.suggestedNextQuestions,
    root?.nextSteps,
  ];
  for (const candidate of candidates) {
    const values = jsonStringArray(candidate);
    if (values.length > 0) {
      return values.slice(0, 4);
    }
  }
  return [];
}

function assistantContextStageLabel(stage: string): string {
  if (stage === "final_context_available") {
    return "已有最终上下文";
  }
  if (stage === "phase_context_available") {
    return "已有阶段上下文";
  }
  return "仅有房间上下文";
}

function assistantContextReceiptSummary(
  snapshot: Record<string, JsonValue> | null,
): string {
  const phaseCount =
    typeof snapshot?.phaseReceiptCount === "number"
      ? Math.floor(snapshot.phaseReceiptCount)
      : 0;
  const finalCount =
    typeof snapshot?.finalReceiptCount === "number"
      ? Math.floor(snapshot.finalReceiptCount)
      : 0;
  return `phase ${phaseCount} / final ${finalCount}`;
}

export function resolveJudgeAssistantAdvisoryView(
  output: JudgeAssistantAdvisoryOutput | null | undefined,
): JudgeAssistantAdvisoryView {
  if (!output) {
    return {
      state: "unknown",
      agentKind: "unknown",
      label: "辅助建议状态未知",
      reasonCode: "not_loaded",
      advisoryOnly: true,
      accepted: false,
      caseId: null,
      message: null,
      items: [],
      contextStage: "unknown",
      contextLabel: "上下文未加载",
      workflowStatus: null,
      latestDispatchType: null,
      receiptSummary: "phase 0 / final 0",
      updatedAt: null,
    };
  }

  const state = assistantAdvisoryViewState(output);
  const advisoryContext = asJsonObject(output.advisoryContext);
  const stageSummary = asJsonObject(advisoryContext?.stageSummary);
  const roomContextSnapshot = asJsonObject(output.sharedContext);
  const contextStage = jsonString(stageSummary?.stage) || "room_context_only";
  const reasonCode =
    String(output.errorCode || output.statusReason || output.status || "unknown") ||
    "unknown";
  const fallbackMessage =
    state === "not_ready"
      ? "辅助建议暂未启用，当前不会影响官方裁决。"
      : state === "proxy_error"
        ? "辅助建议服务暂时不可用，请稍后重试。"
        : state === "contract_violation"
          ? "辅助建议响应未通过安全合同校验。"
          : null;

  return {
    state,
    agentKind: String(output.agentKind || "unknown"),
    label: assistantAdvisoryLabel(state, reasonCode),
    reasonCode,
    advisoryOnly: output.advisoryOnly === true,
    accepted: Boolean(output.accepted) && state === "ready",
    caseId: Number.isFinite(Number(output.caseId)) ? Number(output.caseId) : null,
    message: firstAssistantOutputText(output.output) || fallbackMessage,
    items: state === "ready" ? assistantOutputItems(output.output) : [],
    contextStage,
    contextLabel: assistantContextStageLabel(contextStage),
    workflowStatus: jsonString(roomContextSnapshot?.workflowStatus),
    latestDispatchType: jsonString(roomContextSnapshot?.latestDispatchType),
    receiptSummary: assistantContextReceiptSummary(roomContextSnapshot),
    updatedAt: jsonString(roomContextSnapshot?.updatedAt),
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

function normalizedRequiredAssistantText(field: string, value: string): string {
  const text = String(value || "").trim();
  if (!text) {
    throw new Error(`${field} is required`);
  }
  return text;
}

function normalizedAssistantTraceId(
  value: string | null | undefined,
): string | undefined {
  const text = String(value || "").trim();
  return text || undefined;
}

function normalizedAssistantCaseId(
  value: number | null | undefined,
): number | undefined {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined;
  }
  return Math.floor(parsed);
}

export async function requestNpcCoachAdvice(
  sessionId: number,
  input: RequestNpcCoachAdviceInput,
): Promise<JudgeAssistantAdvisoryOutput> {
  const body: RequestNpcCoachAdviceInput = {
    query: normalizedRequiredAssistantText("query", input.query),
  };
  const traceId = normalizedAssistantTraceId(input.traceId);
  const caseId = normalizedAssistantCaseId(input.caseId);
  if (traceId) {
    body.traceId = traceId;
  }
  if (input.side) {
    body.side = normalizeDebateSide(input.side);
  }
  if (caseId) {
    body.caseId = caseId;
  }
  const response = await http.post<JudgeAssistantAdvisoryOutput>(
    `/debate/sessions/${sessionId}/assistant/npc-coach/advice`,
    body,
  );
  return assertJudgeAssistantAdvisoryOutput(response.data, "npc_coach");
}

export async function requestRoomQaAnswer(
  sessionId: number,
  input: RequestRoomQaAnswerInput,
): Promise<JudgeAssistantAdvisoryOutput> {
  const body: RequestRoomQaAnswerInput = {
    question: normalizedRequiredAssistantText("question", input.question),
  };
  const traceId = normalizedAssistantTraceId(input.traceId);
  const caseId = normalizedAssistantCaseId(input.caseId);
  if (traceId) {
    body.traceId = traceId;
  }
  if (caseId) {
    body.caseId = caseId;
  }
  const response = await http.post<JudgeAssistantAdvisoryOutput>(
    `/debate/sessions/${sessionId}/assistant/room-qa/answer`,
    body,
  );
  return assertJudgeAssistantAdvisoryOutput(response.data, "room_qa");
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
