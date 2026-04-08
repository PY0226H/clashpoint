import { http, toApiError } from "@echoisle/api-client";

export type OpsRole = "ops_admin" | "ops_reviewer" | "ops_viewer";

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | { [key: string]: JsonValue }
  | JsonValue[];

export type OpsPermissionFlags = {
  debateManage: boolean;
  judgeReview: boolean;
  judgeRejudge: boolean;
  roleManage: boolean;
};

export type GetOpsRbacMeOutput = {
  userId: number;
  isOwner: boolean;
  role?: string | null;
  permissions: OpsPermissionFlags;
};

export type OpsRoleAssignment = {
  userId: number;
  userEmail: string;
  userFullname: string;
  role: OpsRole;
  grantedBy: number;
  createdAt: string;
  updatedAt: string;
};

export type ListOpsRoleAssignmentsOutput = {
  items: OpsRoleAssignment[];
};

export type RevokeOpsRoleOutput = {
  userId: number;
  removed: boolean;
};

export type OpsObservabilityThresholds = {
  lowSuccessRateThreshold: number;
  highRetryThreshold: number;
  highCoalescedThreshold: number;
  highDbLatencyThresholdMs: number;
  lowCacheHitRateThreshold: number;
  minRequestForCacheHitCheck: number;
};

export type OpsObservabilityAnomalyStateValue = {
  acknowledgedAtMs: number;
  suppressUntilMs: number;
};

export type GetOpsObservabilityConfigOutput = {
  thresholds: OpsObservabilityThresholds;
  anomalyState: Record<string, OpsObservabilityAnomalyStateValue>;
  updatedBy?: number | null;
  updatedAt?: string | null;
};

export type OpsMetricsDictionaryItem = {
  key: string;
  category: string;
  source: string;
  unit: string;
  aggregation: string;
  description: string;
  target?: string | null;
};

export type GetOpsMetricsDictionaryOutput = {
  version: string;
  generatedAtMs: number;
  items: OpsMetricsDictionaryItem[];
};

export type OpsSloSignalSnapshot = {
  successCount: number;
  failedCount: number;
  completedCount: number;
  successRatePct: number;
  avgDispatchAttempts: number;
  p95LatencyMs: number;
  pendingDlqCount: number;
};

export type OpsSloRuleSnapshotItem = {
  alertKey: string;
  ruleType: string;
  title: string;
  severity: string;
  isActive: boolean;
  status: string;
  suppressed: boolean;
  lastEmittedStatus?: string | null;
  message: string;
  metrics: JsonValue;
};

export type GetOpsSloSnapshotOutput = {
  windowMinutes: number;
  generatedAtMs: number;
  thresholds: OpsObservabilityThresholds;
  signal: OpsSloSignalSnapshot;
  rules: OpsSloRuleSnapshotItem[];
};

export type OpsServiceSplitThresholdItem = {
  key: string;
  title: string;
  status: string;
  triggered: boolean;
  recommendation: string;
  evidence: JsonValue;
};

export type GetOpsServiceSplitReadinessOutput = {
  generatedAtMs: number;
  overallStatus: string;
  nextStep: string;
  thresholds: OpsServiceSplitThresholdItem[];
};

export type UpsertOpsServiceSplitReviewInput = {
  paymentComplianceRequired?: boolean | null;
  reviewNote?: string | null;
};

export type OpsServiceSplitReviewAuditItem = {
  id: number;
  paymentComplianceRequired?: boolean | null;
  reviewNote: string;
  updatedBy: number;
  createdAt: string;
};

export type ListOpsServiceSplitReviewAuditsOutput = {
  total: number;
  limit: number;
  offset: number;
  items: OpsServiceSplitReviewAuditItem[];
};

