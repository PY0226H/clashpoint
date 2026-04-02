import { expect, test } from '@playwright/test';

async function bootstrapAuthState(page) {
  await page.addInitScript(() => {
    localStorage.setItem('user', JSON.stringify({
      id: 1001,
      fullname: 'Chat Operator',
      email: 'chat-shell-e2e@acme.org',
      phoneE164: '+8613800001234',
    }));
    localStorage.setItem('channels', JSON.stringify([
      {
        id: 21,
        name: 'general',
        type: 'group',
        members: [1001, 1002],
      },
    ]));
    localStorage.setItem('single_channels', JSON.stringify([]));
    localStorage.setItem('activeChannelId', JSON.stringify(21));
    localStorage.setItem('users', JSON.stringify({
      1001: { id: 1001, fullname: 'Chat Operator', email: 'chat-shell-e2e@acme.org' },
      1002: { id: 1002, fullname: 'E2E Partner', email: 'peer@acme.org' },
    }));
  });
}

async function mockCommonApis(page, hooks = {}) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;
    const method = request.method();

    if (pathname === '/api/auth/refresh') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ accessToken: 'chat-shell-token' }),
      });
      return;
    }

    if (pathname === '/api/tickets') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          fileToken: 'chat-file-token',
          notifyToken: 'chat-notify-token',
          expiresInSecs: 300,
        }),
      });
      return;
    }

    if (pathname === '/api/chats/21/messages' && method === 'GET') {
      hooks.onMessages?.();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 9001,
            chatId: 21,
            senderId: 1002,
            content: '欢迎来到 EchoIsle 聊天室',
            modifiedContent: '',
            files: [],
            createdAt: '2026-03-03T01:00:00Z',
          },
        ]),
      });
      return;
    }

    if (pathname === '/api/chats/21' && method === 'POST') {
      hooks.onSendMessage?.();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 9002,
          chatId: 21,
          senderId: 1001,
          content: '收到，开始同步本轮事项。',
          modifiedContent: '',
          files: [],
          createdAt: '2026-03-03T01:01:00Z',
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

test('chat page should render refreshed workspace shell', async ({ page }) => {
  await bootstrapAuthState(page);
  let messagesCalls = 0;
  await mockCommonApis(page, {
    onMessages: () => {
      messagesCalls += 1;
    },
  });

  await page.goto('http://127.0.0.1:1420/chat');

  await expect(page.getByRole('heading', { name: '会话工作台' })).toBeVisible();
  await expect(page.getByText('消息流', { exact: true })).toBeVisible();
  await expect(page.getByText('工作区动作')).toBeVisible();
  await expect(page.getByText('支持上传图片后随消息发送')).toBeVisible();
  await expect(page.getByText('欢迎来到 EchoIsle 聊天室')).toBeVisible();
  await expect.poll(() => messagesCalls).toBeGreaterThan(0);
});

test('chat page should send message to active channel', async ({ page }) => {
  await bootstrapAuthState(page);
  let sendMessageCalls = 0;
  await mockCommonApis(page, {
    onSendMessage: () => {
      sendMessageCalls += 1;
    },
  });

  await page.goto('http://127.0.0.1:1420/chat');

  await page.getByPlaceholder('输入消息并按 Enter 发送（Shift+Enter 可换行）').fill('收到，开始同步本轮事项。');
  await page.getByRole('button', { name: '发送消息' }).click();

  await expect.poll(() => sendMessageCalls).toBeGreaterThan(0);
  await expect(page.getByText('收到，开始同步本轮事项。')).toBeVisible();
});
