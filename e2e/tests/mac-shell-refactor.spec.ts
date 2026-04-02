import { expect, test } from '@playwright/test';

async function bootstrapAuthState(page) {
  await page.addInitScript(() => {
    localStorage.setItem('user', JSON.stringify({
      id: 2001,
      email: 'mac-shell-e2e@acme.org',
      phoneE164: '+8613800000001',
    }));
    localStorage.setItem('channels', JSON.stringify([]));
    localStorage.setItem('single_channels', JSON.stringify([]));
    localStorage.setItem('users', JSON.stringify({}));
  });
}

async function mockCommonApis(page, hooks = {}) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;

    if (pathname === '/api/auth/refresh') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ accessToken: 'mac-shell-token' }),
      });
      return;
    }

    if (pathname === '/api/tickets') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          fileToken: 'mac-shell-file',
          notifyToken: 'mac-shell-notify',
          expiresInSecs: 300,
        }),
      });
      return;
    }

    if (pathname === '/api/pay/wallet') {
      hooks.onWalletBalance?.();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ balance: 88 }),
      });
      return;
    }

    if (pathname === '/api/pay/wallet/ledger') {
      hooks.onWalletLedger?.();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
      return;
    }

    if (pathname === '/api/pay/iap/products') {
      hooks.onIapProducts?.();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            productId: 'coins_6',
            coins: 6,
            isActive: true,
          },
        ]),
      });
      return;
    }

    if (pathname === '/api/analytics/judge-refresh/summary') {
      hooks.onJudgeRefreshSummary?.();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ rows: [], windowHours: 24, limit: 20 }),
      });
      return;
    }

    if (pathname === '/api/analytics/judge-refresh/summary/metrics') {
      hooks.onJudgeRefreshSummaryMetrics?.();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          requestTotal: 0,
          cacheHitTotal: 0,
          cacheMissTotal: 0,
          cacheHitRate: 0,
          dbQueryTotal: 0,
          dbErrorTotal: 0,
          avgDbLatencyMs: 0,
          lastDbLatencyMs: 0,
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

test.beforeEach(async ({ page }) => {
  await bootstrapAuthState(page);
  await mockCommonApis(page);
});

test('judge report shell should render with refreshed desktop style', async ({ page }) => {
  await page.goto('http://127.0.0.1:1420/judge-report');
  await expect(page.getByRole('heading', { name: '裁判报告中心' })).toBeVisible();
  await expect(page.getByText('判决链路观测面板')).toBeVisible();
  await expect(page.getByRole('button', { name: '查询' })).toBeVisible();
});

test('judge report page should request summary and metrics endpoints', async ({ page }) => {
  let summaryCalls = 0;
  let metricsCalls = 0;
  await mockCommonApis(page, {
    onJudgeRefreshSummary: () => {
      summaryCalls += 1;
    },
    onJudgeRefreshSummaryMetrics: () => {
      metricsCalls += 1;
    },
  });

  await page.goto('http://127.0.0.1:1420/judge-report');
  await page.getByPlaceholder('例如：123').fill('123');
  await page.getByRole('button', { name: '查询' }).click();
  await expect(page.getByRole('heading', { name: '裁判报告中心' })).toBeVisible();
  await expect.poll(() => summaryCalls).toBeGreaterThan(0);
  await expect.poll(() => metricsCalls).toBeGreaterThan(0);
});

test('wallet shell should render with refreshed desktop style', async ({ page }) => {
  await page.goto('http://127.0.0.1:1420/wallet');
  await expect(page.getByRole('heading', { name: '充值与验单工作台' })).toBeVisible();
  await expect(page.getByText('钱包账本')).toBeVisible();
});

test('wallet page should request wallet and ledger endpoints', async ({ page }) => {
  let walletBalanceCalls = 0;
  let walletLedgerCalls = 0;
  let iapProductsCalls = 0;
  await mockCommonApis(page, {
    onWalletBalance: () => {
      walletBalanceCalls += 1;
    },
    onWalletLedger: () => {
      walletLedgerCalls += 1;
    },
    onIapProducts: () => {
      iapProductsCalls += 1;
    },
  });

  await page.goto('http://127.0.0.1:1420/wallet');
  await expect(page.getByRole('heading', { name: '充值与验单工作台' })).toBeVisible();
  await expect.poll(() => walletBalanceCalls).toBeGreaterThan(0);
  await expect.poll(() => walletLedgerCalls).toBeGreaterThan(0);
  await expect.poll(() => iapProductsCalls).toBeGreaterThan(0);
});

test('profile and notifications should render with refreshed desktop style', async ({ page }) => {
  await page.goto('http://127.0.0.1:1420/me');
  await expect(page.getByRole('heading', { name: '个人资料' })).toBeVisible();
  await expect(page.getByText('账号密码')).toBeVisible();

  await page.goto('http://127.0.0.1:1420/notifications');
  await expect(page.getByRole('heading', { name: '通知中心' })).toBeVisible();
  await expect(page.getByText('通知列表')).toBeVisible();
});
