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

function createOpsApiMock() {
  let executeCount = 0;
  const executeJobIds = [];
  const seedReplayActions = Array.from({ length: 120 }).map((_, index) => ({
    auditId: 17000 + index,
    scope: index % 2 === 0 ? 'final' : 'phase',
    jobId: 1000 + index,
    sessionId: 601,
    requestedBy: 1001,
    reason: `ops_seed_page_${index}`,
    previousStatus: 'failed',
    newStatus: 'queued',
    previousTraceId: `trace-seed-before-${index}`,
    newTraceId: `trace-seed-after-${index}`,
    previousIdempotencyKey: `seed-old-key-${index}`,
    newIdempotencyKey: `seed-new-key-${index}`,
    createdAt: new Date(Date.parse('2026-03-18T01:20:00Z') - index * 1000).toISOString(),
  }));
  return {
    async route(page) {
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
              scannedCount: 2,
              returnedCount: 2,
              phaseCount: 1,
              finalCount: 1,
              failedCount: 2,
              replayEligibleCount: 2,
              items: [
                {
                  scope: 'final',
                  sessionId: 601,
                  traceId: 'trace-final-replay-e2e',
                  idempotencyKey: 'judge_final:e2e',
                  status: 'failed',
                  createdAt: '2026-03-18T01:00:00Z',
                  dispatchAttempts: 1,
                  errorMessage: '[http_5xx] failed',
                  errorCode: 'http_5xx',
                  contractFailureType: 'unknown_contract_failure',
                  finalJobId: 901,
                  phaseJobId: null,
                  phaseNo: null,
                  phaseStartNo: 1,
                  phaseEndNo: 2,
                  phaseReportId: null,
                  finalReportId: 1001,
                  jobId: 901,
                  reportId: 1001,
                  replayActionCount: 0,
                  latestReplayActionId: null,
                  latestReplayAt: null,
                  replayEligible: true,
                  replayRecommendation: 'replay_final_job',
                },
                {
                  scope: 'phase',
                  sessionId: 601,
                  traceId: 'trace-phase-replay-e2e',
                  idempotencyKey: 'judge_phase:e2e',
                  status: 'failed',
                  createdAt: '2026-03-18T01:02:00Z',
                  dispatchAttempts: 2,
                  errorMessage: '[judge_timeout] phase timed out',
                  errorCode: 'judge_timeout',
                  contractFailureType: null,
                  finalJobId: null,
                  phaseJobId: 902,
                  phaseNo: 3,
                  phaseStartNo: null,
                  phaseEndNo: null,
                  phaseReportId: null,
                  finalReportId: null,
                  jobId: 902,
                  reportId: null,
                  replayActionCount: 0,
                  latestReplayActionId: null,
                  latestReplayAt: null,
                  replayEligible: true,
                  replayRecommendation: 'replay_phase_job',
                },
              ],
            }),
          });
          return;
        }
        if (pathname === '/api/debate/ops/judge-replay/actions') {
          const limit = Math.max(1, Number(url.searchParams.get('limit') || 50));
          const offset = Math.max(0, Number(url.searchParams.get('offset') || 0));
          const runtimeReplayActions = executeCount > 0
            ? [{
              auditId: 18888,
              scope: 'final',
              jobId: 901,
              sessionId: 601,
              requestedBy: 1001,
              reason: 'ops_ui_manual_replay',
              previousStatus: 'failed',
              newStatus: 'queued',
              previousTraceId: 'trace-final-replay-e2e',
              newTraceId: 'trace-final-replay-e2e-rerun',
              previousIdempotencyKey: 'old-key',
              newIdempotencyKey: 'new-key',
              createdAt: '2026-03-18T01:30:00Z',
            }]
            : [];
          const allReplayActions = [...runtimeReplayActions, ...seedReplayActions];
          const items = allReplayActions.slice(offset, offset + limit);
          const hasMore = offset + items.length < allReplayActions.length;
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              scannedCount: allReplayActions.length,
              returnedCount: items.length,
              hasMore,
              items,
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
              snapshotHash: 'abcdef0123456789abcdef0123456789abcdef01',
              meta: {
                scope: 'final',
                jobId: 901,
                sessionId: 601,
                status: 'failed',
                traceId: 'trace-final-replay-e2e',
                idempotencyKey: 'judge_final:e2e',
                rubricVersion: 'v3',
                judgePolicyVersion: 'v3-default',
                topicDomain: 'default',
                createdAt: '2026-03-18T01:00:00Z',
                dispatchAttempts: 1,
                replayEligible: true,
              },
              requestSnapshot: {
                marker: 'e2e-preview-payload',
                scope: 'final',
                jobId: 901,
              },
            }),
          });
          return;
        }
        if (pathname === '/api/debate/ops/judge-replay/execute') {
          executeCount += 1;
          const payload = request.postDataJSON() || {};
          executeJobIds.push(Number(payload?.jobId || 0));
          const scope = String(payload?.scope || 'final');
          const jobId = Number(payload?.jobId || 901);
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              auditId: 18880 + executeCount,
              scope,
              jobId,
              sessionId: 601,
              previousStatus: 'failed',
              newStatus: 'queued',
              previousTraceId: `trace-${scope}-${jobId}-before`,
              newTraceId: `trace-${scope}-${jobId}-after`,
              previousIdempotencyKey: `${scope}-${jobId}-old-key`,
              newIdempotencyKey: `${scope}-${jobId}-new-key`,
              replayTriggeredAt: '2026-03-18T01:10:00Z',
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
            body: JSON.stringify({ rows: [], windowHours: 24, limit: 20 }),
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
    },
    getExecuteCount() {
      return executeCount;
    },
    getExecuteJobIds() {
      return executeJobIds.slice();
    },
  };
}

