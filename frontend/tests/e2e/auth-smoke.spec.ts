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

    if (pathname === "/api/debate/topics" && request.method() === "GET") {
      return json(route, 200, {
        items: [
          {
            id: 101,
            title: "AI should regulate itself",
            description: "Debate AI governance boundaries.",
            category: "governance",
            stancePro: "strict self-regulation",
            stanceCon: "external regulation first",
            contextSeed: null,
            isActive: true,
            createdBy: 1,
            createdAt: "2026-01-01T00:00:00Z",
            updatedAt: "2026-01-01T00:00:00Z"
          }
        ],
        hasMore: false,
        nextCursor: null,
        revision: "topic_rev_1"
      });
    }

    if (pathname === "/api/debate/sessions" && request.method() === "GET") {
      return json(route, 200, {
        items: [
          {
            id: 901,
            topicId: 101,
            status: "open",
            scheduledStartAt: "2026-01-01T01:00:00Z",
            actualStartAt: null,
            endAt: "2026-01-01T02:00:00Z",
            maxParticipantsPerSide: 2,
            proCount: 1,
            conCount: 1,
            hotScore: 8,
            createdAt: "2026-01-01T00:00:00Z",
            updatedAt: "2026-01-01T00:00:00Z",
            joinable: true
          }
        ],
        hasMore: false,
        nextCursor: null,
        revision: "session_rev_1"
      });
    }

    if (pathname.match(/^\/api\/debate\/sessions\/\d+\/join$/) && request.method() === "POST") {
      return json(route, 200, {
        sessionId: 901,
        side: body?.side === "con" ? "con" : "pro",
        newlyJoined: true,
        proCount: body?.side === "con" ? 1 : 2,
        conCount: body?.side === "con" ? 2 : 1
      });
    }

    if (pathname.match(/^\/api\/debate\/sessions\/\d+\/messages$/) && request.method() === "GET") {
      return json(route, 200, {
        items: [
          {
            id: 2001,
            sessionId: 901,
            userId: 10,
            side: "pro",
            content: "Opening statement from PRO.",
            createdAt: "2026-01-01T01:03:00Z"
          }
        ],
        hasMore: false,
        nextCursor: null,
        revision: "2001"
      });
    }

    if (pathname.match(/^\/api\/debate\/sessions\/\d+\/pins$/) && request.method() === "GET") {
      return json(route, 200, {
        items: [
          {
            id: 3001,
            sessionId: 901,
            messageId: 2001,
            userId: 10,
            side: "pro",
            content: "Pinned argument",
            costCoins: 20,
            pinSeconds: 60,
            pinnedAt: "2026-01-01T01:04:00Z",
            expiresAt: "2026-01-01T01:05:00Z",
            status: "active"
          }
        ],
        hasMore: false,
        nextCursor: null,
        revision: "3001"
      });
    }

    if (pathname.match(/^\/api\/debate\/sessions\/\d+\/messages$/) && request.method() === "POST") {
      return json(route, 201, {
        id: 2002,
        sessionId: 901,
        userId: 10,
        side: "pro",
        content: body?.content || "new message",
        createdAt: "2026-01-01T01:06:00Z"
      });
    }

    if (pathname === "/api/pay/wallet" && request.method() === "GET") {
      return json(route, 200, {
        userId: 10,
        balance: 180,
        walletRevision: "wallet_rev_1",
        walletInitialized: true
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

test("@smoke lobby should render sessions and support join", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Lobby" }).click();

  await expect(page).toHaveURL(/\/debate$/);
  await expect(page.getByRole("heading", { name: "Debate Lobby" })).toBeVisible();
  await expect(page.getByText("AI should regulate itself")).toBeVisible();
  await page.getByRole("button", { name: "Join Pro" }).click();
  await expect(page).toHaveURL(/\/debate\/sessions\/901$/);
  await expect(page.getByRole("heading", { name: "Debate Room #901" })).toBeVisible();
  await expect(page.getByText("Opening statement from PRO.")).toBeVisible();
  await page.getByPlaceholder("Share your argument...").fill("My realtime argument");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("My realtime argument")).toBeVisible();
});

test("@auth-error password invalid credentials should stay on login", async ({ page }) => {
  await page.route("**/api/auth/v2/signin/password", async (route) => {
    await json(route, 401, { error: "invalid_credentials" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("invalid_credentials")).toBeVisible();
});

test("@auth-error otp send cooldown should show rate limit error", async ({ page }) => {
  await page.route("**/api/auth/v2/sms/send", async (route) => {
    await json(route, 429, { error: "sms_send_cooldown" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "SMS OTP" }).click();
  await page.getByLabel("Phone").fill("+8613900011111");
  await page.getByRole("button", { name: "Send Code" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("sms_send_cooldown")).toBeVisible();
});

test("@auth-error wechat bind should show invalid ticket error", async ({ page }) => {
  await page.route("**/api/auth/v2/wechat/bind-phone", async (route) => {
    await json(route, 400, { error: "invalid_wechat_ticket" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "WeChat" }).click();
  await page.getByRole("button", { name: "Get Challenge" }).click();
  await page.getByLabel("WeChat Auth Code").fill("wx-code-smoke");
  await page.getByRole("button", { name: "Sign In with WeChat" }).click();

  await expect(page).toHaveURL(/\/bind-phone$/);
  await page.getByRole("button", { name: "Send Code" }).click();
  await page.getByLabel("SMS Code").fill("445566");
  await page.getByRole("button", { name: "Bind Phone" }).click();

  await expect(page).toHaveURL(/\/bind-phone$/);
  await expect(page.getByText("invalid_wechat_ticket")).toBeVisible();
});
