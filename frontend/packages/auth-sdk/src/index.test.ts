import { describe, expect, it } from "vitest";
import { isPhoneBindRequired, normalizeAuthUserForPhoneGate } from "./index";

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