test('ops admin should support replay preview and execute flow', async ({ page }) => {
  await bootstrapAuthState(page);
  const mock = createOpsApiMock();
  await mock.route(page);

  await page.goto('http://127.0.0.1:1420/debate/ops');

  await page.getByRole('button', { name: '预览' }).first().click();
  await expect(page.getByText('Replay 预览')).toBeVisible();
  await expect(page.getByText('e2e-preview-payload')).toBeVisible();

  await page.getByRole('button', { name: /^执行回放$/ }).first().click();
  await expect(page.getByText('已触发回放：auditId=18881')).toBeVisible();
  await expect(page.getByText('ops_ui_manual_replay')).toBeVisible();
  await expect.poll(() => mock.getExecuteCount()).toBe(1);
});

test('ops admin should support batch replay execution for selected candidates', async ({ page }) => {
  await bootstrapAuthState(page);
  const mock = createOpsApiMock();
  await mock.route(page);

  await page.goto('http://127.0.0.1:1420/debate/ops');

  await page.getByRole('button', { name: '全选候选' }).click();
  await page.getByRole('button', { name: '批量执行回放' }).click();

  await expect(page.getByText('批量回放执行完成：成功 2 条，失败 0 条')).toBeVisible();
  await expect.poll(() => mock.getExecuteCount()).toBe(2);
  await expect.poll(() => mock.getExecuteJobIds().sort((a, b) => a - b).join(',')).toBe('901,902');
});

test('ops admin replay actions should support quick pagination controls', async ({ page }) => {
  await bootstrapAuthState(page);
  const mock = createOpsApiMock();
  await mock.route(page);

  await page.goto('http://127.0.0.1:1420/debate/ops');

  await expect(page.getByText('当前分页: offset=0 · limit=50')).toBeVisible();
  await expect(page.getByText('ops_seed_page_0')).toBeVisible();

  await page.getByRole('button', { name: '下一页' }).click();
  await expect(page.getByText('当前分页: offset=50 · limit=50')).toBeVisible();
  await expect(page.getByText('ops_seed_page_50')).toBeVisible();

  await page.getByRole('button', { name: '上一页' }).click();
  await expect(page.getByText('当前分页: offset=0 · limit=50')).toBeVisible();
});
