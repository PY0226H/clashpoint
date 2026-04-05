import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  applyOpsObservabilityAnomalyAction,
  getOpsDomainErrorInfo,
  getOpsMetricsDictionary,
  getOpsObservabilityConfig,
  getOpsRbacMe,
  getOpsServiceSplitReadiness,
  getOpsSloSnapshot,
  listOpsRoleAssignments,
  listOpsAlertNotifications,
  revokeOpsRoleAssignment,
  runOpsObservabilityEvaluationOnce,
  toOpsDomainError,
  upsertOpsObservabilityThresholds,
  upsertOpsRoleAssignment,
  type OpsObservabilityThresholds,
  type OpsRole
} from "@echoisle/ops-domain";
import { Button, InlineHint, SectionTitle, TextField } from "@echoisle/ui";

const ROLE_OPTIONS: OpsRole[] = ["ops_admin", "ops_reviewer", "ops_viewer"];
const ALERT_STATUS_OPTIONS = ["all", "raised", "suppressed", "cleared"] as const;
const ALERT_PAGE_SIZE_OPTIONS = [1, 3, 5, 10] as const;
const OBSERVABILITY_ERROR_MAX_VISIBLE = 4;
const OBSERVABILITY_ERROR_MAX_CHARS = 120;
type AlertStatusFilter = (typeof ALERT_STATUS_OPTIONS)[number];
type ThresholdFieldKey = keyof OpsObservabilityThresholds;

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

