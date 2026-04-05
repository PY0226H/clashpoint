import { describe, expect, it } from "vitest";
import { resolveLandingPath } from "../navigation";

describe("resolveLandingPath", () => {
  it("returns login for guest", () => {
    expect(resolveLandingPath({ token: null, user: null, wechatBindTicket: null })).toBe("/login");
  });

  it("returns bind-phone when wechat bind ticket exists", () => {
    expect(resolveLandingPath({ token: null, user: null, wechatBindTicket: "ticket_001" })).toBe("/bind-phone");
  });

  it("returns phone bind when phone is required", () => {
    expect(
      resolveLandingPath({
        token: "token",
        user: { id: 1, phoneBindRequired: true },
        wechatBindTicket: null
      })
    ).toBe("/bind-phone");
  });

  it("returns home for authenticated and phone-bound user", () => {
    expect(
      resolveLandingPath({
        token: "token",
        user: { id: 1, phoneBindRequired: false },
        wechatBindTicket: null
      })
    ).toBe("/home");
  });
});
