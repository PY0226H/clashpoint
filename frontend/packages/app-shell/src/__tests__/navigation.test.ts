import { describe, expect, it } from "vitest";
import { resolveLandingPath } from "../navigation";

describe("resolveLandingPath", () => {
  it("returns login for guest", () => {
    expect(resolveLandingPath({ token: null, user: null })).toBe("/login");
  });

  it("returns phone bind when phone is required", () => {
    expect(
      resolveLandingPath({
        token: "token",
        user: { id: 1, phoneBindRequired: true }
      })
    ).toBe("/bind-phone");
  });

  it("returns home for authenticated and phone-bound user", () => {
    expect(
      resolveLandingPath({
        token: "token",
        user: { id: 1, phoneBindRequired: false }
      })
    ).toBe("/home");
  });
});
