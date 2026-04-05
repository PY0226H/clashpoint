import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getOpsMetricsDictionary,
  getOpsObservabilityConfig,
  getOpsRbacMe,
  getOpsServiceSplitReadiness,
  getOpsSloSnapshot,
  listOpsRoleAssignments,
  listOpsAlertNotifications,
  revokeOpsRoleAssignment,
  toOpsDomainError,
  upsertOpsRoleAssignment,
  type OpsRole
} from "@echoisle/ops-domain";
import { Button, InlineHint, SectionTitle, TextField } from "@echoisle/ui";

const ROLE_OPTIONS: OpsRole[] = ["ops_admin", "ops_reviewer", "ops_viewer"];

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

export function OpsConsolePage() {
  const queryClient = useQueryClient();
  const [targetUserId, setTargetUserId] = useState("");
  const [targetRole, setTargetRole] = useState<OpsRole>("ops_viewer");
  const [pageHint, setPageHint] = useState<string | null>(null);

  const rbacMeQuery = useQuery({
    queryKey: ["ops-rbac-me"],
    queryFn: () => getOpsRbacMe()
  });

  const roleAssignmentsQuery = useQuery({
    queryKey: ["ops-role-assignments"],
    queryFn: () => listOpsRoleAssignments(),
    enabled: Boolean(rbacMeQuery.data?.permissions.roleManage)
  });
  const observabilityConfigQuery = useQuery({
    queryKey: ["ops-observability-config"],
    queryFn: () => getOpsObservabilityConfig(),
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview)
  });
  const sloSnapshotQuery = useQuery({
    queryKey: ["ops-observability-slo"],
    queryFn: () => getOpsSloSnapshot(),
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview)
  });
  const metricsDictionaryQuery = useQuery({
    queryKey: ["ops-observability-metrics-dictionary"],
    queryFn: () => getOpsMetricsDictionary(),
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview)
  });
  const splitReadinessQuery = useQuery({
    queryKey: ["ops-observability-split-readiness"],
    queryFn: () => getOpsServiceSplitReadiness(),
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview)
  });
  const alertsQuery = useQuery({
    queryKey: ["ops-observability-alerts", 5, 0],
    queryFn: () => listOpsAlertNotifications({ limit: 5, offset: 0 }),
    enabled: Boolean(rbacMeQuery.data?.permissions.judgeReview)
  });

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
  const topAlerts = alertsQuery.data?.items.slice(0, 3) || [];
  const thresholdRows = observabilityConfigQuery.data
    ? Object.entries(observabilityConfigQuery.data.thresholds)
    : [];

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
            {observabilityConfigQuery.isLoading ||
            sloSnapshotQuery.isLoading ||
            metricsDictionaryQuery.isLoading ||
            splitReadinessQuery.isLoading ||
            alertsQuery.isLoading ? (
              <InlineHint>Loading observability snapshots...</InlineHint>
            ) : null}
            {observabilityConfigQuery.isError ? (
              <p className="echo-error">{toOpsDomainError(observabilityConfigQuery.error)}</p>
            ) : null}
            {sloSnapshotQuery.isError ? <p className="echo-error">{toOpsDomainError(sloSnapshotQuery.error)}</p> : null}
            {metricsDictionaryQuery.isError ? (
              <p className="echo-error">{toOpsDomainError(metricsDictionaryQuery.error)}</p>
            ) : null}
            {splitReadinessQuery.isError ? (
              <p className="echo-error">{toOpsDomainError(splitReadinessQuery.error)}</p>
            ) : null}
            {alertsQuery.isError ? <p className="echo-error">{toOpsDomainError(alertsQuery.error)}</p> : null}

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
                  <InlineHint key={rule.alertKey}>
                    {rule.alertKey} | {rule.status} | {rule.suppressed ? "suppressed" : "live"}
                  </InlineHint>
                ))}
                {topRules.length === 0 ? <InlineHint>No rules.</InlineHint> : null}
                <InlineHint>suppressed count: {suppressedRuleCount}</InlineHint>
              </article>

              <article className="echo-topic-item">
                <h4>Thresholds</h4>
                {thresholdRows.map(([key, value]) => (
                  <InlineHint key={key}>
                    {key}: {String(value)}
                  </InlineHint>
                ))}
                {thresholdRows.length === 0 ? <InlineHint>No threshold snapshot.</InlineHint> : null}
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
                <InlineHint>total: {alertsQuery.data?.total ?? 0}</InlineHint>
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
