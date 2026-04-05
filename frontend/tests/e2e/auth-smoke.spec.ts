import { expect, test, type Page, type Route } from "@playwright/test";

function json(route: Route, status: number, payload: unknown) {
  return route.fulfill({
    status,
    headers: {
      "content-type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

async function installAuthMocks(page: Page) {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    let body: Record<string, string> | undefined;
    try {
      body = request.postDataJSON() as Record<string, string> | undefined;
    } catch {
      body = undefined;
    }

    if (pathname === "/api/tickets" && request.method() === "POST") {
      return json(route, 200, {
        fileToken: "file_token_smoke",
        notifyToken: "notify_token_smoke",
        expiresInSecs: 3600
      });
    }

    if (pathname === "/api/auth/refresh" && request.method() === "POST") {
      return json(route, 200, {
        accessToken: "token_refresh_smoke",
        tokenType: "Bearer",
        expiresInSecs: 7200
      });
    }

    if (pathname === "/api/auth/v2/signin/password" && request.method() === "POST") {
      return json(route, 200, {
        accessToken: "token_password",
        tokenType: "Bearer",
        expiresInSecs: 7200,
        user: {
          id: 10,
          fullname: "Smoke Password",
          email: body?.account || "super@none.org",
          phoneE164: "+86139000000000",
          phoneBindRequired: false
        }
      });
    }

    if (pathname === "/api/auth/v2/sms/send" && request.method() === "POST") {
      const scene = body?.scene;
      const code = scene === "bind_phone" ? "445566" : "112233";
      return json(route, 200, {
        sent: true,
        ttlSecs: 60,
        cooldownSecs: 1,
        debugCode: code
      });
    }

    if (pathname === "/api/auth/v2/signin/otp" && request.method() === "POST") {
      return json(route, 200, {
        accessToken: "token_otp",
        tokenType: "Bearer",
        expiresInSecs: 7200,
        user: {
          id: 20,
          fullname: "Smoke Otp",
          phoneE164: body?.phone || "+86139000000000",
          phoneBindRequired: false
        }
      });
    }

    if (pathname === "/api/auth/v2/wechat/challenge" && request.method() === "POST") {
      return json(route, 200, {
        state: "wx_state_smoke",
        expiresInSecs: 180,
        appId: "wx_app_smoke"
      });
    }

    if (pathname === "/api/auth/v2/wechat/signin" && request.method() === "POST") {
      return json(route, 200, {
        bindRequired: true,
        wechatTicket: "wx_ticket_smoke"
      });
    }

    if (pathname === "/api/auth/v2/wechat/bind-phone" && request.method() === "POST") {
      if (body?.wechatTicket !== "wx_ticket_smoke") {
        return json(route, 400, { error: "invalid_wechat_ticket" });
      }
      return json(route, 200, {
        bindRequired: false,
        accessToken: "token_wechat_bound",
        tokenType: "Bearer",
        expiresInSecs: 7200,
        user: {
          id: 30,
          fullname: "Smoke WeChat",
          phoneE164: body?.phone || "+86139000000000",
          phoneBindRequired: false
        }
      });
    }

    return json(route, 404, { error: `unmocked endpoint: ${pathname}` });
  });
}

test.beforeEach(async ({ page }) => {
  await installAuthMocks(page);
});

test("@smoke password login lands on home", async ({ page }) => {
  await page.goto("/login");

  await expect(page.getByRole("heading", { name: "EchoIsle Frontend is now React + TypeScript strict." })).toBeVisible();
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByRole("heading", { name: "Mac/Web Migration Workbench" })).toBeVisible();
});

test("@smoke otp login lands on home", async ({ page }) => {
  await page.goto("/login");

  await page.getByRole("button", { name: "SMS OTP" }).click();
  await page.getByLabel("Phone").fill("+8613900011111");
  await page.getByRole("button", { name: "Send Code" }).click();
  await expect(page.getByText("Debug OTP: 112233")).toBeVisible();
  await page.getByLabel("SMS Code").fill("112233");
  await page.getByRole("button", { name: "Sign In with OTP" }).click();

  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByRole("heading", { name: "Mac/Web Migration Workbench" })).toBeVisible();
});

test("@smoke wechat bind flow reaches home", async ({ page }) => {
  await page.goto("/login");

  await page.getByRole("button", { name: "WeChat" }).click();
  await page.getByRole("button", { name: "Get Challenge" }).click();
  await expect(page.getByText("Challenge ready, appId=wx_app_smoke")).toBeVisible();
  await page.getByLabel("WeChat Auth Code").fill("wx-code-smoke");
  await page.getByRole("button", { name: "Sign In with WeChat" }).click();

  await expect(page).toHaveURL(/\/bind-phone$/);
  await expect(page.getByRole("heading", { name: "WeChat Phone Binding" })).toBeVisible();
  await page.getByRole("button", { name: "Send Code" }).click();
  await expect(page.getByText("Debug code: 445566")).toBeVisible();
  await page.getByLabel("SMS Code").fill("445566");
  await page.getByRole("button", { name: "Bind Phone" }).click();

  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByRole("heading", { name: "Mac/Web Migration Workbench" })).toBeVisible();
});
