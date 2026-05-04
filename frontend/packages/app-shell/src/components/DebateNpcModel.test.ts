import { describe, expect, it } from "vitest";
import type { DebateNpcActionCreatedPayload } from "@echoisle/debate-domain";
import {
  debateNpcReducer,
  createInitialDebateNpcState,
  resolveDebateNpcTargetLabel,
} from "./DebateNpcModel";

function npcAction(
  overrides?: Partial<DebateNpcActionCreatedPayload>,
): DebateNpcActionCreatedPayload {
  return {
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
    ...overrides,
  };
}

describe("DebateNpcModel", () => {
  it("builds visible NPC state from a praise room action", () => {
    const state = debateNpcReducer(createInitialDebateNpcState(), {
      type: "roomAction",
      payload: npcAction(),
    });

    expect(state).toMatchObject({
      displayName: "Virtual Judge NPC",
      status: "praising",
      latestEffectKind: "sparkle",
      effectNonce: 1,
    });
    expect(state.latestAction).toMatchObject({
      actionUid: "npc-action-301",
      actionType: "praise",
      text: "That rebuttal landed cleanly.",
      targetLabel: "message #100 / PRO / user 7",
    });
    expect(state.feed).toHaveLength(1);
  });

  it("ignores duplicate room actions during replay", () => {
    const first = debateNpcReducer(createInitialDebateNpcState(), {
      type: "roomAction",
      payload: npcAction(),
    });
    const replayed = debateNpcReducer(first, {
      type: "roomAction",
      payload: npcAction({ publicText: "duplicate should not replace" }),
    });

    expect(replayed).toEqual(first);
  });

  it("falls back to room target when no target is present", () => {
    expect(
      resolveDebateNpcTargetLabel(
        npcAction({
          actionType: "effect",
          publicText: null,
          targetMessageId: null,
          targetSide: null,
          targetUserId: null,
        }),
      ),
    ).toBe("room");
  });
});
