import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  DebateAssistantLockState,
  DebateAssistantResult,
} from "./DebateAssistantPanel";
import type {
  DebateAssistantStatusOutput,
  DebateAssistantView,
} from "@echoisle/debate-domain";

function assistantStatus(
  overrides?: Partial<DebateAssistantStatusOutput>,
): DebateAssistantStatusOutput {
  return {
    sessionId: 9,
    agentKind: "debate_assistant",
    available: false,
    viewerRole: "participant",
    viewerSide: "pro",
    membership: {
      required: true,
      active: false,
      featureKey: "debate_assistant",
      status: "absent",
      startsAt: null,
      expiresAt: null,
    },
    quota: {
      scope: "session",
      limit: 20,
      used: 0,
      remaining: 20,
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
    ...overrides,
  };
}

describe("DebateAssistantPanel presentational states", () => {
  it("renders non-member lock without official verdict semantics", () => {
    const html = renderToStaticMarkup(
      <DebateAssistantLockState status={assistantStatus()} />,
    );

    expect(html).toContain("会员专属");
    expect(html).toContain("开通会员");
    expect(html).toContain("私人辅助，不代表官方裁决");
    expect(html).toContain("本场剩余 20/20");
    expect(html).not.toContain("Winner");
    expect(html).not.toContain("Score");
    expect(html).not.toContain("Judge Trace");
  });

  it("renders ready assistant answer as private guidance lists", () => {
    const view: DebateAssistantView = {
      state: "ready",
      label: "辩论助手已生成建议",
      reasonCode: "debate_assistant_ready",
      accepted: true,
      advisoryOnly: true,
      caseId: 42,
      intent: "speech_structure",
      answerSummary: "下一段可以先承认风险，再提出可执行边界。",
      keyPoints: ["对方强调注意力风险。", "我方需要补充管理规则。"],
      suggestedActions: ["用一句话归纳对方担忧。", "提出时间和场景限制。"],
      contextCaveats: ["仅基于当前公开房间消息。"],
      boundaryNotice: "私人辅助，不代表官方裁决；不会自动发送公开发言。",
      sourceUsePolicy: "仅基于当前房间公开内容和用户输入。",
    };

    const html = renderToStaticMarkup(<DebateAssistantResult view={view} />);

    expect(html).toContain("辩论助手已生成建议");
    expect(html).toContain("下一段可以先承认风险");
    expect(html).toContain("行动建议");
    expect(html).toContain("仅基于当前公开房间消息");
    expect(html).not.toContain("Winner");
    expect(html).not.toContain("Score");
  });

  it("renders quota exhausted as a safe private assistant state", () => {
    const view: DebateAssistantView = {
      state: "quota_exhausted",
      label: "本场助手额度已用完",
      reasonCode: "debate_assistant_quota_exhausted",
      accepted: false,
      advisoryOnly: true,
      caseId: null,
      intent: null,
      answerSummary: "本场可用次数已经用完。",
      keyPoints: [],
      suggestedActions: [],
      contextCaveats: [],
      boundaryNotice: "私人辅助，不代表官方裁决；不会自动发送公开发言。",
      sourceUsePolicy: null,
    };

    const html = renderToStaticMarkup(<DebateAssistantResult view={view} />);

    expect(html).toContain("本场助手额度已用完");
    expect(html).toContain("本场可用次数已经用完");
    expect(html).toContain("私人辅助，不代表官方裁决");
  });
});
