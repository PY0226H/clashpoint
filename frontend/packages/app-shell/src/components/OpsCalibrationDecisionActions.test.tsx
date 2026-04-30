import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { OpsCalibrationDecisionActions } from "./OpsCalibrationDecisionActions";
import {
  buildOpsCalibrationDecisionInput,
  calibrationDecisionReasonForAction
} from "./OpsCalibrationDecisionActionsModel";
import type { GetOpsJudgeRuntimeReadinessOutput, OpsJudgeRuntimeReadinessAction } from "@echoisle/ops-domain";

const shadowAction: OpsJudgeRuntimeReadinessAction = {
  id: "fairness:shadow-drift",
  source: "fairnessCalibrationAdvisor",
  severity: "high",
  code: "panel_shadow_drift",
  title: "Panel shadow drift requires review",
  status: "open"
};

function buildRuntime(status: string): GetOpsJudgeRuntimeReadinessOutput {
  return {
    version: "ops_judge_runtime_readiness_v1",
    generatedAt: null,
    status,
    statusReason: "runtime_env_blocked",
    summary: {
      calibrationHighRiskCount: 1,
      recommendedActionCount: 1,
      panelReadyGroupCount: 0,
      panelWatchGroupCount: 0,
      panelAttentionGroupCount: 1,
      trustChallengeQueueCount: 0,
      productionBlockerCount: 1,
      releaseBlockerCount: 1,
      evidenceBlockerCount: 0
    },
    releaseGate: {
      passed: false,
      code: "blocked",
      registryStatus: "blocked",
      blockedPolicyCount: 1
    },
    fairnessCalibration: {
      gatePassed: false,
      highRiskCount: 1,
      recommendedActionCount: 1,
      panelShadowStatus: "attention"
    },
    panelRuntime: {
      status: "attention",
      readyGroupCount: 0,
      watchGroupCount: 0,
      attentionGroupCount: 1,
      scannedRecordCount: 1
    },
    trustAndChallenge: {
      overallStatus: "ready",
      openChallengeCount: 0,
      urgentChallengeCount: 0,
      trustChallengeQueueCount: 0,
      productionBlockerCount: 0
    },
    realEnv: {
      status: "env_blocked",
      evidenceAvailable: false,
      latestRunEnvironmentMode: null,
      reasonCodes: ["real_env_missing"]
    },
    recommendedActions: [shadowAction],
    evidenceRefs: [],
    visibilityContract: {},
    cacheProfile: {}
  };
}

describe("OpsCalibrationDecisionActions", () => {
  it("maps advisor actions into safe calibration decision payloads", () => {
    const input = buildOpsCalibrationDecisionInput({
      runtime: buildRuntime("env_blocked"),
      action: shadowAction,
      decision: "accept_for_review"
    });

    expect(input).toMatchObject({
      sourceRecommendationId: "fairness:shadow-drift",
      policyVersion: "active",
      decision: "accept_for_review",
      reasonCode: "calibration_shadow_drift",
      localReferenceOnly: true,
      environmentMode: "local_reference"
    });
    expect(input.idempotencyKey).toMatch(/^ops-calibration:fairness:shadow-drift:accept_for_review:/);
    expect(input.evidenceRefs).toEqual([
      {
        kind: "runtime_readiness",
        ref: "runtime_env_blocked",
        status: "env_blocked",
        reasonCode: "panel_shadow_drift"
      }
    ]);
  });

  it("uses manual reject reason over advisor action heuristics", () => {
    expect(calibrationDecisionReasonForAction(shadowAction, "reject")).toBe("calibration_manual_reject");
  });

  it("renders ops-only action buttons without official verdict language", () => {
    const html = renderToStaticMarkup(
      <OpsCalibrationDecisionActions actions={[shadowAction]} onDecision={() => undefined} />
    );

    expect(html).toContain("Accept Review");
    expect(html).toContain("More Evidence");
    expect(html).toContain("fairness:shadow-drift");
    expect(html).not.toContain("Winner");
    expect(html).not.toContain("Official Verdict");
  });
});
