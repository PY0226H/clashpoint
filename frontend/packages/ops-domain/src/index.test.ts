import { describe, expect, it } from "vitest";
import { getOpsDomainErrorInfo } from "./index";

describe("getOpsDomainErrorInfo", () => {
  it("should normalize role-manage permission denied code", () => {
    const info = getOpsDomainErrorInfo({
      response: {
        status: 409,
        data: {
          error: "debate conflict: ops_permission_denied:role_manage"
        }
      }
    });
    expect(info.status).toBe(409);
    expect(info.code).toBe("ops_permission_denied:role_manage");
    expect(info.message).toBe("ops_permission_denied:role_manage");
  });

  it("should normalize ops role target not found code", () => {
    const info = getOpsDomainErrorInfo({
      response: {
        status: 404,
        data: {
          error: "Not found: ops_role_target_user_not_found"
        }
      }
    });
    expect(info.status).toBe(404);
    expect(info.code).toBe("ops_role_target_user_not_found");
    expect(info.message).toBe("ops_role_target_user_not_found");
  });

  it("should normalize rate-limit scope code", () => {
    const info = getOpsDomainErrorInfo({
      response: {
        status: 429,
        data: {
          error: "rate_limit_exceeded:ops_rbac_roles_list"
        }
      }
    });
    expect(info.status).toBe(429);
    expect(info.code).toBe("rate_limit_exceeded:ops_rbac_roles_list");
    expect(info.message).toBe("rate_limit_exceeded:ops_rbac_roles_list");
  });

  it("should fallback to request failed for unknown empty payload", () => {
    const info = getOpsDomainErrorInfo({});
    expect(info.status).toBeNull();
    expect(info.code).toBeNull();
    expect(info.message).toBe("request failed");
  });
});
