import { beforeEach, describe, expect, it, vi } from "vitest";

const apiClient = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn()
}));

vi.mock("@echoisle/api-client", () => ({
  http: {
    get: apiClient.get,
    post: apiClient.post
  }
}));

import { createOpsJudgeCalibrationDecision, getOpsJudgeRuntimeReadiness } from "./runtimeReadiness";

describe("getOpsJudgeRuntimeReadiness", () => {
  beforeEach(() => {
    apiClient.get.mockReset();
    apiClient.post.mockReset();
    apiClient.get.mockResolvedValue({
      data: {
        version: "ai-judge-runtime-readiness-v1",
        status: "env_blocked"
      }
    });
    apiClient.post.mockResolvedValue({
      data: {
        version: "ai-judge-fairness-calibration-decision-log-v1",
        status: "accepted"
      }
    });
  });

  it("should call the ops runtime readiness endpoint with safe defaults", async () => {
    await getOpsJudgeRuntimeReadiness();

    expect(apiClient.get).toHaveBeenCalledWith(
      "/debate/ops/judge-runtime-readiness",
      {
        params: {
          dispatchType: "final",
          policyVersion: undefined,
          windowDays: 7,
          caseScanLimit: 200,
          includeCaseTrust: true,
          trustCaseLimit: 5,
          calibrationRiskLimit: 50,
          panelGroupLimit: 50,
          panelAttentionLimit: 20
        }
      }
    );
  });

  it("should preserve caller supplied runtime readiness filters", async () => {
    await getOpsJudgeRuntimeReadiness({
      dispatchType: "phase",
      policyVersion: "v3-shadow",
      windowDays: 14,
      caseScanLimit: 50,
      includeCaseTrust: false,
      trustCaseLimit: 3,
      calibrationRiskLimit: 8,
      panelGroupLimit: 9,
      panelAttentionLimit: 4
    });

    expect(apiClient.get).toHaveBeenCalledWith(
      "/debate/ops/judge-runtime-readiness",
      {
        params: {
          dispatchType: "phase",
          policyVersion: "v3-shadow",
          windowDays: 14,
          caseScanLimit: 50,
          includeCaseTrust: false,
          trustCaseLimit: 3,
          calibrationRiskLimit: 8,
          panelGroupLimit: 9,
          panelAttentionLimit: 4
        }
      }
    );
  });

  it("should create calibration decisions through the ops-only endpoint with idempotency", async () => {
    await createOpsJudgeCalibrationDecision({
      sourceRecommendationId: "collect-real-env-samples",
      policyVersion: "v3-default",
      decision: "request_more_evidence",
      reasonCode: "calibration_real_samples_missing",
      evidenceRefs: [{ kind: "runtime_readiness", ref: "summary" }],
      localReferenceOnly: true,
      environmentMode: "local_reference",
      idempotencyKey: "calibration-decision-1"
    });

    expect(apiClient.post).toHaveBeenCalledWith(
      "/debate/ops/judge-calibration-decisions",
      {
        sourceRecommendationId: "collect-real-env-samples",
        policyVersion: "v3-default",
        decision: "request_more_evidence",
        reasonCode: "calibration_real_samples_missing",
        evidenceRefs: [{ kind: "runtime_readiness", ref: "summary" }],
        localReferenceOnly: true,
        environmentMode: "local_reference"
      },
      {
        headers: {
          "Idempotency-Key": "calibration-decision-1"
        }
      }
    );
  });
});
