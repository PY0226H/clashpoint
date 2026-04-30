import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AssistantAdvisoryResult } from "./DebateAssistantPanel";
import type { JudgeAssistantAdvisoryView } from "@echoisle/debate-domain";

describe("AssistantAdvisoryResult", () => {
  it("renders not_ready as advisory-only UI and not as official verdict", () => {
    const view: JudgeAssistantAdvisoryView = {
      state: "not_ready",
      agentKind: "npc_coach",
      label: "辅助功能未启用",
      reasonCode: "agent_not_enabled",
      advisoryOnly: true,
      accepted: false,
      caseId: 42,
      message: "辅助建议暂未启用，当前不会影响官方裁决。",
      items: [],
      contextStage: "final_context_available",
      contextLabel: "已有最终上下文",
      workflowStatus: "not_ready",
      latestDispatchType: "final",
      receiptSummary: "phase 0 / final 1",
      updatedAt: null,
    };

    const html = renderToStaticMarkup(
      <AssistantAdvisoryResult title="NPC Coach" view={view} />,
    );

    expect(html).toContain("辅助功能未启用");
    expect(html).toContain("辅助建议，不是官方裁决");
    expect(html).toContain("已有最终上下文");
    expect(html).toContain("当前不会影响官方裁决");
    expect(html).not.toContain("Winner");
    expect(html).not.toContain("Score");
  });

  it("renders deterministic placeholder guidance as advisory-only list", () => {
    const view: JudgeAssistantAdvisoryView = {
      state: "ready",
      agentKind: "room_qa",
      label: "辅助建议已生成",
      reasonCode: "assistant_advisory_ready",
      advisoryOnly: true,
      accepted: true,
      caseId: 42,
      message: "当前上下文阶段：已有阶段上下文。",
      items: ["当前上下文阶段是什么？", "我还可以补充哪些公开材料？"],
      contextStage: "phase_context_available",
      contextLabel: "已有阶段上下文",
      workflowStatus: "done",
      latestDispatchType: "phase",
      receiptSummary: "phase 1 / final 0",
      updatedAt: null,
    };

    const html = renderToStaticMarkup(
      <AssistantAdvisoryResult title="Room QA" view={view} />,
    );

    expect(html).toContain("辅助建议已生成");
    expect(html).toContain("辅助建议，不是官方裁决");
    expect(html).toContain("当前上下文阶段是什么？");
    expect(html).toContain("phase 1 / final 0");
    expect(html).not.toContain("Winner");
    expect(html).not.toContain("Score");
  });
});
