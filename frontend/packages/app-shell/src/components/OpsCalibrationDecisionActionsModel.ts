import {
  type CreateOpsJudgeCalibrationDecisionInput,
  type GetOpsJudgeRuntimeReadinessOutput,
  type OpsJudgeCalibrationDecision,
  type OpsJudgeCalibrationDecisionReasonCode,
  type OpsJudgeRuntimeReadinessAction
} from "@echoisle/ops-domain";

export type OpsCalibrationDecisionSubmitPayload = {
  action: OpsJudgeRuntimeReadinessAction;
  decision: OpsJudgeCalibrationDecision;
};

type BuildOpsCalibrationDecisionInputArgs = {
  runtime?: GetOpsJudgeRuntimeReadinessOutput;
  action: OpsJudgeRuntimeReadinessAction;
  decision: OpsJudgeCalibrationDecision;
};

export function calibrationDecisionReasonForAction(
  action: OpsJudgeRuntimeReadinessAction,
  decision: OpsJudgeCalibrationDecision
): OpsJudgeCalibrationDecisionReasonCode {
  if (decision === "reject") {
    return "calibration_manual_reject";
  }
  const code = `${action.code || ""} ${action.title || ""}`.toLowerCase();
  if (code.includes("shadow") || code.includes("drift")) {
    return "calibration_shadow_drift";
  }
  if (code.includes("release")) {
    return "calibration_release_gate_blocked";
  }
  if (code.includes("sample") || code.includes("real_env") || code.includes("environment")) {
    return "calibration_real_samples_missing";
  }
  return "calibration_local_reference_only";
}

export function buildCalibrationDecisionIdempotencyKey(
  actionId: string,
  decision: OpsJudgeCalibrationDecision
): string {
  const random = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `ops-calibration:${actionId}:${decision}:${random}`;
}

export function buildOpsCalibrationDecisionInput({
  runtime,
  action,
  decision
}: BuildOpsCalibrationDecisionInputArgs): CreateOpsJudgeCalibrationDecisionInput {
  const environmentMode =
    runtime?.realEnv.latestRunEnvironmentMode ||
    (runtime?.status === "local_reference_only" || runtime?.status === "env_blocked" ? "local_reference" : undefined);
  const localReferenceOnly =
    environmentMode !== "production" ||
    runtime?.status === "local_reference_only" ||
    runtime?.status === "env_blocked" ||
    runtime?.realEnv.status === "env_blocked";

  return {
    sourceRecommendationId: action.id,
    policyVersion: "active",
    decision,
    reasonCode: calibrationDecisionReasonForAction(action, decision),
    evidenceRefs: [
      {
        kind: "runtime_readiness",
        ref: runtime?.statusReason || "runtime_readiness",
        status: runtime?.status || "unknown",
        reasonCode: action.code
      }
    ],
    localReferenceOnly,
    environmentMode,
    idempotencyKey: buildCalibrationDecisionIdempotencyKey(action.id, decision)
  };
}
