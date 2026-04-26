import { describe, expect, it } from "vitest";
import {
  getOldestDebateMessageId,
  mergeDebateMessages,
  normalizeDebateSide,
  normalizeDebateStatusFilter,
  resolveDebateJudgePublicVerificationView,
} from "./index";

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
});
