import { http } from "@echoisle/api-client";

import type { JsonValue } from "./json";

export type GetOpsJudgeRuntimeReadinessInput = {
  dispatchType?: "final" | "phase";
  policyVersion?: string;
  windowDays?: number;
  caseScanLimit?: number;
  includeCaseTrust?: boolean;
  trustCaseLimit?: number;
  calibrationRiskLimit?: number;
  panelGroupLimit?: number;
  panelAttentionLimit?: number;
};

export type OpsJudgeRuntimeReadinessSummary = {
  calibrationGatePassed?: boolean | null;
  calibrationHighRiskCount: number;
  recommendedActionCount: number;
  registryPromptToolRiskCount?: number;
  registryPromptToolHighRiskCount?: number;
  panelReadyGroupCount: number;
  panelWatchGroupCount: number;
  panelAttentionGroupCount: number;
  reviewQueueCount?: number;
  reviewHighRiskCount?: number;
  evidenceClaimQueueCount?: number;
  trustChallengeQueueCount: number;
  productionBlockerCount: number;
  releaseBlockerCount: number;
  evidenceBlockerCount: number;
};

export type OpsJudgeRuntimeReadinessReleaseGate = {
  passed?: boolean | null;
  code?: string | null;
  registryStatus?: string | null;
  blockedPolicyCount: number;
  missingKernelBindingCount?: number;
  highRiskItemCount?: number;
  overrideAppliedPolicyCount?: number;
  releaseReadinessEvidenceVersion?: string | null;
  releaseReadinessEvidenceCount?: number;
  releaseReadinessArtifactCount?: number;
  releaseReadinessManifestHashCount?: number;
  reasonCodes?: string[];
};

export type OpsJudgeRuntimeReadinessFairnessCalibration = {
  gatePassed?: boolean | null;
  gateCode?: string | null;
  highRiskCount: number;
  recommendedActionCount: number;
  panelShadowStatus?: string | null;
  shadowRunCount?: number;
  shadowThresholdViolationCount?: number;
  driftBreachCount?: number;
  realSampleManifestStatus?: string | null;
  decisionCount?: number;
  acceptedForReviewDecisionCount?: number;
  productionReadyDecisionCount?: number;
  decisionLogBlocksProductionReadyCount?: number;
};

export type OpsJudgeRuntimeReadinessPanelRuntime = {
  status?: string | null;
  readyGroupCount: number;
  watchGroupCount: number;
  attentionGroupCount: number;
  scannedRecordCount: number;
  shadowGateApplied?: boolean;
  shadowGatePassed?: boolean | null;
  latestShadowRunStatus?: string | null;
  latestShadowRunThresholdDecision?: string | null;
  latestShadowRunEnvironmentMode?: string | null;
  candidateModelGroupCount?: number;
  switchBlockerCount?: number;
  releaseBlockedGroupCount?: number;
  avgShadowDecisionAgreement?: number;
  avgShadowCostEstimate?: number;
  avgShadowLatencyEstimate?: number;
  autoSwitchAllowed?: boolean;
  officialWinnerSemanticsChanged?: boolean;
};

export type OpsJudgeRuntimeReadinessTrustAndChallenge = {
  overallStatus?: string | null;
  artifactStoreStatus?: string | null;
  publicVerificationStatus?: string | null;
  challengeReviewLagStatus?: string | null;
  sampledCaseCount?: number;
  publicVerifiedCount?: number;
  publicVerificationFailedCount?: number;
  openChallengeCount: number;
  urgentChallengeCount: number;
  highPriorityChallengeCount?: number;
  trustChallengeQueueCount: number;
  productionBlockerCount: number;
  reviewBlockerCount?: number;
};

export type OpsJudgeRuntimeReadinessRealEnv = {
  status?: string | null;
  evidenceAvailable: boolean;
  latestRunStatus?: string | null;
  latestRunThresholdDecision?: string | null;
  latestRunEnvironmentMode?: string | null;
  latestRunNeedsRemediation?: boolean | null;
  realSampleManifestStatus?: string | null;
  citationVerifierStatus?: string | null;
  citationVerifierMissingCitationCount?: number;
  citationVerifierWeakCitationCount?: number;
  citationVerifierForbiddenSourceCount?: number;
  envBlockedComponents?: string[];
  reasonCodes?: string[];
};

export type OpsJudgeRuntimeReadinessAction = {
  id: string;
  source: string;
  severity: string;
  code: string;
  title: string;
  owner?: string | null;
  status?: string | null;
};

export type GetOpsJudgeRuntimeReadinessOutput = {
  version: string;
  generatedAt?: string | null;
  status: string;
  statusReason: string;
  summary: OpsJudgeRuntimeReadinessSummary;
  releaseGate: OpsJudgeRuntimeReadinessReleaseGate;
  fairnessCalibration: OpsJudgeRuntimeReadinessFairnessCalibration;
  panelRuntime: OpsJudgeRuntimeReadinessPanelRuntime;
  trustAndChallenge: OpsJudgeRuntimeReadinessTrustAndChallenge;
  realEnv: OpsJudgeRuntimeReadinessRealEnv;
  recommendedActions: OpsJudgeRuntimeReadinessAction[];
  evidenceRefs: JsonValue[];
  visibilityContract: JsonValue;
  cacheProfile: JsonValue;
};

export async function getOpsJudgeRuntimeReadiness(
  input?: GetOpsJudgeRuntimeReadinessInput
): Promise<GetOpsJudgeRuntimeReadinessOutput> {
  const response = await http.get<GetOpsJudgeRuntimeReadinessOutput>(
    "/debate/ops/judge-runtime-readiness",
    {
      params: {
        dispatchType: input?.dispatchType ?? "final",
        policyVersion: input?.policyVersion,
        windowDays: input?.windowDays ?? 7,
        caseScanLimit: input?.caseScanLimit ?? 200,
        includeCaseTrust: input?.includeCaseTrust ?? true,
        trustCaseLimit: input?.trustCaseLimit ?? 5,
        calibrationRiskLimit: input?.calibrationRiskLimit ?? 50,
        panelGroupLimit: input?.panelGroupLimit ?? 50,
        panelAttentionLimit: input?.panelAttentionLimit ?? 20
      }
    }
  );
  return response.data;
}
