import { beforeEach, describe, expect, it, vi } from "vitest";

const apiClient = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock("@echoisle/api-client", () => ({
  http: {
    get: apiClient.get,
    post: apiClient.post,
  },
  toApiError: (error: unknown) =>
    error instanceof Error ? error.message : "request failed",
}));

import {
  DEBATE_NPC_ACTION_CREATED_EVENT,
  assertDebateAssistantOutput,
  assertJudgeAssistantAdvisoryOutput,
  getOldestDebateMessageId,
  isDebateNpcActionCreatedPayload,
  requestDebateAssistant,
  requestDebateAssistantStatus,
  requestNpcCoachAdvice,
  requestRoomQaAnswer,
  mergeDebateMessages,
  normalizeDebateSide,
  normalizeDebateStatusFilter,
  resolveDebateAssistantView,
  resolveJudgeAssistantAdvisoryView,
  resolveDebateJudgeChallengeView,
  resolveDebateJudgePublicVerificationView,
  type DebateAssistantOutput,
  type JudgeAssistantAdvisoryOutput,
  type JsonValue,
} from "./index";

function advisoryOutput(
  agentKind: "npc_coach" | "room_qa",
  overrides?: Partial<JudgeAssistantAdvisoryOutput>,
): JudgeAssistantAdvisoryOutput {
  const roomContextSnapshot = {
    sessionId: 9,
    scopeId: 1,
    caseId: 42,
    workflowStatus: "not_ready",
    latestDispatchType: "final",
    topicDomain: "public-policy",
    phaseReceiptCount: 0,
    finalReceiptCount: 1,
    updatedAt: null,
    officialVerdictFieldsRedacted: true,
  };
  return {
    version: "assistant_advisory_contract_v1",
    agentKind,
    sessionId: 9,
    caseId: 42,
    advisoryOnly: true,
    status: "not_ready",
    statusReason: "agent_not_enabled",
    accepted: false,
    errorCode: "agent_not_enabled",
    errorMessage: null,
    capabilityBoundary: {
      mode: "advisory_only",
      advisoryOnly: true,
      officialVerdictAuthority: false,
      writesVerdictLedger: false,
      writesJudgeTrace: false,
    },
    sharedContext: roomContextSnapshot,
    advisoryContext: {
      advisoryOnly: true,
      roomContextSnapshot,
      stageSummary: {
        stage: "final_context_available",
        workflowStatus: "not_ready",
        latestDispatchType: "final",
        hasPhaseReceipt: false,
        hasFinalReceipt: true,
        officialVerdictFieldsRedacted: true,
      },
      versionContext: {
        ruleVersion: "rule-v1",
        rubricVersion: "rubric-v1",
        judgePolicyVersion: "judge-policy-v1",
      },
      knowledgeGateway: {
        advisoryOnly: true,
      },
      readPolicy: {
        officialJudgeFeedbackAllowed: false,
      },
    },
    output: {},
    cacheProfile: {
      cacheable: false,
      ttlSeconds: 0,
      staleWhileRevalidateSeconds: 0,
    },
    ...overrides,
  };
}

function debateAssistantTranscriptContext(sessionId = 9): JsonValue {
  return {
    version: "assistant_room_transcript_context_v1",
    sessionId,
    topic: {
      title: "是否应开放校园手机使用",
      description: "围绕学习效率与自主权展开辩论",
      category: "education",
      stancePro: "应该开放",
      stanceCon: "不应开放",
    },
    session: {
      status: "running",
      scheduledStartAt: null,
      actualStartAt: "2026-05-06T01:00:00Z",
      endAt: "2026-05-06T02:00:00Z",
    },
    viewer: {
      userId: 7,
      role: "participant",
      side: "pro",
    },
    recentMessages: [
      {
        messageId: 1,
        sessionId,
        userId: 8,
        side: "con",
        content: "手机会分散注意力。",
        createdAt: "2026-05-06T01:03:00Z",
      },
    ],
    messageWindow: {
      limit: 60,
      order: "asc",
      truncated: false,
      latestMessageId: 1,
    },
    redaction: {
      publicOnly: true,
      privateFieldsRedacted: true,
      officialVerdictFieldsRedacted: true,
      membershipSignalsRedacted: true,
    },
  };
}

