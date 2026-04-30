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
});
