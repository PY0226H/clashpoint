import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  applyOpsObservabilityAnomalyAction,
  createOpsJudgeCalibrationDecision,
  getOpsDomainErrorInfo,
  getOpsMetricsDictionary,
  getOpsObservabilityConfig,
  getOpsJudgeRuntimeReadiness,
  getOpsRbacMe,
  getOpsServiceSplitReadiness,
  getOpsSloSnapshot,
  listOpsJudgeChallengeQueue,
  listOpsRoleAssignments,
  listOpsAlertNotifications,
  listOpsServiceSplitReviewAudits,
  revokeOpsRoleAssignment,
  runOpsObservabilityEvaluationOnce,
  toOpsDomainError,
  upsertOpsServiceSplitReview,
  upsertOpsObservabilityThresholds,
  upsertOpsRoleAssignment,
  type OpsObservabilityThresholds,
  type OpsRole,
  type ListOpsRoleAssignmentsInput
} from "@echoisle/ops-domain";
import { Button, InlineHint, SectionTitle, TextField } from "@echoisle/ui";
import { OpsCalibrationDecisionActions } from "../components/OpsCalibrationDecisionActions";
import {
  buildOpsCalibrationDecisionInput,
  type OpsCalibrationDecisionSubmitPayload
} from "../components/OpsCalibrationDecisionActionsModel";

const ROLE_OPTIONS: OpsRole[] = ["ops_admin", "ops_reviewer", "ops_viewer"];
const ROLE_LIST_PII_OPTIONS = ["minimal", "full"] as const;
const ALERT_STATUS_OPTIONS = ["all", "raised", "suppressed", "cleared"] as const;
const ALERT_PAGE_SIZE_OPTIONS = [1, 3, 5, 10] as const;
const OBSERVABILITY_ERROR_MAX_VISIBLE = 4;
const OBSERVABILITY_ERROR_MAX_CHARS = 120;
const OPS_RBAC_REVISION_CONFLICT_CODE = "ops_rbac_revision_conflict";
const OPS_OBSERVABILITY_REVISION_CONFLICT_CODE = "ops_observability_revision_conflict";
const OPS_OBSERVABILITY_IF_MATCH_REQUIRED_CODE = "ops_observability_if_match_required";
type AlertStatusFilter = (typeof ALERT_STATUS_OPTIONS)[number];
type RoleListPiiLevel = NonNullable<ListOpsRoleAssignmentsInput["piiLevel"]>;
type ThresholdFieldKey = keyof OpsObservabilityThresholds;
type SplitReviewSelection = "unset" | "required" | "not_required";
type SplitReviewAuditComplianceFilter = "all" | "required" | "not_required";

const THRESHOLD_FIELD_ORDER: ThresholdFieldKey[] = [
  "lowSuccessRateThreshold",
  "highRetryThreshold",
  "highCoalescedThreshold",
  "highDbLatencyThresholdMs",
  "lowCacheHitRateThreshold",
  "minRequestForCacheHitCheck"
];

const THRESHOLD_FIELD_LABELS: Record<ThresholdFieldKey, string> = {
  lowSuccessRateThreshold: "Low Success Rate Threshold (%)",
  highRetryThreshold: "High Retry Threshold",
  highCoalescedThreshold: "High Coalesced Threshold",
  highDbLatencyThresholdMs: "High DB Latency Threshold (ms)",
  lowCacheHitRateThreshold: "Low Cache Hit Rate Threshold (%)",
  minRequestForCacheHitCheck: "Min Requests For Cache Hit Check"
};

function formatUtc(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString();
}

function formatDecimal(value: number, digits = 2): string {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "--";
  }
  return num.toFixed(digits);
}

function formatMaybeBoolean(value: boolean | null | undefined): string {
  if (value === true) {
    return "yes";
  }
  if (value === false) {
    return "no";
  }
  return "--";
}

function toObservabilityErrorPreview(message: string): string {
  if (message.length <= OBSERVABILITY_ERROR_MAX_CHARS) {
    return message;
  }
  return `${message.slice(0, OBSERVABILITY_ERROR_MAX_CHARS - 3)}...`;
}

function toThresholdDraft(input: OpsObservabilityThresholds): Record<ThresholdFieldKey, string> {
  return {
    lowSuccessRateThreshold: String(input.lowSuccessRateThreshold),
    highRetryThreshold: String(input.highRetryThreshold),
    highCoalescedThreshold: String(input.highCoalescedThreshold),
    highDbLatencyThresholdMs: String(input.highDbLatencyThresholdMs),
    lowCacheHitRateThreshold: String(input.lowCacheHitRateThreshold),
    minRequestForCacheHitCheck: String(input.minRequestForCacheHitCheck)
  };
}

function parseThresholdDraft(draft: Record<ThresholdFieldKey, string>): OpsObservabilityThresholds | null {
  const lowSuccessRateThreshold = Number(draft.lowSuccessRateThreshold);
  const highRetryThreshold = Number(draft.highRetryThreshold);
  const highCoalescedThreshold = Number(draft.highCoalescedThreshold);
  const highDbLatencyThresholdMs = Number(draft.highDbLatencyThresholdMs);
  const lowCacheHitRateThreshold = Number(draft.lowCacheHitRateThreshold);
  const minRequestForCacheHitCheck = Number(draft.minRequestForCacheHitCheck);

  if (
    !Number.isFinite(lowSuccessRateThreshold) ||
    !Number.isFinite(highRetryThreshold) ||
    !Number.isFinite(highCoalescedThreshold) ||
    !Number.isFinite(highDbLatencyThresholdMs) ||
    !Number.isFinite(lowCacheHitRateThreshold) ||
    !Number.isFinite(minRequestForCacheHitCheck)
  ) {
    return null;
  }

  return {
    lowSuccessRateThreshold,
    highRetryThreshold,
    highCoalescedThreshold,
    highDbLatencyThresholdMs: Math.floor(highDbLatencyThresholdMs),
    lowCacheHitRateThreshold,
    minRequestForCacheHitCheck: Math.floor(minRequestForCacheHitCheck)
  };
}

function toEvaluateActionErrorMessage(error: unknown, dryRun: boolean): string {
  const info = getOpsDomainErrorInfo(error);
  const mode = dryRun ? "dry-run" : "run";
  if (info.status === 429) {
    return `Evaluate ${mode} rejected [rate_limit]: ${info.message}.`;
  }
  if (info.status === 400) {
    return `Evaluate ${mode} rejected [bad_request]: ${info.message}.`;
  }
  return `Evaluate ${mode} rejected [backend]: ${info.message}.`;
}

function toSplitReviewSaveErrorMessage(error: unknown): string {
  const info = getOpsDomainErrorInfo(error);
  if (info.status === 409) {
    return `Split review save rejected [permission_conflict]: ${info.message}.`;
  }
  if (info.status === 400) {
    return `Split review save rejected [bad_request]: ${info.message}.`;
  }
  return `Split review save rejected [backend]: ${info.message}.`;
}

function mapSplitReviewSelectionToPayload(selection: SplitReviewSelection): boolean | null {
  if (selection === "required") {
    return true;
  }
  if (selection === "not_required") {
    return false;
  }
  return null;
}

function mapSplitReviewPayloadToSelection(value: unknown): SplitReviewSelection {
  if (value === true) {
    return "required";
  }
  if (value === false) {
    return "not_required";
  }
  return "unset";
}

function toSplitReviewSelectionLabel(value: unknown): SplitReviewSelection {
  return mapSplitReviewPayloadToSelection(value);
}

