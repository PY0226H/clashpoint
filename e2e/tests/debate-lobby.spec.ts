import { expect, test } from '@playwright/test';

const TOPICS = [
  { id: 11, title: '云顶之弈平衡辩题', category: 'game' },
  { id: 22, title: '其他话题', category: 'general' },
];

const SESSIONS = [
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
  {
    id: 202,
    topicId: 11,
    status: 'running',
    joinable: false,
    proCount: 2,
    conCount: 2,
    hotScore: 12,
    scheduledStartAt: '2026-03-03T02:00:00Z',
  },
  {
    id: 203,
    topicId: 22,
    status: 'closed',
    joinable: false,
    proCount: 3,
    conCount: 2,
    hotScore: 6,
    scheduledStartAt: '2026-03-01T02:00:00Z',
  },
];

async function bootstrapAuthState(page) {
  await page.addInitScript(() => {
    localStorage.setItem('user', JSON.stringify({
      id: 1001,
      email: 'e2e@acme.org',
      phoneE164: '+8613800000001',
    }));
    localStorage.setItem('channels', JSON.stringify([]));
    localStorage.setItem('single_channels', JSON.stringify([]));
    localStorage.setItem('users', JSON.stringify({}));
  });
}

async function mockDebateApis(page, hooks = {}) {
  await page.route('**/api/auth/refresh', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        accessToken: 'e2e-access-token',
      }),
    });
  });
  await page.route('**/api/tickets', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        fileToken: 'e2e-file-ticket',
        notifyToken: 'e2e-notify-ticket',
        expiresInSecs: 300,
      }),
    });
  });
  await page.route('**/api/debate/topics**', async (route) => {
    hooks.onDebateTopics?.();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(TOPICS),
    });
  });
  await page.route('**/api/debate/sessions**', async (route) => {
    hooks.onDebateSessions?.();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(SESSIONS),
    });
  });
  await page.route('**/api/debate/sessions/*/join', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        sessionId: 201,
        side: 'pro',
        proCount: 2,
        conCount: 1,
      }),
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

test.describe('Debate Lobby Phase3', () => {
  test.beforeEach(async ({ page }) => {
    await bootstrapAuthState(page);
    await mockDebateApis(page);
  });

  test('should restore filters from query and keep route query in sync', async ({ page }) => {
    await page.goto('http://127.0.0.1:1420/debate?lane=live&q=%E4%BA%91%E9%A1%B6&joinable=1&status=all');

    await expect(page.locator('select').nth(2)).toHaveValue('live');
    await expect(page.locator('input[placeholder="按辩题关键词筛选"]')).toHaveValue('云顶');
    await expect(page.locator('input[type="checkbox"]')).toBeChecked();

    await page.locator('select').nth(2).selectOption('upcoming');
    await expect(page).toHaveURL(/lane=upcoming/);

    await page.locator('input[type="checkbox"]').uncheck();
    await expect(page).not.toHaveURL(/joinable=1/);

    await page.locator('select').nth(1).selectOption('joinable');
    await expect(page).toHaveURL(/status=joinable/);
  });

  test('should expose quick actions for keyword hits and navigate by lane action', async ({ page }) => {
    await page.goto('http://127.0.0.1:1420/debate?q=%E4%BA%91%E9%A1%B6');

    await expect(page.getByText('搜索命中快速操作')).toBeVisible();
    await expect(page.getByText('Session 201 · 云顶之弈平衡辩题')).toBeVisible();
    await expect(page.getByText('Session 202 · 云顶之弈平衡辩题')).toBeVisible();

    await page.getByRole('button', { name: '一键观战' }).first().click();
    await expect(page).toHaveURL(/\/debate\/sessions\/202/);

    await page.goto('http://127.0.0.1:1420/debate?q=%E4%BA%91%E9%A1%B6&lane=upcoming');
    await page.getByRole('button', { name: '加入正方' }).first().click();
    await expect(page).toHaveURL(/\/debate\/sessions\/201/);
  });

  test('should request topics and sessions on debate lobby bootstrap', async ({ page }) => {
    let topicsCalls = 0;
    let sessionsCalls = 0;
    await mockDebateApis(page, {
      onDebateTopics: () => {
        topicsCalls += 1;
      },
      onDebateSessions: () => {
        sessionsCalls += 1;
      },
    });

    await page.goto('http://127.0.0.1:1420/debate');
    await expect(page.getByRole('heading', { name: '辩论场次总览' })).toBeVisible();
    await expect(page.getByText('当前可见场次')).toBeVisible();
    await expect.poll(() => topicsCalls).toBeGreaterThan(0);
    await expect.poll(() => sessionsCalls).toBeGreaterThan(0);
  });
});
