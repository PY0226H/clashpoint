import { describe, expect, it } from "vitest";
import { isPhoneBindRequired, normalizeAuthUserForPhoneGate, resolveWechatSigninOutcome } from "./index";

describe("auth phone gate helpers", () => {
  it("keeps explicit phoneBindRequired flag", () => {
    const normalized = normalizeAuthUserForPhoneGate({
      id: 1,
      email: "user@example.com",
      phoneBindRequired: true
    });
    expect(normalized.phoneBindRequired).toBe(true);
    expect(isPhoneBindRequired(normalized)).toBe(true);
  });

  it("infers phone binding required when phone is missing", () => {
    const normalized = normalizeAuthUserForPhoneGate({
      id: 2,
      email: "user2@example.com"
    });
    expect(normalized.phoneBindRequired).toBe(true);
    expect(isPhoneBindRequired(normalized)).toBe(true);
  });

  it("infers phone binding completed when phone exists", () => {
    const normalized = normalizeAuthUserForPhoneGate({
      id: 3,
      email: "user3@example.com",
      phoneE164: "+8613900000000"
    });
    expect(normalized.phoneBindRequired).toBe(false);
    expect(isPhoneBindRequired(normalized)).toBe(false);
  });
});

describe("wechat signin outcome resolver", () => {
  it("returns bind-required outcome with ticket", () => {
    const outcome = resolveWechatSigninOutcome({
      bindRequired: true,
      wechatTicket: "ticket_123"
    });
    expect(outcome.bindRequired).toBe(true);
    if (outcome.bindRequired) {
      expect(outcome.wechatTicket).toBe("ticket_123");
    }
  });

  it("returns signed-in outcome when token and user are present", () => {
    const outcome = resolveWechatSigninOutcome({
      bindRequired: false,
      accessToken: "token_123",
      user: { id: 9, phoneBindRequired: false }
    });
    expect(outcome.bindRequired).toBe(false);
    if (!outcome.bindRequired) {
      expect(outcome.auth.accessToken).toBe("token_123");
      expect(outcome.auth.user.id).toBe(9);
    }
  });

  it("throws when signin response misses token or user", () => {
    expect(() =>
      resolveWechatSigninOutcome({
        bindRequired: false,
        accessToken: "token_only"
      })
    ).toThrow("auth_wechat_response_invalid");
  });
});