function debateAssistantOutput(
  overrides?: Partial<DebateAssistantOutput>,
): DebateAssistantOutput {
  const context = debateAssistantTranscriptContext();
  return {
    version: "debate_assistant_contract_v1",
    agentKind: "debate_assistant",
    sessionId: 9,
    caseId: 42,
    advisoryOnly: true,
    status: "ok",
    statusReason: "debate_assistant_ready",
    accepted: true,
    errorCode: null,
    errorMessage: null,
    capabilityBoundary: {
      mode: "advisory_only",
      advisoryOnly: true,
      officialVerdictAuthority: false,
      writesVerdictLedger: false,
      writesJudgeTrace: false,
      canTriggerOfficialJudgeRoles: false,
    },
    sharedContext: context,
    advisoryContext: {
      roomTranscriptContext: context,
      request: {
        intent: "room_summary",
      },
    },
    output: {
      accepted: true,
      intent: "room_summary",
      answerSummary: "当前争点集中在学习效率与学生自主权的权衡。",
      keyPoints: ["对方强调注意力风险。", "我方可以补充自主管理条件。"],
      suggestedActions: ["先承认风险，再提出管理边界。"],
      contextCaveats: ["仅基于当前公开发言。"],
      boundaryNotice: "私人辅助，不代表官方裁决；不会自动发送公开发言。",
      sourceUsePolicy: "仅基于当前房间公开内容和用户输入。",
    },
    cacheProfile: {
      cacheable: false,
      ttlSeconds: 0,
      staleWhileRevalidateSeconds: 0,
      cacheKey: "debate-assistant:session:9",
      varyBy: ["authorization", "sessionId", "intent"],
    },
    ...overrides,
  };
}

