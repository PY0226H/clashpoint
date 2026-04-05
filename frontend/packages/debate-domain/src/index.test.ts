import { describe, expect, it } from "vitest";
import { getOldestDebateMessageId, mergeDebateMessages, normalizeDebateSide, normalizeDebateStatusFilter } from "./index";

describe("debate-domain normalize helpers", () => {
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

  it("merges messages by id and keeps ascending order", () => {
    const merged = mergeDebateMessages(
      [
        {
          id: 2,
          sessionId: 9,
          userId: 1,
          side: "pro",
          content: "old",
          createdAt: "2026-01-01T00:00:00Z"
        }
      ],
      [
        {
          id: 1,
          sessionId: 9,
          userId: 2,
          side: "con",
          content: "first",
          createdAt: "2026-01-01T00:00:00Z"
        },
        {
          id: 2,
          sessionId: 9,
          userId: 1,
          side: "pro",
          content: "new",
          createdAt: "2026-01-01T00:00:02Z"
        }
      ]
    );

    expect(merged.map((item) => item.id)).toEqual([1, 2]);
    expect(merged[1]?.content).toBe("new");
  });

  it("returns oldest message id", () => {
    expect(
      getOldestDebateMessageId([
        { id: 8, sessionId: 1, userId: 1, side: "pro", content: "A", createdAt: "" },
        { id: 3, sessionId: 1, userId: 2, side: "con", content: "B", createdAt: "" },
        { id: 6, sessionId: 1, userId: 2, side: "con", content: "C", createdAt: "" }
      ])
    ).toBe(3);
  });
});
