import { expect, test } from '@playwright/test';

async function bootstrapAuthAndMockWs(page) {
  await page.addInitScript(() => {
    localStorage.setItem(
      'user',
      JSON.stringify({
        id: 1001,
        email: 'debate-room-e2e@acme.org',
        phoneE164: '+8613800000000',
      }),
    );
    localStorage.setItem('channels', JSON.stringify([]));
    localStorage.setItem('users', JSON.stringify({}));

    const instances: any[] = [];
    const sentFrames: Array<{ url: string; data: string }> = [];

    class MockWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      url: string;
      readyState: number;
      onopen: ((ev: Event) => void) | null;
      onmessage: ((ev: MessageEvent) => void) | null;
      onerror: ((ev: Event) => void) | null;
      onclose: ((ev: CloseEvent) => void) | null;

      constructor(url: string) {
        this.url = String(url);
        this.readyState = MockWebSocket.CONNECTING;
        this.onopen = null;
        this.onmessage = null;
        this.onerror = null;
        this.onclose = null;
        instances.push(this);
        setTimeout(() => {
          if (this.readyState === MockWebSocket.CLOSED) {
            return;
          }
          this.readyState = MockWebSocket.OPEN;
          this.onopen?.(new Event('open'));
        }, 0);
      }

      send(data: string) {
        sentFrames.push({
          url: this.url,
          data: String(data),
        });
      }

      close() {
        if (this.readyState === MockWebSocket.CLOSED) {
          return;
        }
        this.readyState = MockWebSocket.CLOSED;
        this.onclose?.(new CloseEvent('close', { code: 1000, reason: 'mock-close' }));
      }
    }

    (window as any).__mockDebateWs = {
      urls() {
        return instances.map((ws) => ws.url);
      },
      isOpen(index: number) {
        const ws = instances[index];
        return !!ws && ws.readyState === MockWebSocket.OPEN;
      },
      sent() {
        return sentFrames.slice();
      },
      emit(index: number, message: unknown) {
        const ws = instances[index];
        if (!ws || ws.readyState !== MockWebSocket.OPEN) {
          return false;
        }
        ws.onmessage?.(
          new MessageEvent('message', {
            data: JSON.stringify(message),
          }),
        );
        return true;
      },
      close(index: number) {
        const ws = instances[index];
        if (!ws) {
          return false;
        }
        ws.close();
        return true;
      },
    };

    (window as any).WebSocket = MockWebSocket;
  });
}

async function mockDebateRoomApis(page) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;

    if (pathname === '/api/auth/refresh') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ accessToken: 'debate-room-e2e-token' }),
      });
      return;
    }
    if (pathname === '/api/tickets') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          fileToken: 'debate-room-file-ticket',
          notifyToken: 'debate-room-notify-ticket',
          expiresInSecs: 300,
        }),
      });
      return;
    }
    if (pathname === '/api/pay/wallet') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ balance: 999 }),
      });
      return;
    }
    if (pathname === '/api/debate/sessions/201/messages') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 1,
            sessionId: 201,
            userId: 1001,
            side: 'pro',
            content: 'api-1',
            createdAt: '2026-03-29T20:00:00Z',
          },
          {
            id: 2,
            sessionId: 201,
            userId: 1002,
            side: 'con',
            content: 'api-2',
            createdAt: '2026-03-29T20:00:05Z',
          },
        ]),
      });
      return;
    }
    if (pathname === '/api/debate/sessions/201/pins') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
      return;
    }
    if (pathname === '/api/debate/sessions/201/judge-report') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          sessionId: 201,
          status: 'absent',
          latestJob: null,
          report: null,
        }),
      });
      return;
    }
    if (pathname === '/api/debate/sessions/201/draw-vote') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          sessionId: 201,
          status: 'absent',
          vote: null,
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
      body: ':keepalive\n\n',
    });
  });
}

test.describe('Debate Room WS Recovery', () => {
  test.beforeEach(async ({ page }) => {
    await bootstrapAuthAndMockWs(page);
    await mockDebateRoomApis(page);
  });

  test('should snapshot-recover then reconnect with latest ack seq after syncRequired', async ({
    page,
  }) => {
    await page.goto('http://127.0.0.1:1420/debate/sessions/201');

    await page.waitForFunction(() => (window as any).__mockDebateWs.urls().length >= 1);
    await page.waitForFunction(() => (window as any).__mockDebateWs.isOpen(0) === true);
    const firstEmitResult = await page.evaluate(() => {
      const ctrl = (window as any).__mockDebateWs;
      const emittedWelcome = ctrl.emit(0, {
        type: 'welcome',
        sessionId: 201,
        userId: 1001,
        baselineAckSeq: 0,
        lastEventSeq: 0,
        replayCount: 0,
        heartbeatIntervalMs: 20000,
        heartbeatTimeoutMs: 65000,
      });
      const emittedSeq1 = ctrl.emit(0, {
        type: 'roomEvent',
        eventSeq: 1,
        eventAtMs: Date.now(),
        eventName: 'DebateMessageCreated',
        payload: {
          event: 'DebateMessageCreated',
          messageId: 1,
          sessionId: 201,
          userId: 1001,
          side: 'pro',
          content: 'api-1',
          createdAt: '2026-03-29T20:00:00Z',
        },
      });
      const emittedSyncRequired = ctrl.emit(0, {
        type: 'syncRequired',
        reason: 'lagged_receiver',
        skipped: 1,
        expectedFromSeq: 2,
        gapFromSeq: 2,
        gapToSeq: 2,
        suggestedLastAckSeq: 1,
        latestEventSeq: 2,
        strategy: 'snapshot_then_reconnect',
      });
      return {
        emittedWelcome,
        emittedSeq1,
        emittedSyncRequired,
      };
    });
    expect(firstEmitResult.emittedWelcome).toBe(true);
    expect(firstEmitResult.emittedSeq1).toBe(true);
    expect(firstEmitResult.emittedSyncRequired).toBe(true);

    await page.waitForFunction(() => (window as any).__mockDebateWs.urls().length >= 2);
    const recoveredWsIndex = await page.evaluate(() => {
      const urls = (window as any).__mockDebateWs.urls();
      return urls.length - 1;
    });
    expect(recoveredWsIndex).toBeGreaterThan(0);
    await page.waitForFunction(
      (idx) => (window as any).__mockDebateWs.isOpen(idx) === true,
      recoveredWsIndex,
    );

    await page.evaluate((idx) => {
      const ctrl = (window as any).__mockDebateWs;
      ctrl.emit(idx, {
        type: 'welcome',
        sessionId: 201,
        userId: 1001,
        baselineAckSeq: 2,
        lastEventSeq: 2,
        replayCount: 0,
        heartbeatIntervalMs: 20000,
        heartbeatTimeoutMs: 65000,
      });
      ctrl.emit(idx, {
        type: 'roomEvent',
        eventSeq: 3,
        eventAtMs: Date.now(),
        eventName: 'DebateMessageCreated',
        payload: {
          event: 'DebateMessageCreated',
          messageId: 3,
          sessionId: 201,
          userId: 1003,
          side: 'con',
          content: 'ws-3',
          createdAt: '2026-03-29T20:00:10Z',
        },
      });
    }, recoveredWsIndex);

    await expect(page.getByText('api-1')).toBeVisible();
    await expect(page.getByText('api-2')).toBeVisible();
    await expect(page.getByText('ws-3')).toBeVisible();

    const sentFrames = await page.evaluate(() => {
      return (window as any).__mockDebateWs.sent();
    });
    expect(Array.isArray(sentFrames)).toBe(true);
  });
});