export type OpsAlertNotificationItem = {
  id: number;
  alertKey: string;
  ruleType: string;
  severity: string;
  alertStatus: string;
  title: string;
  message: string;
  metrics: JsonValue;
  recipients: number[];
  deliveryStatus: string;
  errorMessage?: string | null;
  deliveredAt?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ListOpsAlertNotificationsOutput = {
  total: number;
  limit: number;
  offset: number;
  items: OpsAlertNotificationItem[];
};

export type ApplyOpsObservabilityAnomalyActionInput = {
  alertKey: string;
  action: "acknowledge" | "suppress" | "clear";
  suppressMinutes?: number;
};

export type OpsAlertEvalReport = {
  scopesScanned: number;
  alertsRaised: number;
  alertsCleared: number;
  alertsSuppressed: number;
};

export type OpsDomainErrorInfo = {
  status: number | null;
  code: string | null;
  message: string;
};

type ApiErrorPayloadLike = {
  error?: string;
  code?: string;
  message?: string;
};

type ApiErrorLike = {
  response?: {
    status?: number;
    data?: ApiErrorPayloadLike | null;
  };
  message?: string;
};

function normalizeOpsDomainErrorCode(raw: string | null): string | null {
  const value = stripOpsDomainErrorPrefix(String(raw || "").trim());
  if (!value) {
    return null;
  }
  if (value.startsWith("ops_permission_denied:")) {
    const parts = value.split(":");
    if (parts.length >= 2) {
      return `${parts[0]}:${parts[1]}`;
    }
    return "ops_permission_denied";
  }
  if (value.startsWith("rate_limit_exceeded:")) {
    const parts = value.split(":");
    if (parts.length >= 2) {
      return `${parts[0]}:${parts[1]}`;
    }
    return "rate_limit_exceeded";
  }
  if (value.startsWith("ops_role_target_user_not_found")) {
    return "ops_role_target_user_not_found";
  }
  return value;
}

function stripOpsDomainErrorPrefix(raw: string): string {
  const value = String(raw || "").trim();
  if (!value) {
    return value;
  }
  const lower = value.toLowerCase();
  const prefixes = [
    "debate conflict:",
    "debate error:",
    "not found:",
    "validation error:",
    "server error:"
  ];
  for (const prefix of prefixes) {
    if (lower.startsWith(prefix)) {
      return value.slice(prefix.length).trim();
    }
  }
  return value;
}

export function getOpsDomainErrorInfo(error: unknown): OpsDomainErrorInfo {
  const known = error as ApiErrorLike;
  const status = typeof known.response?.status === "number" ? known.response.status : null;
  const rawCode =
    known.response?.data?.code ||
    known.response?.data?.error ||
    known.response?.data?.message ||
    null;
  const code = normalizeOpsDomainErrorCode(rawCode);
  const message =
    code || known.response?.data?.message || known.response?.data?.error || known.message || "request failed";
  return {
    status,
    code,
    message
  };
}

export function toOpsDomainError(error: unknown): string {
  return getOpsDomainErrorInfo(error).message || toApiError(error);
}

export async function getOpsRbacMe(): Promise<GetOpsRbacMeOutput> {
  const response = await http.get<GetOpsRbacMeOutput>("/debate/ops/rbac/me");
  return response.data;
}

export async function listOpsRoleAssignments(): Promise<ListOpsRoleAssignmentsOutput> {
  const response = await http.get<ListOpsRoleAssignmentsOutput>("/debate/ops/rbac/roles");
  return response.data;
}

export async function upsertOpsRoleAssignment(
  userId: number,
  role: OpsRole
): Promise<OpsRoleAssignment> {
  const normalizedUserId = Math.floor(Number(userId) || 0);
  const normalizedRole = String(role || "").trim().toLowerCase() as OpsRole;
  const response = await http.put<OpsRoleAssignment>(`/debate/ops/rbac/roles/${normalizedUserId}`, {
    role: normalizedRole
  });
  return response.data;
}

export async function revokeOpsRoleAssignment(userId: number): Promise<RevokeOpsRoleOutput> {
  const normalizedUserId = Math.floor(Number(userId) || 0);
  const response = await http.delete<RevokeOpsRoleOutput>(`/debate/ops/rbac/roles/${normalizedUserId}`);
  return response.data;
}

export async function getOpsObservabilityConfig(): Promise<GetOpsObservabilityConfigOutput> {
  const response = await http.get<GetOpsObservabilityConfigOutput>("/debate/ops/observability/config");
  return response.data;
}

export async function upsertOpsObservabilityThresholds(
  input: OpsObservabilityThresholds
): Promise<GetOpsObservabilityConfigOutput> {
  const response = await http.put<GetOpsObservabilityConfigOutput>("/debate/ops/observability/thresholds", input);
  return response.data;
}

export async function getOpsMetricsDictionary(): Promise<GetOpsMetricsDictionaryOutput> {
  const response = await http.get<GetOpsMetricsDictionaryOutput>("/debate/ops/observability/metrics-dictionary");
  return response.data;
}

export async function getOpsSloSnapshot(): Promise<GetOpsSloSnapshotOutput> {
  const response = await http.get<GetOpsSloSnapshotOutput>("/debate/ops/observability/slo-snapshot");
  return response.data;
}

export async function getOpsServiceSplitReadiness(): Promise<GetOpsServiceSplitReadinessOutput> {
  const response = await http.get<GetOpsServiceSplitReadinessOutput>("/debate/ops/observability/split-readiness");
  return response.data;
}

export async function upsertOpsServiceSplitReview(
  input: UpsertOpsServiceSplitReviewInput
): Promise<GetOpsServiceSplitReadinessOutput> {
  const response = await http.put<GetOpsServiceSplitReadinessOutput>(
    "/debate/ops/observability/split-readiness/review",
    {
      paymentComplianceRequired: input.paymentComplianceRequired ?? null,
      reviewNote: input.reviewNote ?? null
    }
  );
  return response.data;
}

export async function listOpsServiceSplitReviewAudits(input?: {
  limit?: number;
  offset?: number;
}): Promise<ListOpsServiceSplitReviewAuditsOutput> {
  const response = await http.get<ListOpsServiceSplitReviewAuditsOutput>(
    "/debate/ops/observability/split-readiness/reviews",
    {
      params: {
        limit: input?.limit ?? 3,
        offset: input?.offset ?? 0
      }
    }
  );
  return response.data;
}

export async function listOpsAlertNotifications(input?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<ListOpsAlertNotificationsOutput> {
  const response = await http.get<ListOpsAlertNotificationsOutput>("/debate/ops/observability/alerts", {
    params: {
      status: input?.status,
      limit: input?.limit ?? 10,
      offset: input?.offset ?? 0
    }
  });
  return response.data;
}

export async function applyOpsObservabilityAnomalyAction(
  input: ApplyOpsObservabilityAnomalyActionInput
): Promise<GetOpsObservabilityConfigOutput> {
  const response = await http.post<GetOpsObservabilityConfigOutput>(
    "/debate/ops/observability/anomaly-state/actions",
    {
      alertKey: input.alertKey,
      action: input.action,
      suppressMinutes: input.suppressMinutes
    }
  );
  return response.data;
}

export async function runOpsObservabilityEvaluationOnce(input?: {
  dryRun?: boolean;
}): Promise<OpsAlertEvalReport> {
  const response = await http.post<OpsAlertEvalReport>("/debate/ops/observability/evaluate-once", undefined, {
    params: {
      dryRun: input?.dryRun ?? false
    }
  });
  return response.data;
}