function extractSplitReviewThresholdItem(
  input: ReturnType<typeof getOpsServiceSplitReadiness> extends Promise<infer T> ? T : never
): { evidence: Record<string, unknown> } | null {
  const item = input.thresholds.find((threshold) => threshold.key === "payment_compliance_isolation");
  const evidence = item?.evidence;
  if (!evidence || typeof evidence !== "object" || Array.isArray(evidence)) {
    return null;
  }
  return { evidence: evidence as Record<string, unknown> };
}

function extractSplitReviewFromReadiness(input: ReturnType<typeof getOpsServiceSplitReadiness> extends Promise<infer T> ? T : never): {
  selection: SplitReviewSelection;
  note: string;
} {
  const extracted = extractSplitReviewThresholdItem(input);
  if (!extracted) {
    return { selection: "unset", note: "" };
  }
  const paymentValue = extracted.evidence.paymentComplianceRequired;
  const noteRaw = extracted.evidence.reviewNote;
  return {
    selection: mapSplitReviewPayloadToSelection(paymentValue),
    note: typeof noteRaw === "string" ? noteRaw : ""
  };
}

function extractSplitReviewFreshnessHint(
  input: ReturnType<typeof getOpsServiceSplitReadiness> extends Promise<infer T> ? T : never
): string | null {
  const extracted = extractSplitReviewThresholdItem(input);
  if (!extracted) {
    return null;
  }
  const manualInputRequired = extracted.evidence.manualInputRequired === true;
  const stale = extracted.evidence.stale === true;
  const reviewAgeHoursRaw = extracted.evidence.reviewAgeHours;
  const staleThresholdHoursRaw = extracted.evidence.staleThresholdHours;
  const reviewAgeHours =
    typeof reviewAgeHoursRaw === "number" && Number.isFinite(reviewAgeHoursRaw)
      ? Math.max(0, Math.floor(reviewAgeHoursRaw))
      : null;
  const staleThresholdHours =
    typeof staleThresholdHoursRaw === "number" && Number.isFinite(staleThresholdHoursRaw)
      ? Math.max(0, Math.floor(staleThresholdHoursRaw))
      : null;

  if (manualInputRequired) {
    return "split review manual input required.";
  }
  if (stale) {
    if (reviewAgeHours !== null && staleThresholdHours !== null) {
      return `split review is stale (${reviewAgeHours}h >= ${staleThresholdHours}h), please revalidate.`;
    }
    return "split review is stale, please revalidate.";
  }
  return null;
}

