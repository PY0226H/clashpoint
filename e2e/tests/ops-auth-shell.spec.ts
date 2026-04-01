import { expect, test } from '@playwright/test';

async function bootstrapAuthState(page, options = { phoneBound: true }) {
  await page.addInitScript(({ phoneBound }) => {
    localStorage.setItem('user', JSON.stringify({
      id: 3001,
      email: 'ops-auth-e2e@acme.org',
      phoneE164: phoneBound ? '+8613800000011' : '',
    }));
    localStorage.setItem('channels', JSON.stringify([]));
    localStorage.setItem('single_channels', JSON.stringify([]));
    localStorage.setItem('users', JSON.stringify({}));
  }, options);
}

async function mockOpsAndAuthApis(page) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;

    if (pathname === '/api/auth/refresh') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ accessToken: 'ops-auth-shell-token' }),
      });
      return;
    }

    if (pathname === '/api/tickets') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          fileToken: 'ops-auth-file',
          notifyToken: 'ops-auth-notify',
          expiresInSecs: 300,
        }),
      });
      return;
    }

    if (pathname === '/api/debate/ops/rbac/me') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          isOwner: false,
          role: 'ops',
          permissions: {
            debateManage: true,
            judgeReview: true,
            judgeRejudge: true,
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

test('register page should render refreshed auth shell', async ({ page }) => {
  await page.goto('http://127.0.0.1:1420/register');
  await expect(page.getByRole('heading', { name: '注册账号' })).toBeVisible();
  await expect(page.getByRole('button', { name: '手机号注册' })).toBeVisible();
  await expect(page.getByRole('button', { name: '发码' })).toBeVisible();
});

test('phone bind page should render refreshed auth shell', async ({ page }) => {
  await bootstrapAuthState(page, { phoneBound: false });
  await mockOpsAndAuthApis(page);

  await page.goto('http://127.0.0.1:1420/bind-phone');
  await expect(page.getByRole('heading', { name: '绑定手机号' })).toBeVisible();
  await expect(page.getByRole('button', { name: '发送验证码' })).toBeVisible();
  await expect(page.getByRole('button', { name: '绑定并继续' })).toBeVisible();
});

test('ops page should render refreshed desktop shell', async ({ page }) => {
  await bootstrapAuthState(page);
  await mockOpsAndAuthApis(page);

  await page.goto('http://127.0.0.1:1420/debate/ops');
  await expect(page.getByRole('heading', { name: '运营控制台' })).toBeVisible();
  await expect(page.getByText('当前身份：')).toBeVisible();
  await expect(page.getByRole('button', { name: '刷新 Trace/Replay' })).toBeVisible();
});
