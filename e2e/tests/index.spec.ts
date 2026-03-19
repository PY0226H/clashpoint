import { expect, test } from '@playwright/test';

async function bootstrapAuthState(page) {
  await page.addInitScript(() => {
    localStorage.setItem('user', JSON.stringify({
      id: 1001,
      email: 'ops-e2e@acme.org',
      phoneE164: '+8613800000000',
    }));
    localStorage.setItem('channels', JSON.stringify([]));
    localStorage.setItem('users', JSON.stringify({}));
  });
}

async function mockOpsApis(page) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;

    if (pathname === '/api/auth/refresh') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ accessToken: 'ops-e2e-token' }),
      });
      return;
    }
    if (pathname === '/api/tickets') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          fileToken: 'e2e-file-ticket',
          notifyToken: 'e2e-notify-ticket',
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
          role: 'ops_admin',
          permissions: {
            debateManage: true,
            judgeReview: true,
            judgeRejudge: true,
            roleManage: true,
          },
        }),
      });
      return;
    }
    if (pathname === '/api/debate/ops/rbac/roles') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [] }),
      });
      return;
    }
    if (pathname === '/api/debate/ops/judge-reviews') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ scannedCount: 0, returnedCount: 0, items: [] }),
      });
      return;
    }
    if (pathname === '/api/debate/ops/judge-trace-replay') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scannedCount: 1,
          returnedCount: 1,
          phaseCount: 0,
          finalCount: 1,
          failedCount: 1,
          replayEligibleCount: 1,
          items: [
            {
              scope: 'final',
              sessionId: 501,
              traceId: 'trace-final-e2e',
              idempotencyKey: 'judge_final:e2e',
              status: 'failed',
              createdAt: '2026-03-18T00:00:00Z',
              dispatchAttempts: 1,
              errorMessage: '[e2e_failed] dispatch failed',
              errorCode: 'e2e_failed',
              contractFailureType: 'unknown_contract_failure',
              finalJobId: 701,
              phaseJobId: null,
              phaseNo: null,
              phaseStartNo: 1,
              phaseEndNo: 2,
              phaseReportId: null,
              finalReportId: 801,
              jobId: 701,
              reportId: 801,
              replayActionCount: 2,
              latestReplayActionId: 9001,
              latestReplayAt: '2026-03-18T00:10:00Z',
              replayEligible: true,
              replayRecommendation: 'replay_final_job',
            },
          ],
        }),
      });
      return;
    }
    if (pathname === '/api/debate/ops/judge-replay/actions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          scannedCount: 1,
          returnedCount: 1,
          hasMore: false,
          items: [
            {
              auditId: 9001,
              scope: 'final',
              jobId: 701,
              sessionId: 501,
              requestedBy: 1001,
              reason: 'ops seeded replay',
              previousStatus: 'failed',
              newStatus: 'queued',
              previousTraceId: 'trace-old-final',
              newTraceId: 'trace-new-final',
              previousIdempotencyKey: 'old-key',
              newIdempotencyKey: 'new-key',
              createdAt: '2026-03-18T00:10:00Z',
            },
          ],
        }),
      });
      return;
    }
    if (pathname === '/api/debate/ops/judge-replay/preview') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          sideEffectFree: true,
          snapshotHash: '0123456789abcdef0123456789abcdef01234567',
          meta: {
            scope: 'final',
            jobId: 701,
            sessionId: 501,
            status: 'failed',
            traceId: 'trace-final-e2e',
            idempotencyKey: 'judge_final:e2e',
            rubricVersion: 'v3',
            judgePolicyVersion: 'v3-default',
            topicDomain: 'default',
            createdAt: '2026-03-18T00:00:00Z',
            dispatchAttempts: 1,
            replayEligible: true,
          },
          requestSnapshot: { marker: 'index-preview' },
        }),
      });
      return;
    }
    if (pathname === '/api/debate/ops/judge-replay/execute') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          auditId: 9002,
          scope: 'final',
          jobId: 701,
          sessionId: 501,
          previousStatus: 'failed',
          newStatus: 'queued',
          previousTraceId: 'trace-old-final',
          newTraceId: 'trace-new-final',
          previousIdempotencyKey: 'old-key',
          newIdempotencyKey: 'new-key',
          replayTriggeredAt: '2026-03-18T00:20:00Z',
        }),
      });
      return;
    }
    if (pathname === '/api/debate/topics') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
      return;
    }
    if (pathname === '/api/debate/sessions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
      return;
    }
    if (pathname === '/api/debate/ops/observability/config') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({}),
      });
      return;
    }
    if (pathname === '/api/analytics/judge-refresh/summary') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          rows: [],
          windowHours: 24,
          limit: 20,
        }),
      });
      return;
    }
    if (pathname === '/api/analytics/judge-refresh/summary/metrics') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({}),
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

test('ops admin should render trace/replay and replay actions section', async ({ page }) => {
  await bootstrapAuthState(page);
  await mockOpsApis(page);

  await page.goto('http://127.0.0.1:1420/debate/ops');

  await expect(page.getByText('Trace / Replay 运维闭环')).toBeVisible();
  await expect(page.getByText('e2e_failed')).toBeVisible();
  await expect(page.getByText('ops seeded replay')).toBeVisible();
  await expect(page.getByRole('button', { name: /^执行回放$/ }).first()).toBeVisible();
});
