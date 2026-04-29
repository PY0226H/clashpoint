import { beforeEach, describe, expect, it, vi } from "vitest";

const apiClient = vi.hoisted(() => ({
  get: vi.fn()
}));

vi.mock("@echoisle/api-client", () => ({
  http: {
    get: apiClient.get
  }
}));

import { getOpsJudgeRuntimeReadiness } from "./runtimeReadiness";

describe("getOpsJudgeRuntimeReadiness", () => {
  beforeEach(() => {
    apiClient.get.mockReset();
    apiClient.get.mockResolvedValue({
      data: {
        version: "ai-judge-runtime-readiness-v1",
        status: "env_blocked"
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
});
