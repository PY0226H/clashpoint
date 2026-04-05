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
  let walletBalance = 180;
  let nextLedgerId = 7100;
  const judgeReadySessions = new Set<number>();
  const sessionPins = new Map<
    number,
    Array<{
      id: number;
      sessionId: number;
      messageId: number;
      userId: number;
      side: string;
      content: string;
      costCoins: number;
      pinSeconds: number;
      pinnedAt: string;
      expiresAt: string;
      status: string;
    }>
  >();
  const messageSessionById = new Map<number, number>();
  const walletLedger: Array<{
    id: number;
    orderId: number | null;
    entryType: string;
    amountDelta: number;
    balanceAfter: number;
    idempotencyKey: string;
    metadata: Record<string, unknown>;
    createdAt: string;
  }> = [
    {
      id: 7003,
      orderId: 9003,
      entryType: "iap_credit",
      amountDelta: 120,
      balanceAfter: 180,
      idempotencyKey: "iap_seed_9003",
      metadata: { source: "seed" },
      createdAt: "2026-01-01T01:02:00Z"
    },
    {
      id: 7002,
      orderId: 9002,
      entryType: "pin_debit",
      amountDelta: -20,
      balanceAfter: 60,
      idempotencyKey: "pin_seed_7002",
      metadata: { source: "seed" },
      createdAt: "2026-01-01T01:01:00Z"
    },
    {
      id: 7001,
      orderId: 9001,
      entryType: "iap_credit",
      amountDelta: 80,
      balanceAfter: 80,
      idempotencyKey: "iap_seed_9001",
      metadata: { source: "seed" },
      createdAt: "2026-01-01T00:58:00Z"
    }
  ];
  const opsRoleAssignments: Array<{
    userId: number;
    userEmail: string;
    userFullname: string;
    role: "ops_admin" | "ops_reviewer" | "ops_viewer";
    grantedBy: number;
    createdAt: string;
    updatedAt: string;
  }> = [
    {
      userId: 11,
      userEmail: "reviewer@echoisle.dev",
      userFullname: "Ops Reviewer",
      role: "ops_reviewer",
      grantedBy: 10,
      createdAt: "2026-01-01T00:10:00Z",
      updatedAt: "2026-01-01T00:12:00Z"
    }
  ];
  const opsObservabilityConfig = {
    thresholds: {
      lowSuccessRateThreshold: 95,
      highRetryThreshold: 1.8,
      highCoalescedThreshold: 2.5,
      highDbLatencyThresholdMs: 250,
      lowCacheHitRateThreshold: 70,
      minRequestForCacheHitCheck: 30
    },
    anomalyState: {
      "judge.success_rate.low": {
        acknowledgedAtMs: 1767229200000,
        suppressUntilMs: 1767231000000
      }
    },
    updatedBy: 10,
    updatedAt: "2026-01-01T01:10:00Z"
  };
  const splitReviewState: {
    paymentComplianceRequired: boolean | null;
    reviewNote: string;
    updatedBy: number;
    updatedAt: string;
  } = {
    paymentComplianceRequired: null,
    reviewNote: "",
    updatedBy: 10,
    updatedAt: "2026-01-01T01:12:00Z"
  };
  let nextSplitReviewAuditId = 9003;
  const splitReviewAudits: Array<{
    id: number;
    paymentComplianceRequired: boolean | null;
    reviewNote: string;
    updatedBy: number;
    createdAt: string;
  }> = [
    {
      id: 9002,
      paymentComplianceRequired: true,
      reviewNote: "payment compliance must be checked before split",
      updatedBy: 10,
      createdAt: "2026-01-01T01:07:00Z"
    },
    {
      id: 9001,
      paymentComplianceRequired: null,
      reviewNote: "",
      updatedBy: 10,
      createdAt: "2026-01-01T00:57:00Z"
    }
  ];
  const opsAlertItems = [
    {
      id: 501,
      alertKey: "judge.success_rate.low",
      ruleType: "threshold",
      severity: "high",
      alertStatus: "suppressed",
      title: "Judge success rate low",
      message: "success rate below threshold",
      metrics: { successRatePct: 93.1, threshold: 95 },
      recipients: [10],
      deliveryStatus: "sent",
      errorMessage: null,
      deliveredAt: "2026-01-01T01:09:00Z",
      createdAt: "2026-01-01T01:08:00Z",
      updatedAt: "2026-01-01T01:09:00Z"
    },
    {
      id: 500,
      alertKey: "judge.dispatch.retry.high",
      ruleType: "threshold",
      severity: "medium",
      alertStatus: "cleared",
      title: "Retry ratio high",
      message: "retry ratio recovered",
      metrics: { retryRatio: 1.2, threshold: 1.8 },
      recipients: [10],
      deliveryStatus: "sent",
      errorMessage: null,
      deliveredAt: "2026-01-01T01:02:00Z",
      createdAt: "2026-01-01T01:01:00Z",
      updatedAt: "2026-01-01T01:02:00Z"
    },
    {
      id: 499,
      alertKey: "judge.dispatch.latency.high",
      ruleType: "threshold",
      severity: "high",
      alertStatus: "raised",
      title: "Dispatch latency high",
      message: "dispatch latency above threshold",
      metrics: { p95LatencyMs: 218, threshold: 200 },
      recipients: [10],
      deliveryStatus: "sent",
      errorMessage: null,
      deliveredAt: "2026-01-01T00:58:00Z",
      createdAt: "2026-01-01T00:57:00Z",
      updatedAt: "2026-01-01T00:58:00Z"
    }
  ];
  const drawVoteStateBySession = new Map<
    number,
    {
      status: "open" | "decided" | "expired";
      resolution: "pending" | "keep_winner" | "open_rematch";
      myVote: boolean | null;
      participatedVoters: number;
      agreeVotes: number;
      disagreeVotes: number;
      rematchSessionId: number | null;
      votingEndsAt: string;
      decidedAt: string | null;
    }
  >();

  function matchSessionPath(pathname: string, suffix: string): number | null {
    const matched = pathname.match(new RegExp(`^/api/debate/sessions/(\\d+)/${suffix}$`));
    if (!matched?.[1]) {
      return null;
    }
    const id = Number(matched[1]);
    return Number.isFinite(id) && id > 0 ? id : null;
  }

  function getOrCreateDrawVoteState(sessionId: number) {
    const existing = drawVoteStateBySession.get(sessionId);
    if (existing) {
      return existing;
    }
    const created = {
      status: "open" as const,
      resolution: "pending" as const,
      myVote: null,
      participatedVoters: 0,
      agreeVotes: 0,
      disagreeVotes: 0,
      rematchSessionId: null,
      votingEndsAt: "2026-01-01T01:40:00Z",
      decidedAt: null
    };
    drawVoteStateBySession.set(sessionId, created);
    return created;
  }

  function getOrCreatePins(sessionId: number) {
    const existing = sessionPins.get(sessionId);
    if (existing) {
      return existing;
    }
    const initial = [
      {
        id: 3001,
        sessionId,
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
    ];
    sessionPins.set(sessionId, initial);
    return initial;
  }

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const requestUrl = new URL(request.url());
    const pathname = requestUrl.pathname;
    let body: Record<string, any> | undefined;
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

    if (pathname === "/api/debate/ops/rbac/me" && request.method() === "GET") {
      return json(route, 200, {
        userId: 10,
        isOwner: true,
        role: null,
        permissions: {
          debateManage: true,
          judgeReview: true,
          judgeRejudge: true,
          roleManage: true
        }
      });
    }

    if (pathname === "/api/debate/ops/rbac/roles" && request.method() === "GET") {
      return json(route, 200, {
        items: opsRoleAssignments
      });
    }

    if (pathname === "/api/debate/ops/observability/config" && request.method() === "GET") {
      return json(route, 200, opsObservabilityConfig);
    }

    if (pathname === "/api/debate/ops/observability/thresholds" && request.method() === "PUT") {
      const lowSuccessRateThreshold = Number(body?.lowSuccessRateThreshold);
      const highRetryThreshold = Number(body?.highRetryThreshold);
      const highCoalescedThreshold = Number(body?.highCoalescedThreshold);
      const highDbLatencyThresholdMs = Number(body?.highDbLatencyThresholdMs);
      const lowCacheHitRateThreshold = Number(body?.lowCacheHitRateThreshold);
      const minRequestForCacheHitCheck = Number(body?.minRequestForCacheHitCheck);

      if (
        !Number.isFinite(lowSuccessRateThreshold) ||
        !Number.isFinite(highRetryThreshold) ||
        !Number.isFinite(highCoalescedThreshold) ||
        !Number.isFinite(highDbLatencyThresholdMs) ||
        !Number.isFinite(lowCacheHitRateThreshold) ||
        !Number.isFinite(minRequestForCacheHitCheck)
      ) {
        return json(route, 400, { error: "invalid_observability_threshold_payload" });
      }

      opsObservabilityConfig.thresholds = {
        lowSuccessRateThreshold,
        highRetryThreshold,
        highCoalescedThreshold,
        highDbLatencyThresholdMs: Math.floor(highDbLatencyThresholdMs),
        lowCacheHitRateThreshold,
        minRequestForCacheHitCheck: Math.floor(minRequestForCacheHitCheck)
      };
      opsObservabilityConfig.updatedBy = 10;
      opsObservabilityConfig.updatedAt = "2026-01-01T01:31:00Z";
      return json(route, 200, opsObservabilityConfig);
    }

    if (pathname === "/api/debate/ops/observability/anomaly-state/actions" && request.method() === "POST") {
      const alertKey = String(body?.alertKey || "").trim();
      const action = String(body?.action || "")
        .trim()
        .toLowerCase();
      if (!alertKey) {
        return json(route, 400, { error: "invalid alert key for anomaly action" });
      }
      const nowMs = 1767229900000;
      const nowIso = "2026-01-01T01:25:00Z";
      const current = opsObservabilityConfig.anomalyState[alertKey] || {
        acknowledgedAtMs: 0,
        suppressUntilMs: 0
      };

      if (action === "ack" || action === "acknowledge") {
        opsObservabilityConfig.anomalyState[alertKey] = {
          ...current,
          acknowledgedAtMs: nowMs
        };
      } else if (action === "suppress" || action === "mute") {
        const suppressMinutesRaw = Number(body?.suppressMinutes || 10);
        const suppressMinutes = Number.isFinite(suppressMinutesRaw)
          ? Math.max(1, Math.min(1440, Math.floor(suppressMinutesRaw)))
          : 10;
        opsObservabilityConfig.anomalyState[alertKey] = {
          acknowledgedAtMs: Math.max(nowMs, current.acknowledgedAtMs),
          suppressUntilMs: nowMs + suppressMinutes * 60 * 1000
        };
      } else if (action === "clear" || action === "remove" || action === "unsuppress") {
        delete opsObservabilityConfig.anomalyState[alertKey];
      } else {
        return json(route, 400, {
          error: "invalid anomaly action, expect acknowledge/suppress/clear"
        });
      }

      opsObservabilityConfig.updatedBy = 10;
      opsObservabilityConfig.updatedAt = nowIso;
      return json(route, 200, opsObservabilityConfig);
    }

    if (pathname === "/api/debate/ops/observability/evaluate-once" && request.method() === "POST") {
      const dryRun = (requestUrl.searchParams.get("dryRun") || "").trim().toLowerCase() === "true";
      return json(route, 200, {
        scopesScanned: 3,
        alertsRaised: dryRun ? 0 : 1,
        alertsCleared: 0,
        alertsSuppressed: 1
      });
    }

    if (pathname === "/api/debate/ops/observability/metrics-dictionary" && request.method() === "GET") {
      return json(route, 200, {
        version: "v1",
        generatedAtMs: 1767229800000,
        items: [
          {
            key: "judge.dispatch.failed_total",
            category: "judge_dispatch",
            source: "chat_server.internal_ai.judge.dispatch.metrics",
            unit: "count",
            aggregation: "sum",
            description: "Judge dispatch failed delivery total.",
            target: null
          },
          {
            key: "judge.dispatch.callback_latency_p95_ms",
            category: "judge_dispatch",
            source: "ai_judge_service.trace_store",
            unit: "ms",
            aggregation: "p95",
            description: "Dispatch accepted to callback completed latency p95.",
            target: "<300000"
          }
        ]
      });
    }

    if (pathname === "/api/debate/ops/observability/slo-snapshot" && request.method() === "GET") {
      return json(route, 200, {
        windowMinutes: 30,
        generatedAtMs: 1767229800000,
        thresholds: opsObservabilityConfig.thresholds,
        signal: {
          successCount: 27,
          failedCount: 2,
          completedCount: 29,
          successRatePct: 93.1,
          avgDispatchAttempts: 1.5,
          p95LatencyMs: 218,
          pendingDlqCount: 1
        },
        rules: [
          {
            alertKey: "judge.success_rate.low",
            ruleType: "threshold",
            title: "Judge success rate low",
            severity: "high",
            isActive: true,
            status: "suppressed",
            suppressed: true,
            lastEmittedStatus: "raised",
            message: "success rate below threshold",
            metrics: { successRatePct: 93.1, threshold: 95 }
          },
          {
            alertKey: "judge.dispatch.retry.high",
            ruleType: "threshold",
            title: "Retry ratio high",
            severity: "medium",
            isActive: false,
            status: "cleared",
            suppressed: false,
            lastEmittedStatus: "cleared",
            message: "retry ratio healthy",
            metrics: { retryRatio: 1.2, threshold: 1.8 }
          }
        ]
      });
    }

    if (pathname === "/api/debate/ops/observability/split-readiness" && request.method() === "GET") {
      return json(route, 200, {
        generatedAtMs: 1767229800000,
        overallStatus: "watch",
        nextStep: "stabilize dispatch error budget before split",
        thresholds: [
          {
            key: "dispatch_error_budget",
            title: "Dispatch error budget",
            status: "watch",
            triggered: true,
            recommendation: "reduce retries and DLQ pending count",
            evidence: {
              failedCount: 2,
              pendingDlqCount: 1
            }
          },
          {
            key: "payment_compliance_review",
            title: "Payment compliance review",
            status: splitReviewState.paymentComplianceRequired ? "ready" : "watch",
            triggered: splitReviewState.paymentComplianceRequired !== true,
            recommendation: "confirm payment compliance gate before service split",
            evidence: {
              paymentComplianceRequired: splitReviewState.paymentComplianceRequired,
              reviewNote: splitReviewState.reviewNote,
              updatedBy: splitReviewState.updatedBy,
              updatedAt: splitReviewState.updatedAt
            }
          }
        ]
      });
    }

    if (pathname === "/api/debate/ops/observability/split-readiness/review" && request.method() === "PUT") {
      const paymentRaw = body?.paymentComplianceRequired;
      const noteRaw = body?.reviewNote;
      const paymentComplianceRequired =
        paymentRaw === null || paymentRaw === undefined ? null : Boolean(paymentRaw);
      const reviewNote = typeof noteRaw === "string" ? noteRaw.trim() : "";
      if (reviewNote.length > 1000) {
        return json(route, 400, { error: "split_review_note_too_long" });
      }
      splitReviewState.paymentComplianceRequired = paymentComplianceRequired;
      splitReviewState.reviewNote = reviewNote;
      splitReviewState.updatedBy = 10;
      splitReviewState.updatedAt = "2026-01-01T01:33:00Z";
      splitReviewAudits.unshift({
        id: nextSplitReviewAuditId++,
        paymentComplianceRequired,
        reviewNote,
        updatedBy: 10,
        createdAt: "2026-01-01T01:33:00Z"
      });
      return json(route, 200, {
        generatedAtMs: 1767229980000,
        overallStatus: "watch",
        nextStep: "stabilize dispatch error budget before split",
        thresholds: [
          {
            key: "dispatch_error_budget",
            title: "Dispatch error budget",
            status: "watch",
            triggered: true,
            recommendation: "reduce retries and DLQ pending count",
            evidence: {
              failedCount: 2,
              pendingDlqCount: 1
            }
          },
          {
            key: "payment_compliance_review",
            title: "Payment compliance review",
            status: paymentComplianceRequired ? "ready" : "watch",
            triggered: paymentComplianceRequired !== true,
            recommendation: "confirm payment compliance gate before service split",
            evidence: {
              paymentComplianceRequired,
              reviewNote,
              updatedBy: splitReviewState.updatedBy,
              updatedAt: splitReviewState.updatedAt
            }
          }
        ]
      });
    }

    if (pathname === "/api/debate/ops/observability/split-readiness/reviews" && request.method() === "GET") {
      const limitRaw = Number(requestUrl.searchParams.get("limit") || 3);
      const offsetRaw = Number(requestUrl.searchParams.get("offset") || 0);
      const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.floor(limitRaw)) : 3;
      const offset = Number.isFinite(offsetRaw) ? Math.max(0, Math.floor(offsetRaw)) : 0;
      const sliced = splitReviewAudits.slice(offset, offset + limit);
      return json(route, 200, {
        total: splitReviewAudits.length,
        limit,
        offset,
        items: sliced
      });
    }

    if (pathname === "/api/debate/ops/observability/alerts" && request.method() === "GET") {
      const statusFilter = (requestUrl.searchParams.get("status") || "").trim().toLowerCase();
      const limitRaw = Number(requestUrl.searchParams.get("limit") || 5);
      const offsetRaw = Number(requestUrl.searchParams.get("offset") || 0);
      const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.floor(limitRaw)) : 5;
      const offset = Number.isFinite(offsetRaw) ? Math.max(0, Math.floor(offsetRaw)) : 0;
      const filtered = statusFilter
        ? opsAlertItems.filter((item) => item.alertStatus === statusFilter)
        : [...opsAlertItems];
      const paged = filtered.slice(offset, offset + limit);
      return json(route, 200, {
        total: filtered.length,
        limit,
        offset,
        items: paged
      });
    }

    const upsertRoleMatch = pathname.match(/^\/api\/debate\/ops\/rbac\/roles\/(\d+)$/);
    if (upsertRoleMatch?.[1] && request.method() === "PUT") {
      const targetUserId = Number(upsertRoleMatch[1]);
      const role = String(body?.role || "").trim().toLowerCase();
      if (!["ops_admin", "ops_reviewer", "ops_viewer"].includes(role)) {
        return json(route, 400, { error: "invalid_role" });
      }
      const nowIso = "2026-01-01T01:15:00Z";
      const existing = opsRoleAssignments.find((item) => item.userId === targetUserId);
      if (existing) {
        existing.role = role as "ops_admin" | "ops_reviewer" | "ops_viewer";
        existing.updatedAt = nowIso;
        return json(route, 200, existing);
      }
      const created = {
        userId: targetUserId,
        userEmail: `user${targetUserId}@echoisle.dev`,
        userFullname: `User ${targetUserId}`,
        role: role as "ops_admin" | "ops_reviewer" | "ops_viewer",
        grantedBy: 10,
        createdAt: nowIso,
        updatedAt: nowIso
      };
      opsRoleAssignments.unshift(created);
      return json(route, 200, created);
    }

    const revokeRoleMatch = pathname.match(/^\/api\/debate\/ops\/rbac\/roles\/(\d+)$/);
    if (revokeRoleMatch?.[1] && request.method() === "DELETE") {
      const targetUserId = Number(revokeRoleMatch[1]);
      const index = opsRoleAssignments.findIndex((item) => item.userId === targetUserId);
      const removed = index >= 0;
      if (removed) {
        opsRoleAssignments.splice(index, 1);
      }
      return json(route, 200, {
        userId: targetUserId,
        removed
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

    const messageListSessionId = matchSessionPath(pathname, "messages");
    if (messageListSessionId && request.method() === "GET") {
      messageSessionById.set(2001, messageListSessionId);
      return json(route, 200, {
        items: [
          {
            id: 2001,
            sessionId: messageListSessionId,
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

    const pinListSessionId = matchSessionPath(pathname, "pins");
    if (pinListSessionId && request.method() === "GET") {
      const pins = getOrCreatePins(pinListSessionId);
      return json(route, 200, {
        items: pins,
        hasMore: false,
        nextCursor: null,
        revision: String(pins[0]?.id || "0")
      });
    }

    const messageCreateSessionId = matchSessionPath(pathname, "messages");
    if (messageCreateSessionId && request.method() === "POST") {
      messageSessionById.set(2002, messageCreateSessionId);
      return json(route, 201, {
        id: 2002,
        sessionId: messageCreateSessionId,
        userId: 10,
        side: "pro",
        content: body?.content || "new message",
        createdAt: "2026-01-01T01:06:00Z"
      });
    }

    const pinMessageMatch = pathname.match(/^\/api\/debate\/messages\/(\d+)\/pin$/);
    if (pinMessageMatch?.[1] && request.method() === "POST") {
      const messageId = Number(pinMessageMatch[1]);
      const pinSeconds = Math.max(1, Number(body?.pinSeconds || 60));
      const sessionId = messageSessionById.get(messageId) || 901;
      const pins = getOrCreatePins(sessionId);
      const pinId = 3000 + pins.length + 1;
      const debitedCoins = 20;
      walletBalance = Math.max(0, walletBalance - debitedCoins);
      pins.unshift({
        id: pinId,
        sessionId,
        messageId,
        userId: 10,
        side: "pro",
        content: `Pinned #${messageId}`,
        costCoins: debitedCoins,
        pinSeconds,
        pinnedAt: "2026-01-01T01:08:00Z",
        expiresAt: "2026-01-01T01:09:00Z",
        status: "active"
      });
      walletLedger.unshift({
        id: nextLedgerId++,
        orderId: null,
        entryType: "pin_debit",
        amountDelta: -debitedCoins,
        balanceAfter: walletBalance,
        idempotencyKey: String(body?.idempotencyKey || `pin_${messageId}`),
        metadata: {
          messageId,
          pinSeconds
        },
        createdAt: "2026-01-01T01:08:00Z"
      });
      return json(route, 200, {
        pinId,
        sessionId,
        messageId,
        ledgerId: nextLedgerId - 1,
        debitedCoins,
        walletBalance,
        pinSeconds,
        expiresAt: "2026-01-01T01:09:00Z",
        newlyPinned: true
      });
    }

    const judgeReportSessionId = matchSessionPath(pathname, "judge-report");
    if (judgeReportSessionId && request.method() === "GET") {
      if (!judgeReadySessions.has(judgeReportSessionId)) {
        return json(route, 200, {
          sessionId: judgeReportSessionId,
          status: "judging",
          finalDispatchDiagnostics: null,
          finalDispatchFailureStats: null,
          finalReport: null
        });
      }
      return json(route, 200, {
        sessionId: judgeReportSessionId,
        status: "closed",
        finalDispatchDiagnostics: null,
        finalDispatchFailureStats: null,
        finalReport: {
          finalReportId: 5001,
          finalJobId: 6001,
          winner: "draw",
          proScore: 8.2,
          conScore: 8.2,
          finalRationale: "双方关键观点质量接近，建议进入平票流程。",
          winnerFirst: null,
          winnerSecond: null,
          rejudgeTriggered: false,
          needsDrawVote: true,
          dimensionScores: {
            logic: { pro: 8, con: 8 },
            evidence: { pro: 8, con: 8 }
          },
          verdictEvidenceRefs: [],
          phaseRollupSummary: [],
          retrievalSnapshotRollup: [],
          judgeTrace: {},
          auditAlerts: [],
          errorCodes: [],
          degradationLevel: 0,
          createdAt: "2026-01-01T01:20:00Z"
        }
      });
    }

    const judgeRequestSessionId = matchSessionPath(pathname, "judge/jobs");
    if (judgeRequestSessionId && request.method() === "POST") {
      judgeReadySessions.add(judgeRequestSessionId);
      getOrCreateDrawVoteState(judgeRequestSessionId);
      return json(route, 202, {
        accepted: true,
        sessionId: judgeRequestSessionId,
        status: "queued",
        reason: null,
        queuedPhaseJobs: 3,
        queuedFinalJob: true,
        triggerMode: "manual"
      });
    }

    const drawVoteSessionId = matchSessionPath(pathname, "draw-vote");
    if (drawVoteSessionId && request.method() === "GET") {
      if (!judgeReadySessions.has(drawVoteSessionId)) {
        return json(route, 200, {
          sessionId: drawVoteSessionId,
          status: "absent",
          vote: null
        });
      }
      const state = getOrCreateDrawVoteState(drawVoteSessionId);
      return json(route, 200, {
        sessionId: drawVoteSessionId,
        status: state.status,
        vote: {
          voteId: drawVoteSessionId * 10,
          finalReportId: 5001,
          status: state.status,
          resolution: state.resolution,
          decisionSource: state.status === "open" ? "awaiting_threshold" : "majority",
          thresholdPercent: 60,
          eligibleVoters: 2,
          requiredVoters: 2,
          participatedVoters: state.participatedVoters,
          agreeVotes: state.agreeVotes,
          disagreeVotes: state.disagreeVotes,
          votingEndsAt: state.votingEndsAt,
          decidedAt: state.decidedAt,
          myVote: state.myVote,
          rematchSessionId: state.rematchSessionId
        }
      });
    }

    const drawVoteSubmitSessionId = matchSessionPath(pathname, "draw-vote/ballots");
    if (drawVoteSubmitSessionId && request.method() === "POST") {
      if (!judgeReadySessions.has(drawVoteSubmitSessionId)) {
        return json(route, 409, { error: "draw_vote_absent" });
      }
      const agree = body?.agreeDraw === true;
      const state = getOrCreateDrawVoteState(drawVoteSubmitSessionId);
      state.status = "decided";
      state.myVote = agree;
      state.participatedVoters = 2;
      state.agreeVotes = agree ? 2 : 0;
      state.disagreeVotes = agree ? 0 : 2;
      state.resolution = agree ? "open_rematch" : "keep_winner";
      state.decidedAt = "2026-01-01T01:25:00Z";
      state.rematchSessionId = agree ? drawVoteSubmitSessionId + 1 : null;
      return json(route, 200, {
        sessionId: drawVoteSubmitSessionId,
        status: state.status,
        vote: {
          voteId: drawVoteSubmitSessionId * 10,
          finalReportId: 5001,
          status: state.status,
          resolution: state.resolution,
          decisionSource: "majority",
          thresholdPercent: 60,
          eligibleVoters: 2,
          requiredVoters: 2,
          participatedVoters: state.participatedVoters,
          agreeVotes: state.agreeVotes,
          disagreeVotes: state.disagreeVotes,
          votingEndsAt: state.votingEndsAt,
          decidedAt: state.decidedAt,
          myVote: state.myVote,
          rematchSessionId: state.rematchSessionId
        },
        newlySubmitted: true
      });
    }

    if (pathname === "/api/pay/iap/products" && request.method() === "GET") {
      return json(route, 200, {
        items: [
          { productId: "coins_60", coins: 60, isActive: true },
          { productId: "coins_180", coins: 180, isActive: true }
        ],
        revision: "iap_rev_1",
        emptyReason: null
      });
    }

    if (pathname === "/api/pay/iap/orders/by-transaction" && request.method() === "GET") {
      const transactionId = requestUrl.searchParams.get("transactionId") || "";
      if (transactionId === "tx-verified-001") {
        return json(route, 200, {
          found: true,
          order: {
            orderId: 9101,
            status: "verified",
            verifyMode: "mock",
            verifyReason: null,
            productId: "coins_180",
            coins: 180,
            credited: true
          },
          probeStatus: "verified_credited",
          nextRetryAfterMs: null
        });
      }
      if (transactionId === "tx-pending-001") {
        return json(route, 200, {
          found: true,
          order: {
            orderId: 9102,
            status: "pending",
            verifyMode: "apple",
            verifyReason: "apple_pending",
            productId: "coins_60",
            coins: 60,
            credited: false
          },
          probeStatus: "pending_credit",
          nextRetryAfterMs: 1200
        });
      }
      return json(route, 200, {
        found: false,
        order: null,
        probeStatus: "not_found",
        nextRetryAfterMs: null
      });
    }

    if (pathname === "/api/pay/wallet/ledger" && request.method() === "GET") {
      const lastIdRaw = requestUrl.searchParams.get("lastId");
      const lastId = lastIdRaw ? Number(lastIdRaw) : null;
      const items =
        lastId == null
          ? walletLedger.slice(0, 2)
          : walletLedger.filter((item) => item.id < lastId).slice(0, 2);
      const tail = items[items.length - 1]?.id ?? null;
      const hasMore = tail != null ? walletLedger.some((item) => item.id < tail) : false;
      return json(route, 200, {
        items,
        nextLastId: tail,
        hasMore
      });
    }

    if (pathname === "/api/pay/wallet" && request.method() === "GET") {
      return json(route, 200, {
        userId: 10,
        balance: walletBalance,
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

test("@smoke room judge-draw flow should support rematch jump", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Lobby" }).click();
  await page.getByRole("button", { name: "Join Pro" }).click();

  await expect(page).toHaveURL(/\/debate\/sessions\/901$/);
  await page.getByRole("button", { name: "Request AI Judge" }).click();
  await expect(page.getByText("Judge request accepted")).toBeVisible();
  await expect(page.getByText("Winner: DRAW")).toBeVisible();
  await expect(page.getByText("Resolution: pending")).toBeVisible();

  await page.getByRole("button", { name: "Vote Draw" }).click();
  await expect(page.getByText("Resolution: open_rematch")).toBeVisible();
  await page.getByRole("button", { name: "Go To Rematch #902" }).click();
  await expect(page).toHaveURL(/\/debate\/sessions\/902$/);
  await expect(page.getByRole("heading", { name: "Debate Room #902" })).toBeVisible();
});

test("@smoke room should pin message and consume wallet", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Lobby" }).click();
  await page.getByRole("button", { name: "Join Pro" }).click();

  await expect(page).toHaveURL(/\/debate\/sessions\/901$/);
  await page.getByRole("button", { name: "Pin 60s" }).first().click();
  await expect(page.getByText("Pinned message #2001")).toBeVisible();
  await expect(page.getByText("balance=160")).toBeVisible();
});

test("@smoke wallet page should render products ledger and probe", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Wallet" }).click();

  await expect(page).toHaveURL(/\/wallet$/);
  await expect(page.getByRole("heading", { name: "Wallet & Top-Up" })).toBeVisible();
  await expect(page.getByText("coins_180")).toBeVisible();
  await page.getByLabel("Transaction ID").fill("tx-verified-001");
  await page.getByRole("button", { name: "Probe Order" }).click();
  await expect(page.getByText("Order #9101")).toBeVisible();
  await page.getByRole("button", { name: "Load Older Entries" }).click();
  await expect(page.getByText("#7001 | iap_credit")).toBeVisible();
});

test("@smoke wallet probe pending order should show retry hint", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Wallet" }).click();

  await expect(page).toHaveURL(/\/wallet$/);
  await page.getByLabel("Transaction ID").fill("tx-pending-001");
  await page.getByRole("button", { name: "Probe Order" }).click();
  await expect(page.getByText("Probe Status: pending_credit")).toBeVisible();
  await expect(page.getByText("Next Retry: 1200 ms")).toBeVisible();
});

test("@smoke ops console should show rbac and support role upsert/revoke", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Ops" }).click();

  await expect(page).toHaveURL(/\/ops$/);
  await expect(page.getByRole("heading", { name: "Ops Console" })).toBeVisible();
  await expect(page.getByText("role_manage")).toBeVisible();
  await expect(page.getByText("#11 | ops_reviewer")).toBeVisible();

  await page.getByLabel("Target User ID").fill("42");
  await page.getByLabel("Target Role").selectOption("ops_admin");
  await page.getByRole("button", { name: "Grant Role" }).click();

  await expect(page.getByText("#42 | ops_admin")).toBeVisible();
  await page.getByRole("button", { name: "Revoke #42" }).click();
  await expect(page.getByText("#42 | ops_admin")).toHaveCount(0);
  await expect(page.getByText("SLO Success Rate")).toBeVisible();
  await expect(page.getByText("judge.dispatch.failed_total")).toBeVisible();
  await expect(page.getByText("next step: stabilize dispatch error budget before split")).toBeVisible();
  await page.getByLabel("Alert Page Size").selectOption("1");
  await expect(page.getByText("#501 | judge.success_rate.low | suppressed")).toBeVisible();
  await page.getByRole("button", { name: "Next Alerts" }).click();
  await expect(page.getByText("#500 | judge.dispatch.retry.high | cleared")).toBeVisible();
  await page.getByLabel("Alert Status").selectOption("raised");
  await expect(page.getByText("#499 | judge.dispatch.latency.high | raised")).toBeVisible();
  await page.getByRole("button", { name: "Refresh Snapshot" }).click();
  await expect(page.getByText("Observability snapshot refreshed.")).toBeVisible();
  await page.getByLabel("Threshold lowSuccessRateThreshold").fill("92");
  await page.getByRole("button", { name: "Save Thresholds" }).click();
  await expect(page.getByText("Observability thresholds updated.")).toBeVisible();
  await expect(page.getByLabel("Threshold lowSuccessRateThreshold")).toHaveValue("92");
  await page.getByLabel("Suppress Minutes").fill("7");
  await page.getByRole("button", { name: "Suppress judge.dispatch.retry.high" }).click();
  await expect(page.getByText("Anomaly action applied: suppress judge.dispatch.retry.high.")).toBeVisible();
  await page.getByRole("button", { name: "Evaluate Dry Run" }).click();
  await expect(page.getByText("Ops evaluation dry-run: raised=0, cleared=0, suppressed=1.")).toBeVisible();
  await page.getByRole("button", { name: "Evaluate Once" }).click();
  await expect(page.getByText("Ops evaluation run: raised=1, cleared=0, suppressed=1.")).toBeVisible();
  await page.getByLabel("Split Review Payment Compliance").selectOption("required");
  await page.getByLabel("Split Review Note").fill("manual compliance review passed");
  await page.getByRole("button", { name: "Save Split Review" }).click();
  await expect(page.getByText("Split readiness review updated.")).toBeVisible();
  await expect(page.getByText(/#9003 \| compliance: required \| by #10 \| at .+ \| note: manual compliance review passed/)).toBeVisible();
  await expect(page.getByText(/note: manual compliance review passed/)).toBeVisible();
  await page.getByLabel("Split Review Compliance Filter").selectOption("required");
  await page.getByLabel("Split Review Keyword Filter").fill("manual compliance");
  await page.getByLabel("Split Review Created After ISO").fill("2026-01-01T01:32:00Z");
  await page.getByLabel("Split Review Created Before ISO").fill("2026-01-01T01:34:00Z");
  await expect(page.getByText(/#9003 \| compliance: required \| by #10 \| at .+ \| note: manual compliance review passed/)).toBeVisible();
  await expect(page.getByText("#9002 | compliance: required")).toHaveCount(0);
  await page.getByRole("button", { name: "Clear Audit Filters" }).click();
  await expect(page.getByText("#9002 | compliance: required")).toBeVisible();
});

test("@auth-error pin should show insufficient wallet balance error", async ({ page }) => {
  await page.route("**/api/debate/messages/*/pin", async (route) => {
    await json(route, 409, { error: "wallet_balance_insufficient" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Lobby" }).click();
  await page.getByRole("button", { name: "Join Pro" }).click();

  await expect(page).toHaveURL(/\/debate\/sessions\/901$/);
  await page.getByRole("button", { name: "Pin 60s" }).first().click();
  await expect(page.getByText("wallet_balance_insufficient")).toBeVisible();
});

test("@auth-error ops console should degrade when judge review permission missing", async ({ page }) => {
  await page.route("**/api/debate/ops/rbac/me", async (route) => {
    await json(route, 200, {
      userId: 10,
      isOwner: false,
      role: "ops_viewer",
      permissions: {
        debateManage: false,
        judgeReview: false,
        judgeRejudge: false,
        roleManage: false
      }
    });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Ops" }).click();
  await expect(page).toHaveURL(/\/ops$/);
  await expect(page.getByText("Role management requires `role_manage` permission from platform owner scope.")).toBeVisible();
  await expect(page.getByText("Observability panels require `judge_review` permission.")).toBeVisible();
});

test("@auth-error ops console should show alerts permission error when backend rejects", async ({ page }) => {
  await page.route("**/api/debate/ops/observability/alerts**", async (route) => {
    await json(route, 409, { error: "ops_permission_denied:judge_review:backend_policy_mismatch" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Ops" }).click();
  await expect(page).toHaveURL(/\/ops$/);
  await expect(page.getByText("ops_permission_denied:judge_review:backend_policy_mismatch")).toBeVisible();
});

test("@auth-error ops anomaly action should show permission error when backend rejects", async ({ page }) => {
  await page.route("**/api/debate/ops/observability/anomaly-state/actions**", async (route) => {
    await json(route, 409, { error: "ops_permission_denied:judge_review:anomaly_action" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Ops" }).click();
  await expect(page).toHaveURL(/\/ops$/);
  await page.getByRole("button", { name: "Acknowledge judge.success_rate.low" }).click();
  await expect(page.getByText("ops_permission_denied:judge_review:anomaly_action")).toBeVisible();
});

test("@auth-error ops evaluate-once should show rate-limit grade when backend returns 429", async ({ page }) => {
  await page.route("**/api/debate/ops/observability/evaluate-once**", async (route) => {
    await json(route, 429, { error: "ops_observability_evaluate_once_rate_limited" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Ops" }).click();
  await expect(page).toHaveURL(/\/ops$/);
  await page.getByRole("button", { name: "Evaluate Once" }).click();
  await expect(
    page.getByText("Evaluate run rejected [rate_limit]: ops_observability_evaluate_once_rate_limited.")
  ).toBeVisible();
});

test("@auth-error ops evaluate-once should show bad-request grade when backend returns 400", async ({ page }) => {
  await page.route("**/api/debate/ops/observability/evaluate-once**", async (route) => {
    await json(route, 400, { error: "invalid_observability_evaluate_once_query" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Ops" }).click();
  await expect(page).toHaveURL(/\/ops$/);
  await page.getByRole("button", { name: "Evaluate Dry Run" }).click();
  await expect(
    page.getByText("Evaluate dry-run rejected [bad_request]: invalid_observability_evaluate_once_query.")
  ).toBeVisible();
});

test("@auth-error ops split review save should show permission error when backend rejects", async ({ page }) => {
  await page.route("**/api/debate/ops/observability/split-readiness/review", async (route) => {
    await json(route, 409, { error: "ops_permission_denied:judge_review:split_review_update" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Ops" }).click();
  await expect(page).toHaveURL(/\/ops$/);
  await page.getByLabel("Split Review Payment Compliance").selectOption("required");
  await page.getByLabel("Split Review Note").fill("attempt update with denied permission");
  await page.getByRole("button", { name: "Save Split Review" }).click();
  await expect(
    page.getByText(
      "Split review save rejected [permission_conflict]: ops_permission_denied:judge_review:split_review_update."
    )
  ).toBeVisible();
});

test("@auth-error ops split review save should show bad-request grade when backend returns 400", async ({ page }) => {
  await page.route("**/api/debate/ops/observability/split-readiness/review", async (route) => {
    await json(route, 400, { error: "split_review_note_too_long" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Ops" }).click();
  await expect(page).toHaveURL(/\/ops$/);
  await page.getByLabel("Split Review Payment Compliance").selectOption("required");
  await page.getByLabel("Split Review Note").fill("attempt update with too long note");
  await page.getByRole("button", { name: "Save Split Review" }).click();
  await expect(page.getByText("Split review save rejected [bad_request]: split_review_note_too_long.")).toBeVisible();
});

test("@auth-error ops console should aggregate observability multi-endpoint failures", async ({ page }) => {
  await page.route("**/api/debate/ops/observability/slo**", async (route) => {
    await json(route, 409, { error: "ops_permission_denied:judge_review:slo" });
  });
  await page.route("**/api/debate/ops/observability/metrics-dictionary**", async (route) => {
    await json(route, 500, { error: "metrics_dictionary_unavailable" });
  });
  await page.route("**/api/debate/ops/observability/split-readiness", async (route) => {
    await json(route, 503, { error: "split_readiness_unavailable" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Ops" }).click();
  await expect(page).toHaveURL(/\/ops$/);

  await expect(page.getByText("Observability snapshot partially unavailable (3 errors).")).toBeVisible();
  await expect(page.getByText("ops_permission_denied:judge_review:slo")).toBeVisible();
  await expect(page.getByText("metrics_dictionary_unavailable")).toBeVisible();
  await expect(page.getByText("split_readiness_unavailable").first()).toBeVisible();
});

test("@auth-error ops console should cap and truncate observability error details", async ({ page }) => {
  const longConfigError = `obs_config_error_long_prefix_${"x".repeat(220)}`;

  await page.route("**/api/debate/ops/observability/config", async (route) => {
    await json(route, 500, { error: longConfigError });
  });
  await page.route("**/api/debate/ops/observability/slo**", async (route) => {
    await json(route, 409, { error: "ops_permission_denied:judge_review:slo" });
  });
  await page.route("**/api/debate/ops/observability/metrics-dictionary**", async (route) => {
    await json(route, 500, { error: "metrics_dictionary_unavailable" });
  });
  await page.route("**/api/debate/ops/observability/split-readiness", async (route) => {
    await json(route, 503, { error: "split_readiness_unavailable" });
  });
  await page.route("**/api/debate/ops/observability/alerts**", async (route) => {
    await json(route, 500, { error: "alerts_feed_unavailable_due_to_backend_timeout" });
  });

  await page.goto("/login");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/home$/);
  await page.getByRole("link", { name: "Ops" }).click();
  await expect(page).toHaveURL(/\/ops$/);

  await expect(page.getByText("Observability snapshot partially unavailable (5 errors).")).toBeVisible();
  await expect(page.getByText("ops_permission_denied:judge_review:slo")).toBeVisible();
  await expect(page.getByText("metrics_dictionary_unavailable")).toBeVisible();
  await expect(page.getByText("split_readiness_unavailable").first()).toBeVisible();
  await expect(page.getByText("1 more errors hidden.")).toBeVisible();
  await expect(page.getByText(longConfigError)).toHaveCount(0);
  await expect(page.getByText(/obs_config_error_long_prefix_x+/)).toBeVisible();
  await expect(page.getByText("alerts_feed_unavailable_due_to_backend_timeout")).toHaveCount(0);
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