export function OpsConsolePage() {
  const queryClient = useQueryClient();
  const [targetUserId, setTargetUserId] = useState("");
  const [targetRole, setTargetRole] = useState<OpsRole>("ops_viewer");
  const [alertStatusFilter, setAlertStatusFilter] = useState<AlertStatusFilter>("all");
  const [alertPageSize, setAlertPageSize] = useState<number>(3);
  const [alertPageIndex, setAlertPageIndex] = useState(0);
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
    queryKey: ["ops-role-assignments"],
    queryFn: () => listOpsRoleAssignments(),
    enabled: Boolean(rbacMeQuery.data?.permissions.roleManage),
    retry: false
  });
  const observabilityConfigQuery = useQuery({
    queryKey: ["ops-observability-config"],
    queryFn: () => getOpsObservabilityConfig(),
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview),
    retry: false
  });
  const sloSnapshotQuery = useQuery({
    queryKey: ["ops-observability-slo"],
    queryFn: () => getOpsSloSnapshot(),
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview),
    retry: false
  });
  const metricsDictionaryQuery = useQuery({
    queryKey: ["ops-observability-metrics-dictionary"],
    queryFn: () => getOpsMetricsDictionary(),
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview),
    retry: false
  });
  const splitReadinessQuery = useQuery({
    queryKey: ["ops-observability-split-readiness"],
    queryFn: () => getOpsServiceSplitReadiness(),
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview),
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
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview),
    retry: false
  });

  useEffect(() => {
    setAlertPageIndex(0);
  }, [alertPageSize, alertStatusFilter]);

  const upsertRoleMutation = useMutation({
    mutationFn: async (payload: { userId: number; role: OpsRole }) =>
      upsertOpsRoleAssignment(payload.userId, payload.role),
    onSuccess: (result) => {
      setPageHint(`Granted ${result.role} to user #${result.userId}.`);
      setTargetUserId("");
      void queryClient.invalidateQueries({ queryKey: ["ops-role-assignments"] });
      void queryClient.invalidateQueries({ queryKey: ["ops-rbac-me"] });
    },
    onError: (error) => {
      setPageHint(toOpsDomainError(error));
    }
  });

  const revokeRoleMutation = useMutation({
    mutationFn: async (userId: number) => revokeOpsRoleAssignment(userId),
    onSuccess: (result) => {
      setPageHint(
        result.removed
          ? `Revoked role from user #${result.userId}.`
          : `No role assignment existed for user #${result.userId}.`
      );
      void queryClient.invalidateQueries({ queryKey: ["ops-role-assignments"] });
    },
    onError: (error) => {
      setPageHint(toOpsDomainError(error));
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
    mutationFn: async (payload: OpsObservabilityThresholds) => upsertOpsObservabilityThresholds(payload),
    onSuccess: (ret) => {
      setThresholdDraft(toThresholdDraft(ret.thresholds));
      setThresholdDirty(false);
      setPageHint("Observability thresholds updated.");
      void invalidateObservabilityQueries();
    },
    onError: (error) => {
      setPageHint(toOpsDomainError(error));
    }
  });

  const canManageRoles = Boolean(rbacMeQuery.data?.permissions.roleManage);
  const canReviewJudge = Boolean(rbacMeQuery.data?.permissions.judgeReview);
  const permissions = rbacMeQuery.data?.permissions;
  const permissionRows = useMemo(
    () => [
      { key: "debate_manage", value: permissions?.debateManage ?? false },
      { key: "judge_review", value: permissions?.judgeReview ?? false },
      { key: "judge_rejudge", value: permissions?.judgeRejudge ?? false },
      { key: "role_manage", value: permissions?.roleManage ?? false }
    ],
    [permissions]
  );
  const activeRuleCount = sloSnapshotQuery.data?.rules.filter((rule) => rule.isActive).length ?? 0;
  const suppressedRuleCount = sloSnapshotQuery.data?.rules.filter((rule) => rule.suppressed).length ?? 0;
  const topDictionaryItems = metricsDictionaryQuery.data?.items.slice(0, 4) || [];
  const topRules = sloSnapshotQuery.data?.rules.slice(0, 4) || [];
  const topAlerts = alertsQuery.data?.items || [];
  const totalAlerts = alertsQuery.data?.total ?? 0;
  const alertPageCount = Math.max(1, Math.ceil(totalAlerts / alertPageSize));
  const canGoPrevPage = alertPageIndex > 0;
  const canGoNextPage = alertPageIndex + 1 < alertPageCount;
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

  return (
    <section className="echo-ops-page">
      <header className="echo-ops-header">
        <SectionTitle>Ops Console</SectionTitle>
        <p>Phase 5 ops slice: RBAC capability snapshot and role assignment management.</p>
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
      </section>

      <section className="echo-lobby-panel">
        <h3>Role Assignment</h3>
        {canManageRoles ? (
          <>
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
                disabled={upsertRoleMutation.isPending || !targetUserId.trim()}
                onClick={() =>
                  upsertRoleMutation.mutate({
                    userId: Number(targetUserId),
                    role: targetRole
                  })
                }
                type="button"
              >
                {upsertRoleMutation.isPending ? "Granting..." : "Grant Role"}
              </Button>
            </div>

            {roleAssignmentsQuery.isLoading ? <InlineHint>Loading role assignments...</InlineHint> : null}
            {roleAssignmentsQuery.isError ? (
              <p className="echo-error">{toOpsDomainError(roleAssignmentsQuery.error)}</p>
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
                      disabled={revokeRoleMutation.isPending}
                      onClick={() => revokeRoleMutation.mutate(item.userId)}
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
        <h3>Observability Snapshot</h3>
        {canReviewJudge ? (
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
                  inputMode="numeric"
                  onChange={(event) => setSuppressMinutesInput(event.target.value)}
                  placeholder="10"
                  value={suppressMinutesInput}
                />
              </label>
              <Button
                disabled={evaluateObservabilityMutation.isPending}
                onClick={() => evaluateObservabilityMutation.mutate(false)}
                type="button"
              >
                Evaluate Once
              </Button>
              <Button
                disabled={evaluateObservabilityMutation.isPending}
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
                        disabled={applyAnomalyActionMutation.isPending}
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
                        disabled={applyAnomalyActionMutation.isPending}
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
                        disabled={applyAnomalyActionMutation.isPending}
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
                        disabled={upsertThresholdMutation.isPending || !thresholdDirty}
                        onClick={submitThresholds}
                        type="button"
                      >
                        {upsertThresholdMutation.isPending ? "Saving..." : "Save Thresholds"}
                      </Button>
                      <Button
                        disabled={!thresholdDirty || upsertThresholdMutation.isPending}
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
          </>
        ) : (
          <InlineHint>Observability panels require `judge_review` permission.</InlineHint>
        )}
      </section>

      {pageHint ? <InlineHint>{pageHint}</InlineHint> : null}
    </section>
  );
}
