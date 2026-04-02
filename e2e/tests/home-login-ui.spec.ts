import { expect, test } from '@playwright/test';

async function bootstrapAuthState(page) {
  await page.addInitScript(() => {
    localStorage.setItem('user', JSON.stringify({
      id: 1001,
      email: 'ui-e2e@acme.org',
      phoneE164: '+8613800000000',
    }));
    localStorage.setItem('channels', JSON.stringify([
      { id: 21, name: 'general' },
    ]));
    localStorage.setItem('single_channels', JSON.stringify([
      {
        id: 31,
        recipient: {
          fullname: 'E2E Friend',
        },
      },
    ]));
    localStorage.setItem('users', JSON.stringify({}));
  });
}

async function mockCommonApis(page, hooks = {}) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;

    if (pathname === '/api/auth/refresh') {
      hooks.onAuthRefresh?.();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ accessToken: 'ui-e2e-token' }),
      });
      return;
    }

    if (pathname === '/api/tickets') {
      hooks.onTickets?.();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          fileToken: 'ui-file-token',
          notifyToken: 'ui-notify-token',
          expiresInSecs: 300,
        }),
      });
      return;
    }

    if (pathname === '/api/debate/topics') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 11, title: '云顶之弈平衡辩题', category: 'game' }]),
      });
      return;
    }

    if (pathname === '/api/debate/sessions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 201,
            topicId: 11,
            status: 'open',
            joinable: true,
            proCount: 1,
            conCount: 1,
            hotScore: 8,
            scheduledStartAt: '2026-03-03T01:00:00Z',
          },
        ]),
      });
      return;
    }

    if (pathname === '/api/iap/wallet/balance') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ balance: 66 }),
      });
      return;
    }

    if (pathname === '/api/debate/ops/rbac/me') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          isOwner: false,
          role: 'user',
          permissions: {
            debateManage: false,
            judgeReview: false,
            judgeRejudge: false,
            roleManage: false,
          },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({}),
    });
  });

  await page.route('**/events**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: '',
    });
  });
}

test('login page should render refreshed visual structure', async ({ page }) => {
  await page.goto('http://127.0.0.1:1420/login');

  await expect(page.getByText('在线辩论 AI 裁判平台')).toBeVisible();
  await expect(page.getByRole('heading', { name: '登录' })).toBeVisible();
  await expect(page.getByRole('button', { name: '邮箱+密码' })).toBeVisible();
  await expect(page.getByRole('button', { name: '手机+密码' })).toBeVisible();
  await expect(page.getByRole('button', { name: '手机+验证码' })).toBeVisible();
});

test('home page should render four-entry dashboard with new shell', async ({ page }) => {
  await bootstrapAuthState(page);
  await mockCommonApis(page);

  await page.goto('http://127.0.0.1:1420/home');

  await expect(page.getByRole('heading', { name: 'EchoIsle 首页工作台' })).toBeVisible();
  await expect(page.getByText('入口 1')).toBeVisible();
  await expect(page.getByText('入口 2')).toBeVisible();
  await expect(page.getByText('入口 3')).toBeVisible();
  await expect(page.getByText('入口 4')).toBeVisible();

  await page.getByRole('button', { name: '辩论广场' }).click();
  await expect(page).toHaveURL(/\/debate/);
  await expect(page.getByRole('heading', { name: '辩论场次总览' })).toBeVisible();
});

test('home bootstrap should request refresh session and tickets', async ({ page }) => {
  await bootstrapAuthState(page);
  let refreshCalls = 0;
  let ticketsCalls = 0;
  await mockCommonApis(page, {
    onAuthRefresh: () => {
      refreshCalls += 1;
    },
    onTickets: () => {
      ticketsCalls += 1;
    },
  });

  await page.goto('http://127.0.0.1:1420/home');
  await expect(page.getByRole('heading', { name: 'EchoIsle 首页工作台' })).toBeVisible();
  await expect.poll(() => refreshCalls).toBeGreaterThan(0);
  await expect.poll(() => ticketsCalls).toBeGreaterThan(0);
});