export function OpsConsolePage() {
  const queryClient = useQueryClient();
  const [targetUserId, setTargetUserId] = useState("");
  const [targetRole, setTargetRole] = useState<OpsRole>("ops_viewer");
  const [roleListPiiLevel, setRoleListPiiLevel] = useState<RoleListPiiLevel>("minimal");
  const [alertStatusFilter, setAlertStatusFilter] = useState<AlertStatusFilter>("all");
  const [alertPageSize, setAlertPageSize] = useState<number>(3);
  const [alertPageIndex, setAlertPageIndex] = useState(0);
  const [splitReviewSelection, setSplitReviewSelection] = useState<SplitReviewSelection>("unset");
  const [splitReviewNote, setSplitReviewNote] = useState("");
  const [splitReviewAuditPageSize, setSplitReviewAuditPageSize] = useState(3);
  const [splitReviewAuditPageIndex, setSplitReviewAuditPageIndex] = useState(0);
  const [splitReviewAuditComplianceFilter, setSplitReviewAuditComplianceFilter] =
    useState<SplitReviewAuditComplianceFilter>("all");
  const [splitReviewAuditUpdatedByFilter, setSplitReviewAuditUpdatedByFilter] = useState("");
  const [splitReviewAuditCreatedAfterIso, setSplitReviewAuditCreatedAfterIso] = useState("");
  const [splitReviewAuditCreatedBeforeIso, setSplitReviewAuditCreatedBeforeIso] = useState("");
  const [thresholdDraft, setThresholdDraft] = useState<Record<ThresholdFieldKey, string> | null>(null);
  const [thresholdDirty, setThresholdDirty] = useState(false);
  const [suppressMinutesInput, setSuppressMinutesInput] = useState("10");
  const [pageHint, setPageHint] = useState<string | null>(null);

  const rbacMeQuery = useQuery({
    queryKey: ["ops-rbac-me"],
    queryFn: () => getOpsRbacMe(),
    retry: false
  });

  const roleAssignmentsQuery = useQuery({
    queryKey: ["ops-role-assignments", roleListPiiLevel],
    queryFn: () => listOpsRoleAssignments({ piiLevel: roleListPiiLevel }),
    enabled: Boolean(rbacMeQuery.data?.permissions.roleManage),
    retry: false
  });
  const judgeChallengeQueueQuery = useQuery({
    queryKey: ["ops-judge-challenge-queue"],
    queryFn: () =>
      listOpsJudgeChallengeQueue({
        challengeState: "open",
        limit: 5
      }),
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview),
    retry: false
  });
  const judgeRuntimeReadinessQuery = useQuery({
    queryKey: ["ops-judge-runtime-readiness"],
    queryFn: () =>
      getOpsJudgeRuntimeReadiness({
        dispatchType: "final",
        windowDays: 7,
        includeCaseTrust: true,
        trustCaseLimit: 5
      }),
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview),
    retry: false
  });
  const createCalibrationDecisionMutation = useMutation({
    mutationFn: async (payload: OpsCalibrationDecisionSubmitPayload) => {
      const result = await createOpsJudgeCalibrationDecision(
        buildOpsCalibrationDecisionInput({
          runtime: judgeRuntimeReadinessQuery.data,
          action: payload.action,
          decision: payload.decision
        })
      );
      return { payload, result };
    },
    onSuccess: ({ payload, result }) => {
      setPageHint(`Calibration decision ${payload.decision} recorded: ${result.statusReason}.`);
      void queryClient.invalidateQueries({ queryKey: ["ops-judge-runtime-readiness"] });
    },
    onError: (error) => {
      setPageHint(toOpsDomainError(error));
    }
  });
  const observabilityConfigQuery = useQuery({
    queryKey: ["ops-observability-config"],
    queryFn: () => getOpsObservabilityConfig(),
    enabled: Boolean(rbacMeQuery.data?.permissions.observabilityRead),
    retry: false
  });
  const sloSnapshotQuery = useQuery({
    queryKey: ["ops-observability-slo"],
    queryFn: () => getOpsSloSnapshot(),
    enabled: Boolean(rbacMeQuery.data?.permissions.observabilityRead),
    retry: false
  });
  const metricsDictionaryQuery = useQuery({
    queryKey: ["ops-observability-metrics-dictionary"],
    queryFn: () => getOpsMetricsDictionary(),
    enabled: Boolean(rbacMeQuery.data?.permissions.observabilityRead),
    retry: false
  });
  const splitReadinessQuery = useQuery({
    queryKey: ["ops-observability-split-readiness"],
    queryFn: () => getOpsServiceSplitReadiness(),
    enabled: Boolean(rbacMeQuery.data?.permissions.observabilityRead),
    retry: false
  });
  const splitReviewAuditUpdatedBy = useMemo(() => {
    const raw = splitReviewAuditUpdatedByFilter.trim();
    if (!raw) {
      return undefined;
    }
    const parsed = Number(raw);
    if (!Number.isInteger(parsed) || parsed <= 0) {
      return undefined;
    }
    return parsed;
  }, [splitReviewAuditUpdatedByFilter]);
  const splitReviewAuditPaymentFilter =
    splitReviewAuditComplianceFilter === "all"
      ? undefined
      : splitReviewAuditComplianceFilter === "required"
        ? true
        : splitReviewAuditComplianceFilter === "not_required"
          ? false
          : undefined;
  const splitReviewAuditCreatedAfter = splitReviewAuditCreatedAfterIso.trim() || undefined;
  const splitReviewAuditCreatedBefore = splitReviewAuditCreatedBeforeIso.trim() || undefined;
  const splitReviewAuditsQuery = useQuery({
    queryKey: [
      "ops-observability-split-review-audits",
      splitReviewAuditPageSize,
      splitReviewAuditPageIndex,
      splitReviewAuditUpdatedBy,
      splitReviewAuditPaymentFilter,
      splitReviewAuditCreatedAfter,
      splitReviewAuditCreatedBefore
    ],
    queryFn: () =>
      listOpsServiceSplitReviewAudits({
        limit: splitReviewAuditPageSize,
        offset: splitReviewAuditPageIndex * splitReviewAuditPageSize,
        updatedBy: splitReviewAuditUpdatedBy,
        paymentComplianceRequired: splitReviewAuditPaymentFilter,
        createdAfter: splitReviewAuditCreatedAfter,
        createdBefore: splitReviewAuditCreatedBefore
      }),
    enabled: Boolean(rbacMeQuery.data?.permissions.observabilityRead),
    retry: false
  });
  const alertsQuery = useQuery({
    queryKey: ["ops-observability-alerts", alertStatusFilter, alertPageSize, alertPageIndex],
    queryFn: () =>
      listOpsAlertNotifications({
        status: alertStatusFilter === "all" ? undefined : alertStatusFilter,
        limit: alertPageSize,
        offset: alertPageIndex * alertPageSize
      }),
    enabled: Boolean(rbacMeQuery.data?.permissions.observabilityRead),
    retry: false
  });
  const roleWriteRevision = String(
    roleAssignmentsQuery.data?.rbacRevision || rbacMeQuery.data?.rbacRevision || ""
  ).trim();
  const roleWriteRevisionReady = roleWriteRevision.length > 0;

  useEffect(() => {
    setAlertPageIndex(0);
  }, [alertPageSize, alertStatusFilter]);
  useEffect(() => {
    setSplitReviewAuditPageIndex(0);
  }, [
    splitReviewAuditPageSize,
    splitReviewAuditComplianceFilter,
    splitReviewAuditCreatedAfterIso,
    splitReviewAuditCreatedBeforeIso,
    splitReviewAuditUpdatedByFilter
  ]);

  const upsertRoleMutation = useMutation({
    mutationFn: async (payload: { userId: number; role: OpsRole; expectedRevision: string }) =>
      upsertOpsRoleAssignment(payload.userId, payload.role, payload.expectedRevision),
    onSuccess: (result) => {
      setPageHint(`Granted ${result.role} to user #${result.userId}.`);
      setTargetUserId("");
      void queryClient.invalidateQueries({ queryKey: ["ops-role-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["ops-rbac-me"] });
    },
    onError: (error) => {
      const info = getOpsDomainErrorInfo(error);
      if (info.code === OPS_RBAC_REVISION_CONFLICT_CODE) {
        setPageHint("RBAC revision conflict detected. Snapshot refreshed, please retry.");
        void queryClient.invalidateQueries({ queryKey: ["ops-role-assignments"] });
        void queryClient.invalidateQueries({ queryKey: ["ops-rbac-me"] });
        return;
      }
      setPageHint(info.message || toOpsDomainError(error));
    }
  });

  const revokeRoleMutation = useMutation({
    mutationFn: async (payload: { userId: number; expectedRevision: string }) =>
      revokeOpsRoleAssignment(payload.userId, payload.expectedRevision),
    onSuccess: (result) => {
      setPageHint(
        result.removed
          ? `Revoked role from user #${result.userId}.`
          : `No role assignment existed for user #${result.userId}.`
      );
      void queryClient.invalidateQueries({ queryKey: ["ops-role-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["ops-rbac-me"] });
    },
    onError: (error) => {
      const info = getOpsDomainErrorInfo(error);
      if (info.code === OPS_RBAC_REVISION_CONFLICT_CODE) {
        setPageHint("RBAC revision conflict detected. Snapshot refreshed, please retry.");
        void queryClient.invalidateQueries({ queryKey: ["ops-role-assignments"] });
        void queryClient.invalidateQueries({ queryKey: ["ops-rbac-me"] });
        return;
      }
      setPageHint(info.message || toOpsDomainError(error));
    }
  });
  const applyAnomalyActionMutation = useMutation({
    mutationFn: async (payload: {
      alertKey: string;
      action: "acknowledge" | "suppress" | "clear";
      suppressMinutes?: number;
    }) => {
      const ret = await applyOpsObservabilityAnomalyAction(payload);
      return { payload, ret };
    },
    onSuccess: ({ payload }) => {
      setPageHint(`Anomaly action applied: ${payload.action} ${payload.alertKey}.`);
      void invalidateObservabilityQueries();
    },
    onError: (error) => {
      setPageHint(toOpsDomainError(error));
    }
  });
  const evaluateObservabilityMutation = useMutation({
    mutationFn: async (dryRun: boolean) => {
      const report = await runOpsObservabilityEvaluationOnce({ dryRun });
      return { dryRun, report };
    },
    onSuccess: ({ dryRun, report }) => {
      setPageHint(
        `Ops evaluation ${dryRun ? "dry-run" : "run"}: raised=${report.alertsRaised}, cleared=${report.alertsCleared}, suppressed=${report.alertsSuppressed}.`
      );
      void invalidateObservabilityQueries();
    },
    onError: (error, dryRun) => {
      setPageHint(toEvaluateActionErrorMessage(error, dryRun));
    }
  });
  const upsertThresholdMutation = useMutation({
    mutationFn: async (payload: OpsObservabilityThresholds) => {
      const expectedRevision = observabilityConfigQuery.data?.configRevision || "";
      return upsertOpsObservabilityThresholds(payload, expectedRevision);
    },
    onSuccess: (ret) => {
      setThresholdDraft(toThresholdDraft(ret.thresholds));
      setThresholdDirty(false);
      setPageHint("Observability thresholds updated.");
      void invalidateObservabilityQueries();
    },
    onError: (error) => {
      const info = getOpsDomainErrorInfo(error);
      if (info.code === OPS_OBSERVABILITY_REVISION_CONFLICT_CODE) {
        setPageHint("Observability config revision conflict detected. Snapshot refreshed, please retry.");
        void invalidateObservabilityQueries();
        return;
      }
      if (info.code === OPS_OBSERVABILITY_IF_MATCH_REQUIRED_CODE) {
        setPageHint("Observability config revision missing, snapshot refreshed. Please retry.");
        void invalidateObservabilityQueries();
        return;
      }
      setPageHint(toOpsDomainError(error));
    }
  });
  const upsertSplitReviewMutation = useMutation({
    mutationFn: async () =>
      upsertOpsServiceSplitReview({
        paymentComplianceRequired: mapSplitReviewSelectionToPayload(splitReviewSelection),
        reviewNote: splitReviewNote.trim() || null
      }),
    onSuccess: async () => {
      setPageHint("Split readiness review updated.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ops-observability-split-readiness"] }),
        queryClient.invalidateQueries({ queryKey: ["ops-observability-split-review-audits"] })
      ]);
    },
    onError: (error) => {
      setPageHint(toSplitReviewSaveErrorMessage(error));
    }
  });

  const canManageRoles = Boolean(rbacMeQuery.data?.permissions.roleManage);
  const canReadJudgeReview = Boolean(rbacMeQuery.data?.permissions.judgeReview);
  const canReadObservability = Boolean(rbacMeQuery.data?.permissions.observabilityRead);
  const canManageObservability = Boolean(rbacMeQuery.data?.permissions.observabilityManage);
  const permissions = rbacMeQuery.data?.permissions;
  const permissionRows = useMemo(
    () => [
      { key: "debate_manage", value: permissions?.debateManage ?? false },
      { key: "judge_review", value: permissions?.judgeReview ?? false },
      { key: "judge_rejudge", value: permissions?.judgeRejudge ?? false },
      { key: "observability_read", value: permissions?.observabilityRead ?? false },
      { key: "observability_manage", value: permissions?.observabilityManage ?? false },
      { key: "role_manage", value: permissions?.roleManage ?? false }
    ],
    [permissions]
  );
  const activeRuleCount = sloSnapshotQuery.data?.rules.filter((rule) => rule.isActive).length ?? 0;
  const suppressedRuleCount = sloSnapshotQuery.data?.rules.filter((rule) => rule.suppressed).length ?? 0;
  const topDictionaryItems = metricsDictionaryQuery.data?.items.slice(0, 4) || [];
  const topRules = sloSnapshotQuery.data?.rules.slice(0, 4) || [];
  const topAlerts = alertsQuery.data?.items || [];
  const topChallengeItems = judgeChallengeQueueQuery.data?.items || [];
  const runtimeReadiness = judgeRuntimeReadinessQuery.data;
  const runtimeActions = runtimeReadiness?.recommendedActions.slice(0, 4) || [];
  const fairnessCalibrationActions = runtimeActions.filter((action) => action.source === "fairnessCalibrationAdvisor");
  const runtimeReasonCodes = runtimeReadiness?.realEnv.reasonCodes || [];
  const runtimeBlockedComponents = runtimeReadiness?.realEnv.envBlockedComponents || [];
  const runtimeRealEnvStatusCounts = Object.entries(runtimeReadiness?.realEnv.realEnvEvidenceStatusCounts || {})
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([status, count]) => `${status}: ${count}`);
  const totalAlerts = alertsQuery.data?.total ?? 0;
  const alertPageCount = Math.max(1, Math.ceil(totalAlerts / alertPageSize));
  const canGoPrevPage = alertPageIndex > 0;
  const canGoNextPage = alertPageIndex + 1 < alertPageCount;
  const totalSplitReviewAudits = splitReviewAuditsQuery.data?.total ?? 0;
  const splitReviewAuditPageCount = Math.max(1, Math.ceil(totalSplitReviewAudits / splitReviewAuditPageSize));
  const canGoPrevSplitReviewAuditPage = splitReviewAuditPageIndex > 0;
  const canGoNextSplitReviewAuditPage = splitReviewAuditPageIndex + 1 < splitReviewAuditPageCount;
  const splitReviewFreshnessHint = splitReadinessQuery.data
    ? extractSplitReviewFreshnessHint(splitReadinessQuery.data)
    : null;
  const splitReviewAuditItems = splitReviewAuditsQuery.data?.items ?? [];
  const splitReviewAuditPageItemCount = splitReviewAuditItems.length;
  const observabilityErrors = useMemo(() => {
    const seen = new Set<string>();
    const items = [
        observabilityConfigQuery.error ? toOpsDomainError(observabilityConfigQuery.error) : null,
        sloSnapshotQuery.error ? toOpsDomainError(sloSnapshotQuery.error) : null,
        metricsDictionaryQuery.error ? toOpsDomainError(metricsDictionaryQuery.error) : null,
        splitReadinessQuery.error ? toOpsDomainError(splitReadinessQuery.error) : null,
        alertsQuery.error ? toOpsDomainError(alertsQuery.error) : null
      ]
      .filter((item): item is string => Boolean(item))
      .map((message) => message.trim())
      .filter((message) => message.length > 0)
      .filter((message) => {
        if (seen.has(message)) {
          return false;
        }
        seen.add(message);
        return true;
      })
      .map((fullMessage) => ({
        fullMessage,
        previewMessage: toObservabilityErrorPreview(fullMessage)
      }));
    return items;
  }, [
      alertsQuery.error,
      metricsDictionaryQuery.error,
      observabilityConfigQuery.error,
      sloSnapshotQuery.error,
      splitReadinessQuery.error
    ]);
  const visibleObservabilityErrors = observabilityErrors.slice(0, OBSERVABILITY_ERROR_MAX_VISIBLE);
  const hiddenObservabilityErrorCount = Math.max(0, observabilityErrors.length - visibleObservabilityErrors.length);
  const normalizedSuppressMinutes = Math.max(1, Math.min(1440, Math.floor(Number(suppressMinutesInput) || 10)));

  useEffect(() => {
    if (!observabilityConfigQuery.data?.thresholds) {
      return;
    }
    setThresholdDraft(toThresholdDraft(observabilityConfigQuery.data.thresholds));
    setThresholdDirty(false);
  }, [observabilityConfigQuery.data]);
  useEffect(() => {
    if (!splitReadinessQuery.data) {
      return;
    }
    const extracted = extractSplitReviewFromReadiness(splitReadinessQuery.data);
    setSplitReviewSelection(extracted.selection);
    setSplitReviewNote(extracted.note);
  }, [splitReadinessQuery.data]);

  async function invalidateObservabilityQueries() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["ops-observability-config"] }),
      queryClient.invalidateQueries({ queryKey: ["ops-observability-slo"] }),
      queryClient.invalidateQueries({ queryKey: ["ops-observability-metrics-dictionary"] }),
      queryClient.invalidateQueries({ queryKey: ["ops-observability-split-readiness"] }),
      queryClient.invalidateQueries({ queryKey: ["ops-observability-alerts"] })
    ]);
  }

  async function refreshObservability() {
    setPageHint(null);
    await invalidateObservabilityQueries();
    setPageHint("Observability snapshot refreshed.");
  }

  function onThresholdFieldChange(key: ThresholdFieldKey, value: string) {
    setThresholdDraft((prev) => {
      const base = prev || {
        lowSuccessRateThreshold: "",
        highRetryThreshold: "",
        highCoalescedThreshold: "",
        highDbLatencyThresholdMs: "",
        lowCacheHitRateThreshold: "",
        minRequestForCacheHitCheck: ""
      };
      return {
        ...base,
        [key]: value
      };
    });
    setThresholdDirty(true);
  }

  function submitThresholds() {
    if (!thresholdDraft) {
      setPageHint("Threshold snapshot unavailable, please refresh first.");
      return;
    }
    const parsed = parseThresholdDraft(thresholdDraft);
    if (!parsed) {
      setPageHint("Threshold values must be valid numbers.");
      return;
    }
    upsertThresholdMutation.mutate(parsed);
  }

  function resetThresholdDraft() {
    if (!observabilityConfigQuery.data?.thresholds) {
      return;
    }
    setThresholdDraft(toThresholdDraft(observabilityConfigQuery.data.thresholds));
    setThresholdDirty(false);
    setPageHint("Threshold edits reverted.");
  }

  function clearSplitReviewAuditFilters() {
    setSplitReviewAuditComplianceFilter("all");
    setSplitReviewAuditUpdatedByFilter("");
    setSplitReviewAuditCreatedAfterIso("");
    setSplitReviewAuditCreatedBeforeIso("");
    setPageHint("Split review audit filters cleared.");
  }

  return (
    <section className="echo-ops-page">
      <header className="echo-ops-header">
        <SectionTitle>Ops Console</SectionTitle>
        <p>Ops control plane: RBAC, judge runtime readiness, challenge queue, and observability.</p>
      </header>

      <section className="echo-lobby-summary">
        <article>
          <strong>{rbacMeQuery.data?.isOwner ? "YES" : "NO"}</strong>
          <span>Platform Owner</span>
        </article>
        <article>
          <strong>{rbacMeQuery.data?.role || (rbacMeQuery.data?.isOwner ? "owner" : "none")}</strong>
          <span>Current Role</span>
        </article>
        <article>
          <strong>{permissionRows.filter((item) => item.value).length}</strong>
          <span>Granted Permissions</span>
        </article>
      </section>

      <section className="echo-lobby-panel">
        <h3>Permission Snapshot</h3>
        {rbacMeQuery.isLoading ? <InlineHint>Loading RBAC snapshot...</InlineHint> : null}
        {rbacMeQuery.isError ? <p className="echo-error">{toOpsDomainError(rbacMeQuery.error)}</p> : null}
        <div className="echo-ops-permission-grid">
          {permissionRows.map((item) => (
            <article className="echo-topic-item" key={item.key}>
              <h4>{item.key}</h4>
              <InlineHint>{item.value ? "granted" : "denied"}</InlineHint>
            </article>
          ))}
        </div>
        {rbacMeQuery.data?.rbacRevision ? (
          <InlineHint>RBAC revision: {rbacMeQuery.data.rbacRevision}</InlineHint>
        ) : null}
      </section>

      <section className="echo-lobby-panel">
        <h3>Role Assignment</h3>
        {canManageRoles ? (
          <>
            <div className="echo-ops-grant-row">
              <label className="echo-ops-role-label">
                <span>PII Visibility</span>
                <select
                  aria-label="Role List PII Visibility"
                  onChange={(event) => setRoleListPiiLevel(event.target.value as RoleListPiiLevel)}
                  value={roleListPiiLevel}
                >
                  {ROLE_LIST_PII_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {roleListPiiLevel === "full" ? (
              <InlineHint>Full PII mode is enabled for owner troubleshooting.</InlineHint>
            ) : (
              <InlineHint>Minimal mode masks email and fullname by default.</InlineHint>
            )}
            <div className="echo-ops-grant-row">
              <TextField
                aria-label="Target User ID"
                onChange={(event) => setTargetUserId(event.target.value)}
                placeholder="target user id"
                value={targetUserId}
              />
              <label className="echo-ops-role-label">
                <span>Role</span>
                <select
                  aria-label="Target Role"
                  onChange={(event) => setTargetRole(event.target.value as OpsRole)}
                  value={targetRole}
                >
                  {ROLE_OPTIONS.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                disabled={upsertRoleMutation.isPending || !targetUserId.trim() || !roleWriteRevisionReady}
                onClick={() => {
                  if (!roleWriteRevisionReady) {
                    setPageHint("RBAC revision is not ready yet. Please retry in a moment.");
                    return;
                  }
                  upsertRoleMutation.mutate({
                    userId: Number(targetUserId),
                    role: targetRole,
                    expectedRevision: roleWriteRevision
                  });
                }}
                type="button"
              >
                {upsertRoleMutation.isPending ? "Granting..." : "Grant Role"}
              </Button>
            </div>

            {roleAssignmentsQuery.isLoading ? <InlineHint>Loading role assignments...</InlineHint> : null}
            {roleAssignmentsQuery.isError ? (
              <p className="echo-error">{toOpsDomainError(roleAssignmentsQuery.error)}</p>
            ) : null}
            {roleAssignmentsQuery.data?.rbacRevision ? (
              <InlineHint>Role list revision: {roleAssignmentsQuery.data.rbacRevision}</InlineHint>
            ) : null}
            {!roleWriteRevisionReady ? (
              <InlineHint>RBAC revision is loading. Role write actions stay disabled until revision is ready.</InlineHint>
            ) : null}
            <div className="echo-ops-role-list">
              {(roleAssignmentsQuery.data?.items || []).map((item) => (
                <article className="echo-room-message" key={item.userId}>
                  <header>
                    <strong>
                      #{item.userId} | {item.role}
                    </strong>
                    <span>{formatUtc(item.updatedAt)}</span>
                  </header>
                  <p>
                    {item.userFullname || "Unnamed"} | {item.userEmail || "no-email"}
                  </p>
                  <InlineHint>grantedBy: #{item.grantedBy}</InlineHint>
                  <div className="echo-ops-role-actions">
                    <Button
                      disabled={revokeRoleMutation.isPending || !roleWriteRevisionReady}
                      onClick={() => {
                        if (!roleWriteRevisionReady) {
                          setPageHint("RBAC revision is not ready yet. Please retry in a moment.");
                          return;
                        }
                        revokeRoleMutation.mutate({
                          userId: item.userId,
                          expectedRevision: roleWriteRevision
                        });
                      }}
                      type="button"
                    >
                      Revoke #{item.userId}
                    </Button>
                  </div>
                </article>
              ))}
              {!roleAssignmentsQuery.isLoading && (roleAssignmentsQuery.data?.items.length || 0) === 0 ? (
                <InlineHint>No role assignments yet.</InlineHint>
              ) : null}
            </div>
          </>
        ) : (
          <InlineHint>Role management requires `role_manage` permission from platform owner scope.</InlineHint>
        )}
      </section>

      <section className="echo-lobby-panel">
        <h3>Judge Runtime Readiness</h3>
        {canReadJudgeReview ? (
          <>
            <div className="echo-ops-alert-toolbar">
              <Button
                disabled={judgeRuntimeReadinessQuery.isLoading}
                onClick={() => void queryClient.invalidateQueries({ queryKey: ["ops-judge-runtime-readiness"] })}
                type="button"
              >
                Refresh Runtime
              </Button>
              <InlineHint>
                status: {runtimeReadiness?.status || "loading"} | reason: {runtimeReadiness?.statusReason || "--"}
              </InlineHint>
              {runtimeReadiness?.generatedAt ? <InlineHint>generated: {formatUtc(runtimeReadiness.generatedAt)}</InlineHint> : null}
            </div>
            {judgeRuntimeReadinessQuery.isLoading ? <InlineHint>Loading runtime readiness...</InlineHint> : null}
            {judgeRuntimeReadinessQuery.isError ? (
              <p className="echo-error">{toOpsDomainError(judgeRuntimeReadinessQuery.error)}</p>
            ) : null}
            <div className="echo-lobby-summary">
              <article>
                <strong>{runtimeReadiness?.status || "unknown"}</strong>
                <span>Runtime Status</span>
              </article>
              <article>
                <strong>{formatMaybeBoolean(runtimeReadiness?.releaseGate.passed)}</strong>
                <span>Release Gate</span>
              </article>
              <article>
                <strong>{runtimeReadiness?.summary.calibrationHighRiskCount ?? 0}</strong>
                <span>Calibration Risk</span>
              </article>
              <article>
                <strong>{runtimeReadiness?.panelRuntime.attentionGroupCount ?? 0}</strong>
                <span>Panel Attention</span>
              </article>
            </div>

            <div className="echo-ops-observability-grid">
              <article className="echo-topic-item">
                <h4>Release Gate</h4>
                <InlineHint>
                  code: {runtimeReadiness?.releaseGate.code || "--"} | registry:{" "}
                  {runtimeReadiness?.releaseGate.registryStatus || "--"}
                </InlineHint>
                <InlineHint>
                  blocked policies: {runtimeReadiness?.releaseGate.blockedPolicyCount ?? 0} | high risk items:{" "}
                  {runtimeReadiness?.releaseGate.highRiskItemCount ?? 0}
                </InlineHint>
                <InlineHint>
                  evidence: {runtimeReadiness?.releaseGate.releaseReadinessEvidenceCount ?? 0} | artifacts:{" "}
                  {runtimeReadiness?.releaseGate.releaseReadinessArtifactCount ?? 0} | hashes:{" "}
                  {runtimeReadiness?.releaseGate.releaseReadinessManifestHashCount ?? 0}
                </InlineHint>
              </article>

              <article className="echo-topic-item">
                <h4>Fairness Calibration</h4>
                <InlineHint>
                  gate: {formatMaybeBoolean(runtimeReadiness?.fairnessCalibration.gatePassed)} | high risk:{" "}
                  {runtimeReadiness?.fairnessCalibration.highRiskCount ?? 0}
                </InlineHint>
                <InlineHint>
                  actions: {runtimeReadiness?.fairnessCalibration.recommendedActionCount ?? 0} | shadow:{" "}
                  {runtimeReadiness?.fairnessCalibration.panelShadowStatus || "--"}
                </InlineHint>
                <InlineHint>
                  shadow violations: {runtimeReadiness?.fairnessCalibration.shadowThresholdViolationCount ?? 0} | drift breaches:{" "}
                  {runtimeReadiness?.fairnessCalibration.driftBreachCount ?? 0}
                </InlineHint>
                <InlineHint>
                  decisions: {runtimeReadiness?.fairnessCalibration.decisionCount ?? 0} | accepted:{" "}
                  {runtimeReadiness?.fairnessCalibration.acceptedForReviewDecisionCount ?? 0} | blockers:{" "}
                  {runtimeReadiness?.fairnessCalibration.decisionLogBlocksProductionReadyCount ?? 0}
                </InlineHint>
                <OpsCalibrationDecisionActions
                  actions={fairnessCalibrationActions}
                  isPending={createCalibrationDecisionMutation.isPending}
                  onDecision={(payload) => createCalibrationDecisionMutation.mutate(payload)}
                />
              </article>

              <article className="echo-topic-item">
                <h4>Panel Runtime</h4>
                <InlineHint>
                  status: {runtimeReadiness?.panelRuntime.status || "--"} | scanned:{" "}
                  {runtimeReadiness?.panelRuntime.scannedRecordCount ?? 0}
                </InlineHint>
                <InlineHint>
                  ready: {runtimeReadiness?.panelRuntime.readyGroupCount ?? 0} | watch:{" "}
                  {runtimeReadiness?.panelRuntime.watchGroupCount ?? 0} | attention:{" "}
                  {runtimeReadiness?.panelRuntime.attentionGroupCount ?? 0}
                </InlineHint>
                <InlineHint>
                  shadow gate: {formatMaybeBoolean(runtimeReadiness?.panelRuntime.shadowGatePassed)} | mode:{" "}
                  {runtimeReadiness?.panelRuntime.latestShadowRunEnvironmentMode || "--"}
                </InlineHint>
                <InlineHint>
                  candidates: {runtimeReadiness?.panelRuntime.candidateModelGroupCount ?? 0} | blockers:{" "}
                  {runtimeReadiness?.panelRuntime.switchBlockerCount ?? 0} | release blocked:{" "}
                  {runtimeReadiness?.panelRuntime.releaseBlockedGroupCount ?? 0}
                </InlineHint>
              </article>

              <article className="echo-topic-item">
                <h4>Real Environment</h4>
                <InlineHint>
                  status: {runtimeReadiness?.realEnv.status || "--"} | available:{" "}
                  {formatMaybeBoolean(runtimeReadiness?.realEnv.evidenceAvailable)}
                </InlineHint>
                <InlineHint>
                  latest: {runtimeReadiness?.realEnv.latestRunStatus || "--"} | decision:{" "}
                  {runtimeReadiness?.realEnv.latestRunThresholdDecision || "--"} | mode:{" "}
                  {runtimeReadiness?.realEnv.latestRunEnvironmentMode || "--"}
                </InlineHint>
                <InlineHint>
                  reasons: {runtimeReasonCodes.length > 0 ? runtimeReasonCodes.join(", ") : "--"}
                </InlineHint>
                <InlineHint>
                  blocked: {runtimeBlockedComponents.length > 0 ? runtimeBlockedComponents.join(", ") : "--"}
                </InlineHint>
                <InlineHint>
                  evidence states: {runtimeRealEnvStatusCounts.length > 0 ? runtimeRealEnvStatusCounts.join(", ") : "--"}
                </InlineHint>
              </article>

              <article className="echo-topic-item">
                <h4>Trust & Challenge</h4>
                <InlineHint>
                  overall: {runtimeReadiness?.trustAndChallenge.overallStatus || "--"} | public verify:{" "}
                  {runtimeReadiness?.trustAndChallenge.publicVerificationStatus || "--"}
                </InlineHint>
                <InlineHint>
                  artifact store: {runtimeReadiness?.trustAndChallenge.artifactStoreStatus || "--"} | challenge lag:{" "}
                  {runtimeReadiness?.trustAndChallenge.challengeReviewLagStatus || "--"}
                </InlineHint>
                <InlineHint>
                  open challenges: {runtimeReadiness?.trustAndChallenge.openChallengeCount ?? 0} | urgent:{" "}
                  {runtimeReadiness?.trustAndChallenge.urgentChallengeCount ?? 0}
                </InlineHint>
                <InlineHint>
                  production blockers: {runtimeReadiness?.trustAndChallenge.productionBlockerCount ?? 0} | review blockers:{" "}
                  {runtimeReadiness?.trustAndChallenge.reviewBlockerCount ?? 0}
                </InlineHint>
              </article>

              <article className="echo-topic-item">
                <h4>Recommended Actions</h4>
                {runtimeActions.map((action) => (
                  <InlineHint key={action.id}>
                    {action.severity} | {action.code} | {action.status || "open"} | {action.title}
                  </InlineHint>
                ))}
                {runtimeActions.length === 0 ? <InlineHint>No runtime actions.</InlineHint> : null}
                <InlineHint>contract: {runtimeReadiness?.version || "--"}</InlineHint>
              </article>
            </div>
          </>
        ) : (
          <InlineHint>Judge runtime readiness requires `judge_review` permission.</InlineHint>
        )}
      </section>

      <section className="echo-lobby-panel">
        <h3>Judge Challenge Queue</h3>
        {canReadJudgeReview ? (
          <>
            <div className="echo-ops-alert-toolbar">
              <Button
                disabled={judgeChallengeQueueQuery.isLoading}
                onClick={() => void queryClient.invalidateQueries({ queryKey: ["ops-judge-challenge-queue"] })}
                type="button"
              >
                Refresh Challenges
              </Button>
              <InlineHint>
                status: {judgeChallengeQueueQuery.data?.status || "loading"} | reason:{" "}
                {judgeChallengeQueueQuery.data?.statusReason || "--"}
              </InlineHint>
            </div>
            {judgeChallengeQueueQuery.isLoading ? <InlineHint>Loading challenge queue...</InlineHint> : null}
            {judgeChallengeQueueQuery.isError ? (
              <p className="echo-error">{toOpsDomainError(judgeChallengeQueueQuery.error)}</p>
            ) : null}
            <div className="echo-lobby-summary">
              <article>
                <strong>{judgeChallengeQueueQuery.data?.summary.openCount ?? 0}</strong>
                <span>Open Challenges</span>
              </article>
              <article>
                <strong>{judgeChallengeQueueQuery.data?.summary.highPriorityCount ?? 0}</strong>
                <span>High Priority</span>
              </article>
              <article>
                <strong>{judgeChallengeQueueQuery.data?.summary.urgentCount ?? 0}</strong>
                <span>Urgent SLA</span>
              </article>
              <article>
                <strong>{judgeChallengeQueueQuery.data?.summary.oldestOpenAgeMinutes ?? "--"}</strong>
                <span>Oldest Age (min)</span>
              </article>
            </div>
            <div className="echo-ops-role-list">
              {topChallengeItems.map((item) => (
                <article className="echo-room-message" key={`${item.caseId}-${item.traceId || "trace"}`}>
                  <header>
                    <strong>
                      #{item.caseId} | {item.challengeReview.state || "unknown"}
                    </strong>
                    <span>{item.priorityProfile.slaBucket || "unknown"}</span>
                  </header>
                  <p>
                    priority: {item.priorityProfile.level || "--"} | score:{" "}
                    {String(item.priorityProfile.score ?? "--")} | review:{" "}
                    {item.challengeReview.reviewState || "--"}
                  </p>
                  <InlineHint>
                    reasons: {(item.challengeReview.challengeReasons || []).join(", ") || "--"} | actions:{" "}
                    {item.actionHints.join(", ") || "--"}
                  </InlineHint>
                </article>
              ))}
              {!judgeChallengeQueueQuery.isLoading && topChallengeItems.length === 0 ? (
                <InlineHint>No open judge challenges.</InlineHint>
              ) : null}
            </div>
          </>
        ) : (
          <InlineHint>Judge challenge queue requires `judge_review` permission.</InlineHint>
        )}
      </section>

      <section className="echo-lobby-panel">
        <h3>Observability Snapshot</h3>
        {canReadObservability ? (
          <>
            <div className="echo-ops-alert-toolbar">
              <label className="echo-ops-role-label">
                <span>Alert Status</span>
                <select
                  aria-label="Alert Status"
                  onChange={(event) => setAlertStatusFilter(event.target.value as AlertStatusFilter)}
                  value={alertStatusFilter}
                >
                  {ALERT_STATUS_OPTIONS.map((status) => (
                    <option key={status} value={status}>
                      {status}
                    </option>
                  ))}
                </select>
              </label>
              <label className="echo-ops-role-label">
                <span>Alert Page Size</span>
                <select
                  aria-label="Alert Page Size"
                  onChange={(event) => setAlertPageSize(Math.max(1, Number(event.target.value) || 3))}
                  value={String(alertPageSize)}
                >
                  {ALERT_PAGE_SIZE_OPTIONS.map((size) => (
                    <option key={size} value={String(size)}>
                      {size}
                    </option>
                  ))}
                </select>
              </label>
              <div className="echo-ops-alert-pager">
                <Button
                  disabled={alertsQuery.isLoading || !canGoPrevPage}
                  onClick={() => setAlertPageIndex((current) => Math.max(0, current - 1))}
                  type="button"
                >
                  Prev Alerts
                </Button>
                <Button
                  disabled={alertsQuery.isLoading || !canGoNextPage}
                  onClick={() => setAlertPageIndex((current) => current + 1)}
                  type="button"
                >
                  Next Alerts
                </Button>
              </div>
              <Button disabled={alertsQuery.isLoading} onClick={() => void refreshObservability()} type="button">
                Refresh Snapshot
              </Button>
            </div>
            <div className="echo-ops-action-toolbar">
              <label className="echo-ops-role-label">
                <span>Suppress Minutes</span>
                <TextField
                  aria-label="Suppress Minutes"
                  disabled={!canManageObservability}
                  inputMode="numeric"
                  onChange={(event) => setSuppressMinutesInput(event.target.value)}
                  placeholder="10"
                  value={suppressMinutesInput}
                />
              </label>
              <Button
                disabled={evaluateObservabilityMutation.isPending || !canManageObservability}
                onClick={() => evaluateObservabilityMutation.mutate(false)}
                type="button"
              >
                Evaluate Once
              </Button>
              <Button
                disabled={evaluateObservabilityMutation.isPending || !canManageObservability}
                onClick={() => evaluateObservabilityMutation.mutate(true)}
                type="button"
              >
                Evaluate Dry Run
              </Button>
            </div>
            {observabilityConfigQuery.isLoading ||
            sloSnapshotQuery.isLoading ||
            metricsDictionaryQuery.isLoading ||
            splitReadinessQuery.isLoading ||
            alertsQuery.isLoading ? (
              <InlineHint>Loading observability snapshots...</InlineHint>
            ) : null}
            {observabilityErrors.length > 0 ? (
              <div aria-live="polite" className="echo-ops-observability-errors" role="alert">
                <p className="echo-error">
                  Observability snapshot partially unavailable ({observabilityErrors.length} errors).
                </p>
                {visibleObservabilityErrors.map((item) => (
                  <InlineHint key={item.fullMessage}>
                    <span className="echo-ops-observability-error-item" title={item.fullMessage}>
                      {item.previewMessage}
                    </span>
                  </InlineHint>
                ))}
                {hiddenObservabilityErrorCount > 0 ? (
                  <InlineHint>{hiddenObservabilityErrorCount} more errors hidden.</InlineHint>
                ) : null}
              </div>
            ) : null}

            <div className="echo-lobby-summary">
              <article>
                <strong>{formatDecimal(sloSnapshotQuery.data?.signal.successRatePct ?? NaN, 2)}%</strong>
                <span>SLO Success Rate</span>
              </article>
              <article>
                <strong>{formatDecimal(sloSnapshotQuery.data?.signal.p95LatencyMs ?? NaN, 0)} ms</strong>
                <span>Dispatch P95</span>
              </article>
              <article>
                <strong>{activeRuleCount}</strong>
                <span>Active Rules</span>
              </article>
              <article>
                <strong>{splitReadinessQuery.data?.overallStatus || "unknown"}</strong>
                <span>Split Readiness</span>
              </article>
            </div>

            <div className="echo-ops-observability-grid">
              <article className="echo-topic-item">
                <h4>SLO Rules</h4>
                {topRules.map((rule) => (
                  <div className="echo-ops-rule-item" key={rule.alertKey}>
                    <InlineHint>
                      {rule.alertKey} | {rule.status} | {rule.suppressed ? "suppressed" : "live"}
                    </InlineHint>
                    <div className="echo-ops-rule-actions">
                      <Button
                        aria-label={`Acknowledge ${rule.alertKey}`}
                        disabled={applyAnomalyActionMutation.isPending || !canManageObservability}
                        onClick={() =>
                          applyAnomalyActionMutation.mutate({
                            alertKey: rule.alertKey,
                            action: "acknowledge"
                          })
                        }
                        type="button"
                      >
                        Ack {rule.alertKey}
                      </Button>
                      <Button
                        aria-label={`Suppress ${rule.alertKey}`}
                        disabled={applyAnomalyActionMutation.isPending || !canManageObservability}
                        onClick={() =>
                          applyAnomalyActionMutation.mutate({
                            alertKey: rule.alertKey,
                            action: "suppress",
                            suppressMinutes: normalizedSuppressMinutes
                          })
                        }
                        type="button"
                      >
                        Suppress {rule.alertKey}
                      </Button>
                      <Button
                        aria-label={`Clear ${rule.alertKey}`}
                        disabled={applyAnomalyActionMutation.isPending || !canManageObservability}
                        onClick={() =>
                          applyAnomalyActionMutation.mutate({
                            alertKey: rule.alertKey,
                            action: "clear"
                          })
                        }
                        type="button"
                      >
                        Clear {rule.alertKey}
                      </Button>
                    </div>
                  </div>
                ))}
                {topRules.length === 0 ? <InlineHint>No rules.</InlineHint> : null}
                <InlineHint>suppressed count: {suppressedRuleCount}</InlineHint>
              </article>

              <article className="echo-topic-item">
                <h4>Thresholds</h4>
                {thresholdDraft ? (
                  <>
                    <div className="echo-ops-threshold-list">
                      {THRESHOLD_FIELD_ORDER.map((key) => (
                        <label className="echo-ops-threshold-row" key={key}>
                          <span>{THRESHOLD_FIELD_LABELS[key]}</span>
                          <TextField
                            aria-label={`Threshold ${key}`}
                            disabled={!canManageObservability}
                            inputMode="decimal"
                            onChange={(event) => onThresholdFieldChange(key, event.target.value)}
                            type="number"
                            value={thresholdDraft[key]}
                          />
                        </label>
                      ))}
                    </div>
                    <div className="echo-ops-threshold-actions">
                      <Button
                        disabled={
                          upsertThresholdMutation.isPending || !thresholdDirty || !canManageObservability
                        }
                        onClick={submitThresholds}
                        type="button"
                      >
                        {upsertThresholdMutation.isPending ? "Saving..." : "Save Thresholds"}
                      </Button>
                      <Button
                        disabled={!thresholdDirty || upsertThresholdMutation.isPending || !canManageObservability}
                        onClick={resetThresholdDraft}
                        type="button"
                      >
                        Reset Edits
                      </Button>
                    </div>
                    <InlineHint>
                      updatedBy: {String(observabilityConfigQuery.data?.updatedBy ?? "--")} | updatedAt:{" "}
                      {observabilityConfigQuery.data?.updatedAt
                        ? formatUtc(observabilityConfigQuery.data.updatedAt)
                        : "--"}
                    </InlineHint>
                  </>
                ) : (
                  <InlineHint>No threshold snapshot.</InlineHint>
                )}
              </article>

              <article className="echo-topic-item">
                <h4>Metrics Dictionary</h4>
                {topDictionaryItems.map((item) => (
                  <InlineHint key={item.key}>
                    {item.key} ({item.unit}, {item.aggregation})
                  </InlineHint>
                ))}
                <InlineHint>version: {metricsDictionaryQuery.data?.version || "--"}</InlineHint>
              </article>

              <article className="echo-topic-item">
                <h4>Split Review</h4>
                <label className="echo-ops-role-label">
                  <span>Payment Compliance</span>
                  <select
                    aria-label="Split Review Payment Compliance"
                    disabled={!canManageObservability}
                    onChange={(event) => setSplitReviewSelection(event.target.value as SplitReviewSelection)}
                    value={splitReviewSelection}
                  >
                    <option value="unset">unset</option>
                    <option value="required">required</option>
                    <option value="not_required">not_required</option>
                  </select>
                </label>
                <label className="echo-ops-role-label">
                  <span>Review Note</span>
                  <textarea
                    aria-label="Split Review Note"
                    className="echo-room-input"
                    disabled={!canManageObservability}
                    onChange={(event) => setSplitReviewNote(event.target.value)}
                    placeholder="Add split readiness review note"
                    rows={3}
                    value={splitReviewNote}
                  />
                </label>
                <div className="echo-ops-threshold-actions">
                  <Button
                    disabled={upsertSplitReviewMutation.isPending || !canManageObservability}
                    onClick={() => upsertSplitReviewMutation.mutate()}
                    type="button"
                  >
                    {upsertSplitReviewMutation.isPending ? "Saving Review..." : "Save Split Review"}
                  </Button>
                </div>
                {splitReviewAuditsQuery.isError ? (
                  <p className="echo-error">{toOpsDomainError(splitReviewAuditsQuery.error)}</p>
                ) : null}
                <InlineHint>
                  audits: total {totalSplitReviewAudits} | page {splitReviewAuditPageIndex + 1}/{splitReviewAuditPageCount}
                </InlineHint>
                <div className="echo-ops-split-review-filters">
                  <label className="echo-ops-role-label">
                    <span>Compliance Filter</span>
                    <select
                      aria-label="Split Review Compliance Filter"
                      onChange={(event) =>
                        setSplitReviewAuditComplianceFilter(event.target.value as SplitReviewAuditComplianceFilter)
                      }
                      value={splitReviewAuditComplianceFilter}
                    >
                      <option value="all">all</option>
                      <option value="required">required</option>
                      <option value="not_required">not_required</option>
                    </select>
                  </label>
                  <label className="echo-ops-role-label">
                    <span>Updated By</span>
                    <TextField
                      aria-label="Split Review Updated By Filter"
                      inputMode="numeric"
                      onChange={(event) => setSplitReviewAuditUpdatedByFilter(event.target.value)}
                      placeholder="user id"
                      value={splitReviewAuditUpdatedByFilter}
                    />
                  </label>
                  <label className="echo-ops-role-label">
                    <span>Created After (ISO)</span>
                    <TextField
                      aria-label="Split Review Created After ISO"
                      onChange={(event) => setSplitReviewAuditCreatedAfterIso(event.target.value)}
                      placeholder="2026-01-01T01:30:00Z"
                      value={splitReviewAuditCreatedAfterIso}
                    />
                  </label>
                  <label className="echo-ops-role-label">
                    <span>Created Before (ISO)</span>
                    <TextField
                      aria-label="Split Review Created Before ISO"
                      onChange={(event) => setSplitReviewAuditCreatedBeforeIso(event.target.value)}
                      placeholder="2026-01-01T01:40:00Z"
                      value={splitReviewAuditCreatedBeforeIso}
                    />
                  </label>
                  <div className="echo-ops-threshold-actions">
                    <Button onClick={clearSplitReviewAuditFilters} type="button">
                      Clear Audit Filters
                    </Button>
                  </div>
                </div>
                <div className="echo-ops-alert-toolbar">
                  <label className="echo-ops-role-label">
                    <span>Audit Page Size</span>
                    <select
                      aria-label="Split Review Audit Page Size"
                      onChange={(event) => setSplitReviewAuditPageSize(Math.max(1, Number(event.target.value) || 3))}
                      value={String(splitReviewAuditPageSize)}
                    >
                      {ALERT_PAGE_SIZE_OPTIONS.map((size) => (
                        <option key={size} value={String(size)}>
                          {size}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="echo-ops-alert-pager">
                    <Button
                      disabled={splitReviewAuditsQuery.isLoading || !canGoPrevSplitReviewAuditPage}
                      onClick={() => setSplitReviewAuditPageIndex((current) => Math.max(0, current - 1))}
                      type="button"
                    >
                      Prev Audits
                    </Button>
                    <Button
                      disabled={splitReviewAuditsQuery.isLoading || !canGoNextSplitReviewAuditPage}
                      onClick={() => setSplitReviewAuditPageIndex((current) => current + 1)}
                      type="button"
                    >
                      Next Audits
                    </Button>
                  </div>
                </div>
                <div className="echo-ops-review-audit-list">
                  {splitReviewAuditItems.map((item) => (
                    <InlineHint key={item.id}>
                      #{item.id} | compliance:{" "}
                      {toSplitReviewSelectionLabel(item.paymentComplianceRequired)} | by #{item.updatedBy} | at{" "}
                      {formatUtc(item.createdAt)} | note: {item.reviewNote || "--"}
                    </InlineHint>
                  ))}
                  {!splitReviewAuditsQuery.isLoading && splitReviewAuditPageItemCount === 0 ? (
                    <InlineHint>No split review audits.</InlineHint>
                  ) : null}
                </div>
              </article>

              <article className="echo-topic-item">
                <h4>Recent Alerts</h4>
                {topAlerts.map((item) => (
                  <InlineHint key={item.id}>
                    #{item.id} | {item.alertKey} | {item.alertStatus}
                  </InlineHint>
                ))}
                {topAlerts.length === 0 ? <InlineHint>No recent alerts.</InlineHint> : null}
                <InlineHint>
                  total: {alertsQuery.data?.total ?? 0} | page {alertPageIndex + 1}/{alertPageCount}
                </InlineHint>
              </article>
            </div>

            {splitReadinessQuery.data ? (
              <InlineHint>
                next step: {splitReadinessQuery.data.nextStep} (thresholds: {splitReadinessQuery.data.thresholds.length})
              </InlineHint>
            ) : null}
            {splitReviewFreshnessHint ? <InlineHint>{splitReviewFreshnessHint}</InlineHint> : null}
          </>
        ) : (
          <InlineHint>Observability panels require `observability_read` permission.</InlineHint>
        )}
      </section>

      {pageHint ? <InlineHint>{pageHint}</InlineHint> : null}
    </section>
  );
}
