import { expect, test } from '@playwright/test';

async function bootstrapAuthState(page) {
  await page.addInitScript(() => {
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 1001, email: 'e2e@acme.org', phoneE164: '+8613800138000' }),
    );
    localStorage.setItem('channels', JSON.stringify([]));
    localStorage.setItem('users', JSON.stringify({}));
  });
}

async function mockCommonApis(page) {
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
  await page.route('**/api/pay/wallet', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        balance: 88,
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

test.describe('Me password set flow', () => {
  test.beforeEach(async ({ page }) => {
    await bootstrapAuthState(page);
    await mockCommonApis(page);
  });

  test('should call set password api with trimmed password and show success text', async ({ page }) => {
    let payload = null;
    await page.route('**/api/auth/v2/password/set', async (route) => {
      payload = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ updated: true }),
      });
    });

    await page.goto('http://127.0.0.1:1420/me');

    await page.locator('input[type="password"]').first().fill('  654321  ');
    await page.locator('input[type="password"]').nth(1).fill('654321');
    await page.getByPlaceholder('6位验证码').fill(' 112233 ');
    await page.getByRole('button', { name: '设置密码' }).click();

    await expect(page.getByText('密码已更新')).toBeVisible();
    expect(payload).toEqual({ password: '654321', smsCode: '112233' });
    await expect(page.locator('input[type="password"]').first()).toHaveValue('');
    await expect(page.locator('input[type="password"]').nth(1)).toHaveValue('');
    await expect(page.getByPlaceholder('6位验证码')).toHaveValue('');
  });

  test('should block submit when confirm password mismatches', async ({ page }) => {
    let submitCount = 0;
    await page.route('**/api/auth/v2/password/set', async (route) => {
      submitCount += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ updated: true }),
      });
    });

    await page.goto('http://127.0.0.1:1420/me');

    await page.locator('input[type="password"]').first().fill('123456');
    await page.locator('input[type="password"]').nth(1).fill('654321');
    await page.getByPlaceholder('6位验证码').fill('112233');
    await page.getByRole('button', { name: '设置密码' }).click();

    await expect(page.getByText('两次输入的密码不一致')).toBeVisible();
    expect(submitCount).toBe(0);
  });
});
