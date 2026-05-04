import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DebateNpcPanel } from "./DebateNpcPanel";
import {
  debateNpcReducer,
  createInitialDebateNpcState,
} from "./DebateNpcModel";

describe("DebateNpcPanel", () => {
  it("renders an always-visible room NPC shell", () => {
    const html = renderToStaticMarkup(
      <DebateNpcPanel state={createInitialDebateNpcState()} />,
    );

    expect(html).toContain("Virtual Judge NPC");
    expect(html).toContain("Room host");
    expect(html).toContain("Observing");
    expect(html).toContain("Watching the room.");
    expect(html).not.toContain("Winner");
    expect(html).not.toContain("Official Verdict");
  });

  it("renders praise action feed without private chat affordance", () => {
    const state = debateNpcReducer(createInitialDebateNpcState(), {
      type: "roomAction",
      payload: {
        event: "DebateNpcActionCreated",
        actionId: 301,
        actionUid: "npc-action-301",
        sessionId: 15,
        npcId: "virtual_judge_default",
        displayName: "Virtual Judge NPC",
        actionType: "praise",
        publicText: "That rebuttal landed cleanly.",
        targetMessageId: 100,
        targetUserId: 7,
        targetSide: "pro",
        effectKind: "sparkle",
        npcStatus: "praising",
        reasonCode: "strong_rebuttal",
        createdAt: "2026-05-03T09:00:00Z",
      },
    });

    const html = renderToStaticMarkup(<DebateNpcPanel state={state} />);

    expect(html).toContain("Praising");
    expect(html).toContain("Highlighted move");
    expect(html).toContain("That rebuttal landed cleanly.");
    expect(html).toContain("message #100 / PRO / user 7");
    expect(html).not.toContain("Private");
    expect(html).not.toContain("chat");
    expect(html).not.toContain("Score");
  });
});
