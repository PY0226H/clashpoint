import { describe, expect, it } from "vitest";
import {
  DEBATE_NPC_ACTION_CREATED_EVENT,
  buildDebateRoomAckMessage,
  buildDebateRoomWsUrl,
  buildNotifyTicketProtocol,
  computeWsReconnectDelayMs,
  parseDebateRoomServerMessage
} from "./index";

describe("realtime-sdk debate room helpers", () => {
  it("builds debate room websocket url from notify base", () => {
    expect(buildDebateRoomWsUrl({ notifyBase: "http://localhost:6687/events", sessionId: 101, lastAckSeq: 6 })).toBe(
      "ws://localhost:6687/ws/debate/101?lastAckSeq=6"
    );
  });

  it("builds notify ticket websocket subprotocol", () => {
    expect(buildNotifyTicketProtocol("token_abc")).toBe("notify-ticket.token_abc");
  });

  it("parses roomEvent payload", () => {
    const parsed = parseDebateRoomServerMessage(
      JSON.stringify({
        type: "roomEvent",
        eventSeq: 9,
        eventName: "DebateMessageCreated",
        eventAtMs: 123,
        payload: {
          event: "DebateMessageCreated",
          messageId: 2001
        }
      })
    );
    expect(parsed?.type).toBe("roomEvent");
    if (!parsed || parsed.type !== "roomEvent") {
      throw new Error("roomEvent parse failed");
    }
    expect(parsed.eventSeq).toBe(9);
    expect(parsed.eventName).toBe("DebateMessageCreated");
  });

  it("parses virtual judge NPC roomEvent payload without special WS handling", () => {
    const parsed = parseDebateRoomServerMessage(
      JSON.stringify({
        type: "roomEvent",
        eventSeq: 10,
        eventName: DEBATE_NPC_ACTION_CREATED_EVENT,
        eventAtMs: 123,
        payload: {
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
        },
      }),
    );
    expect(parsed?.type).toBe("roomEvent");
    if (!parsed || parsed.type !== "roomEvent") {
      throw new Error("roomEvent parse failed");
    }
    expect(parsed.eventSeq).toBe(10);
    expect(parsed.eventName).toBe(DEBATE_NPC_ACTION_CREATED_EVENT);
    expect(parsed.payload.event).toBe(DEBATE_NPC_ACTION_CREATED_EVENT);
    expect(parsed.payload.actionUid).toBe("npc-action-301");
  });

  it("builds ack message", () => {
    expect(buildDebateRoomAckMessage(17)).toBe("{\"type\":\"ack\",\"eventSeq\":17}");
    expect(buildDebateRoomAckMessage(-1)).toBeNull();
  });

  it("computes reconnect delay with jitter", () => {
    const delay = computeWsReconnectDelayMs(3, {
      baseMs: 1000,
      maxMs: 10000,
      jitterRatio: 0.2,
      randomValue: 0.5
    });
    expect(delay).toBeGreaterThanOrEqual(1000);
    expect(delay).toBeLessThanOrEqual(10000);
  });
});