describe("debate-domain normalize helpers", () => {
  beforeEach(() => {
    apiClient.get.mockReset();
    apiClient.post.mockReset();
  });

  it("normalizes unknown status to all", () => {
    expect(normalizeDebateStatusFilter("invalid")).toBe("all");
  });

  it("normalizes known status with case-insensitive input", () => {
    expect(normalizeDebateStatusFilter("Running")).toBe("running");
    expect(normalizeDebateStatusFilter(" CLOSED ")).toBe("closed");
    expect(normalizeDebateStatusFilter("scheduled")).toBe("scheduled");
  });

  it("normalizes debate side to pro/con", () => {
    expect(normalizeDebateSide("con")).toBe("con");
    expect(normalizeDebateSide("anything")).toBe("pro");
  });

  it("accepts virtual judge NPC visible room payload", () => {
    expect(
      isDebateNpcActionCreatedPayload({
        event: DEBATE_NPC_ACTION_CREATED_EVENT,
        actionId: 301,
        actionUid: "npc-action-301",
        sessionId: 15,
        npcId: "virtual_judge_default",
        displayName: "虚拟裁判",
        actionType: "praise",
        publicText: "这段反驳很漂亮。",
        targetMessageId: 100,
        targetUserId: 7,
        targetSide: "pro",
        effectKind: "sparkle",
        npcStatus: "praising",
        reasonCode: "strong_rebuttal",
        createdAt: "2026-05-03T09:00:00Z",
      }),
    ).toBe(true);
  });

  it("accepts virtual judge NPC pause suggestion payload", () => {
    expect(
      isDebateNpcActionCreatedPayload({
        event: DEBATE_NPC_ACTION_CREATED_EVENT,
        actionId: 302,
        actionUid: "npc-action-302",
        sessionId: 15,
        npcId: "virtual_judge_default",
        displayName: "虚拟裁判",
        actionType: "pause_suggestion",
        publicText: "建议大家先做一次短暂停顿评估，再继续推进论点。",
        targetMessageId: null,
        targetUserId: null,
        targetSide: null,
        effectKind: null,
        npcStatus: "speaking",
        reasonCode: "rule_public_call_pause_review",
        createdAt: "2026-05-03T09:01:00Z",
      }),
    ).toBe(true);
  });

  it("rejects virtual judge NPC payload with official verdict or internal fields", () => {
    const payload = {
      event: DEBATE_NPC_ACTION_CREATED_EVENT,
      actionId: 301,
      actionUid: "npc-action-301",
      sessionId: 15,
      npcId: "virtual_judge_default",
      displayName: "虚拟裁判",
      actionType: "praise",
      publicText: "这段反驳很漂亮。",
      targetMessageId: 100,
      targetUserId: 7,
      targetSide: "pro",
      effectKind: "sparkle",
      npcStatus: "praising",
      reasonCode: "strong_rebuttal",
      createdAt: "2026-05-03T09:00:00Z",
      policyVersion: "internal-policy-v1",
      executorVersion: "llm-executor-v1",
      traceId: "trace-hidden",
      winner: "pro",
    };

    expect(isDebateNpcActionCreatedPayload(payload)).toBe(false);
  });

  it("merges messages by id and keeps ascending order", () => {
    const merged = mergeDebateMessages(
      [
        {
          id: 2,
          sessionId: 9,
          userId: 1,
          side: "pro",
          content: "old",
          createdAt: "2026-01-01T00:00:00Z",
        },
      ],
      [
        {
          id: 1,
          sessionId: 9,
          userId: 2,
          side: "con",
          content: "first",
          createdAt: "2026-01-01T00:00:00Z",
        },
        {
          id: 2,
          sessionId: 9,
          userId: 1,
          side: "pro",
          content: "new",
          createdAt: "2026-01-01T00:00:02Z",
        },
      ],
    );

    expect(merged.map((item) => item.id)).toEqual([1, 2]);
    expect(merged[1]?.content).toBe("new");
  });

  it("returns oldest message id", () => {
    expect(
      getOldestDebateMessageId([
        {
          id: 8,
          sessionId: 1,
          userId: 1,
          side: "pro",
          content: "A",
          createdAt: "",
        },
        {
          id: 3,
          sessionId: 1,
          userId: 2,
          side: "con",
          content: "B",
          createdAt: "",
        },
        {
          id: 6,
          sessionId: 1,
          userId: 2,
          side: "con",
          content: "C",
          createdAt: "",
        },
      ]),
    ).toBe(3);
  });

  it("resolves ready public verification summary from allowlisted fields", () => {
    const view = resolveDebateJudgePublicVerificationView({
      sessionId: 9,
      status: "ready",
      statusReason: "public_verify_ready",
      caseId: 42,
      dispatchType: "final",
      verificationReadiness: {
        ready: true,
        status: "ready",
        blockers: [],
        externalizable: true,
      },
      cacheProfile: {
        cacheable: true,
        ttlSeconds: 60,
        staleWhileRevalidateSeconds: 120,
        cacheKey: "public-verify:42",
        varyBy: ["dispatchType"],
      },
      publicVerify: {
        verificationVersion: "trust-public-v1",
        verifyPayload: {
          checksum: "sha256:case-42",
          provider: "hidden-upstream",
        },
      },
    });

    expect(view.state).toBe("ready");
    expect(view.label).toBe("Publicly verifiable");
    expect(view.caseId).toBe(42);
    expect(view.verificationVersion).toBe("trust-public-v1");
    expect(view.hashSummary).toBe("sha256:case-42");
    expect(view.cacheable).toBe(true);
  });

  it("maps absent and proxy error public verification states without leaking raw payload", () => {
    const absent = resolveDebateJudgePublicVerificationView({
      sessionId: 9,
      status: "absent",
      statusReason: "public_verify_case_absent",
      caseId: null,
      dispatchType: "final",
      verificationReadiness: {
        ready: false,
        status: "absent",
        blockers: ["public_verify_case_absent"],
      },
      cacheProfile: {
        cacheable: false,
        ttlSeconds: 0,
        staleWhileRevalidateSeconds: 0,
      },
      publicVerify: {},
    });
    expect(absent.state).toBe("no_report");
    expect(absent.label).toBe("No judge report yet");
    expect(absent.blockers).toEqual(["public_verify_case_absent"]);

    const proxyError = resolveDebateJudgePublicVerificationView({
      sessionId: 9,
      status: "proxy_error",
      statusReason: "public_verify_proxy_failed",
      caseId: 42,
      dispatchType: "final",
      verificationReadiness: {
        ready: false,
        status: "proxy_error",
        blockers: ["public_verify_proxy_failed"],
      },
      cacheProfile: {
        cacheable: false,
        ttlSeconds: 0,
        staleWhileRevalidateSeconds: 0,
      },
      publicVerify: {
        provider: "must-not-render",
        rawTrace: "must-not-render",
      },
    });
    expect(proxyError.state).toBe("proxy_error");
    expect(proxyError.label).toBe("Verification unavailable");
    expect(proxyError.hashSummary).toBeNull();
    expect(proxyError.verificationVersion).toBeNull();
  });

  it("resolves eligible challenge status into a requestable view", () => {
    const view = resolveDebateJudgeChallengeView({
      sessionId: 9,
      status: "eligible",
      statusReason: "challenge_eligible",
      caseId: 42,
      dispatchType: "final",
      eligibility: {
        status: "eligible",
        eligible: true,
        requestable: true,
        reasonCode: null,
        blockers: [],
      },
      challenge: {
        state: "not_challenged",
        activeChallengeId: null,
        latestChallengeId: null,
        latestDecision: null,
        latestReasonCode: null,
        totalChallenges: 0,
      },
      review: {
        state: "not_required",
        required: false,
        workflowStatus: null,
      },
      allowedActions: ["challenge.view", "challenge.request"],
      blockers: [],
      cacheProfile: {
        cacheable: false,
        ttlSeconds: 0,
        staleIfErrorSeconds: 0,
      },
      policy: {
        policyStatus: "enabled",
        challengeWindow: "open",
      },
      reviewDecisionSync: {
        version: "trust-challenge-review-decision-sync-v1",
        syncState: "not_available",
        result: "none",
        userVisibleStatus: "not_available",
      },
    });

    expect(view.state).toBe("eligible");
    expect(view.label).toBe("Challenge available");
    expect(view.requestable).toBe(true);
    expect(view.caseId).toBe(42);
    expect(view.reviewSyncState).toBe("not_available");
    expect(view.blockerLabels).toEqual([]);
  });

  it("maps challenge review states and blockers without exposing raw internals", () => {
    const open = resolveDebateJudgeChallengeView({
      sessionId: 9,
      status: "under_review",
      statusReason: "challenge_duplicate_open",
      caseId: 42,
      dispatchType: "final",
      eligibility: {
        status: "under_review",
        eligible: false,
        requestable: false,
        reasonCode: "challenge_duplicate_open",
        blockers: ["challenge_duplicate_open"],
      },
      challenge: {
        state: "under_internal_review",
        activeChallengeId: "challenge-1",
        latestChallengeId: "challenge-1",
        latestDecision: null,
        latestReasonCode: "manual_challenge",
        totalChallenges: 1,
      },
      review: {
        state: "pending_review",
        required: true,
        workflowStatus: "review_required",
      },
      allowedActions: ["challenge.view", "review.view"],
      blockers: ["challenge_duplicate_open"],
      cacheProfile: {
        cacheable: false,
        ttlSeconds: 0,
        staleIfErrorSeconds: 0,
      },
      policy: {
        policyStatus: "enabled",
        provider: "must-not-render",
      },
      reviewDecisionSync: {
        version: "trust-challenge-review-decision-sync-v1",
        syncState: "pending_review",
        result: "none",
        userVisibleStatus: "review_required",
        nextStep: "await_review_decision",
      },
    });

    expect(open.state).toBe("under_review");
    expect(open.label).toBe("Review in progress");
    expect(open.requestable).toBe(false);
    expect(open.reviewVisibleStatus).toBe("review_required");
    expect(open.blockerLabels).toEqual(["A challenge is already open"]);

    const overturned = resolveDebateJudgeChallengeView({
      ...{
        sessionId: 9,
        status: "closed",
        statusReason: "challenge_review_already_closed",
        caseId: 42,
        dispatchType: "final" as const,
        eligibility: {
          status: "closed",
          eligible: false,
          requestable: false,
          reasonCode: "challenge_review_already_closed",
          blockers: ["challenge_review_already_closed"],
        },
        challenge: {
          state: "verdict_overturned",
          activeChallengeId: null,
          latestChallengeId: "challenge-1",
          latestDecision: "overturn",
          latestReasonCode: "manual_challenge",
          totalChallenges: 1,
        },
        review: {
          state: "approved",
          required: false,
          workflowStatus: "completed",
        },
        allowedActions: ["challenge.view", "review.view"],
        blockers: ["challenge_review_already_closed"],
        cacheProfile: {
          cacheable: true,
          ttlSeconds: 300,
          staleIfErrorSeconds: 0,
        },
        policy: {
          policyStatus: "enabled",
        },
        reviewDecisionSync: {
          version: "trust-challenge-review-decision-sync-v1",
          syncState: "awaiting_verdict_source",
          result: "verdict_overturned",
          userVisibleStatus: "review_required",
          nextStep: "await_revised_verdict_artifact",
        },
      },
    });
    expect(overturned.state).toBe("closed");
    expect(overturned.label).toBe("Verdict changed");
    expect(overturned.latestDecision).toBe("overturn");
    expect(overturned.reviewSyncState).toBe("awaiting_verdict_source");
  });

  it("calls NPC Coach advisory proxy with trimmed typed body", async () => {
    apiClient.post.mockResolvedValue({
      data: advisoryOutput("npc_coach"),
    });

    const result = await requestNpcCoachAdvice(9, {
      query: "  我该怎么回应？  ",
      traceId: " trace-1 ",
      side: "con",
      caseId: 42,
    });

    expect(apiClient.post).toHaveBeenCalledWith(
      "/debate/sessions/9/assistant/npc-coach/advice",
      {
        query: "我该怎么回应？",
        traceId: "trace-1",
        side: "con",
        caseId: 42,
      },
    );
    expect(result.status).toBe("not_ready");
    expect(result.advisoryOnly).toBe(true);
  });

  it("loads debate assistant status for membership and quota display", async () => {
    apiClient.get.mockResolvedValue({
      data: {
        sessionId: 9,
        agentKind: "debate_assistant",
        available: true,
        viewerRole: "participant",
        viewerSide: "pro",
        membership: {
          required: true,
          active: true,
          featureKey: "debate_assistant",
          status: "active",
          startsAt: null,
          expiresAt: null,
        },
        quota: {
          scope: "session",
          limit: 20,
          used: 3,
          remaining: 17,
          resetAt: null,
        },
        intents: [
          "room_summary",
          "opponent_summary",
          "unanswered_points",
          "speech_structure",
          "draft_polish",
        ],
        boundaryNotice: "私人辅助，不代表官方裁决；不会自动发送公开发言。",
      },
    });

    const result = await requestDebateAssistantStatus(9);

    expect(apiClient.get).toHaveBeenCalledWith(
      "/debate/sessions/9/assistant/debate-assistant/status",
    );
    expect(result.available).toBe(true);
    expect(result.quota.remaining).toBe(17);
    expect(result.membership.featureKey).toBe("debate_assistant");
  });

  it("calls debate assistant query with trimmed typed body", async () => {
    apiClient.post.mockResolvedValue({
      data: debateAssistantOutput(),
    });

    const result = await requestDebateAssistant(9, {
      intent: "draft_polish",
      question: "  帮我优化这段草稿  ",
      draft: "  我认为可以开放手机，但需要规则。  ",
      traceId: " trace-2 ",
      side: "con",
      caseId: 42,
    });

    expect(apiClient.post).toHaveBeenCalledWith(
      "/debate/sessions/9/assistant/debate-assistant/query",
      {
        intent: "draft_polish",
        question: "帮我优化这段草稿",
        draft: "我认为可以开放手机，但需要规则。",
        traceId: "trace-2",
        side: "con",
        caseId: 42,
      },
    );
    expect(result.agentKind).toBe("debate_assistant");
    expect(result.accepted).toBe(true);
  });

  it("maps debate assistant output into a private assistant view", () => {
    const view = resolveDebateAssistantView(debateAssistantOutput());

    expect(view.state).toBe("ready");
    expect(view.label).toBe("辩论助手已生成建议");
    expect(view.answerSummary).toBe(
      "当前争点集中在学习效率与学生自主权的权衡。",
    );
    expect(view.keyPoints).toEqual([
      "对方强调注意力风险。",
      "我方可以补充自主管理条件。",
    ]);
    expect(view.boundaryNotice).toContain("不代表官方裁决");
  });

  it("fails closed when debate assistant output includes official or private fields", async () => {
    apiClient.post.mockResolvedValue({
      data: debateAssistantOutput({
        advisoryContext: {
          roomTranscriptContext: debateAssistantTranscriptContext(),
          winner: "pro",
          walletBalance: 100,
        } satisfies JsonValue,
      }),
    });

    await expect(
      requestDebateAssistant(9, {
        intent: "room_summary",
        question: "总结当前争点",
      }),
    ).rejects.toThrow("forbidden official or private fields");
    expect(apiClient.post).toHaveBeenCalledWith(
      "/debate/sessions/9/assistant/debate-assistant/query",
      {
        intent: "room_summary",
        question: "总结当前争点",
      },
    );
  });

  it("allows user-safe proxy error output without transcript context", () => {
    const output = debateAssistantOutput({
      status: "proxy_error",
      statusReason: "debate_assistant_proxy_failed",
      accepted: false,
      errorCode: "debate_assistant_proxy_failed",
      errorMessage: "debate assistant request failed",
      sharedContext: {},
      advisoryContext: {},
      output: {
        accepted: false,
        intent: null,
        answerSummary: null,
        keyPoints: [],
        suggestedActions: [],
        contextCaveats: ["辩论助手暂不可用，请稍后重试。"],
        boundaryNotice: "私人辅助，不代表官方裁决；不会自动发送公开发言。",
        sourceUsePolicy: "未生成助手回答。",
      },
    });

    expect(assertDebateAssistantOutput(output).status).toBe("proxy_error");
    expect(resolveDebateAssistantView(output).state).toBe("proxy_error");
  });

  it("maps not_ready advisory response into a user-safe read model", () => {
    const view = resolveJudgeAssistantAdvisoryView(advisoryOutput("room_qa"));

    expect(view.state).toBe("not_ready");
    expect(view.label).toBe("辅助功能未启用");
    expect(view.message).toBe("辅助建议暂未启用，当前不会影响官方裁决。");
    expect(view.advisoryOnly).toBe(true);
    expect(view.accepted).toBe(false);
    expect(view.contextLabel).toBe("已有最终上下文");
    expect(view.receiptSummary).toBe("phase 0 / final 1");
  });

  it("maps deterministic placeholder output into ready advisory text and questions", () => {
    const output = advisoryOutput("npc_coach", {
      status: "ok",
      statusReason: "assistant_advisory_ready",
      accepted: true,
      errorCode: null,
      output: {
        safeGuidanceSummary: "当前为本地 deterministic 占位建议。",
        suggestedNextQuestions: [
          "请系统总结当前争点。",
          "我可以补充哪些公开证据？",
        ],
        availableContext: {
          stage: "final_context_available",
          officialVerdictFieldsRedacted: true,
        },
        limitations: ["不会预测胜负、评分或生成官方裁决理由。"],
      },
    });

    const view = resolveJudgeAssistantAdvisoryView(output);

    expect(view.state).toBe("ready");
    expect(view.label).toBe("辅助建议已生成");
    expect(view.accepted).toBe(true);
    expect(view.message).toBe("当前为本地 deterministic 占位建议。");
    expect(view.items).toEqual([
      "请系统总结当前争点。",
      "我可以补充哪些公开证据？",
    ]);
  });

  it("fails closed when assistant advisory output includes official fields", async () => {
    apiClient.post.mockResolvedValue({
      data: advisoryOutput("room_qa", {
        status: "ok",
        statusReason: "assistant_advisory_ready",
        accepted: true,
        errorCode: null,
        output: {
          answer: "当前争点是证据链是否足够。",
          verdictReason: "must-not-render",
        } satisfies JsonValue,
      }),
    });

    await expect(
      requestRoomQaAnswer(9, {
        question: "  当前争点是什么？  ",
      }),
    ).rejects.toThrow("forbidden official fields");
    expect(apiClient.post).toHaveBeenCalledWith(
      "/debate/sessions/9/assistant/room-qa/answer",
      {
        question: "当前争点是什么？",
      },
    );
  });

  it("fails closed when shared room context includes non-whitelisted fields", () => {
    expect(() =>
      assertJudgeAssistantAdvisoryOutput(
        advisoryOutput("npc_coach", {
          sharedContext: {
            sessionId: 9,
            scopeId: 1,
            caseId: 42,
            workflowStatus: "not_ready",
            latestDispatchType: "phase",
            topicDomain: "public-policy",
            phaseReceiptCount: 1,
            finalReceiptCount: 0,
            updatedAt: null,
            officialVerdictFieldsRedacted: true,
            ruleVersion: "must-not-be-shared",
          } satisfies JsonValue,
        }),
        "npc_coach",
      ),
    ).toThrow("room context snapshot");
  });
});
