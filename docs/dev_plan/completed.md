# completed.md

## A. 文档说明
- 本文件只记录“主体已完成”的模块快照，不承担开发过程记录。
- 每条完成项至少包含：模块、结论、代码证据、验证结论、归档来源。
- 若模块仍有后续压测、上线前收口、联调或告警固化工作，统一放入 `todo.md`，并在本文件用“关联待办”指向对应债务项。
- `归档来源` 记录的是“阶段收口来源/回合来源”，不是必须长期存在的计划文件路径。
- 历史前端路径说明：文中 `chatapp/...` 为历史证据路径，已于 2026-04-06（Phase6）净删除；当前前端主线目录为 `frontend/apps/*` 与 `frontend/packages/*`。

## B. 当前写入区（新结构）

### B1. 认证治理
| 模块 | 结论 | 代码证据 | 验证结论 | 归档来源 | 关联待办 |
|---|---|---|---|---|---|
| auth-session-revoke-hardening | `DELETE /api/auth/sessions/{sid}` 全链路优化已落地。 | `chat/chat_server/src/handlers/auth.rs`、`chat/migrations/20260402182000_auth_session_revoke_hardening.sql` | 本地回归测试与 handler/model 专项测试已补齐。 | 历史完成项迁移（2026-04-08） | `auth-session-revoke-redis-fault-injection-evidence`；`auth-session-revoke-multi-client-contract-alignment` |
| auth-sms-send-hardening | `POST /api/auth/v2/sms/send` 全链路优化已落地。 | `chat/chat_server/src/handlers/auth.rs`、`chat/chat_server/src/openapi.rs`、`chat/migrations/20260402203000_auth_sms_send_hardening.sql` | 本地回归测试已补齐，专项错误语义与指标已落地。 | 历史完成项迁移（2026-04-08） | `auth-sms-send-multi-client-contract-alignment`；`auth-sms-send-redis-fault-injection-evidence`；`auth-sms-send-callback-anti-replay` |

### B2. 支付与钱包
| 模块 | 结论 | 代码证据 | 验证结论 | 归档来源 | 关联待办 |
|---|---|---|---|---|---|
| pay-iap-verify-hardening | `POST /api/pay/iap/verify` 全链路优化已落地。 | `chat/chat_server/src/handlers/payment.rs`、`chat/chat_server/src/models/payment/order_ops.rs`、`chat/chat_server/src/openapi.rs` | handler/model 回归矩阵已补齐，事务边界与稳定错误码已收敛。 | 历史完成项迁移（2026-04-08） | `pay-iap-verify-multi-client-contract-alignment`；`pay-iap-verify-rate-limit-and-retry-baseline`；`pay-iap-verify-observability-dashboard-baseline` |
| pay-wallet-hardening | `GET /api/pay/wallet` 全链路优化已落地。 | `chat/chat_server/src/handlers/payment.rs`、`chat/chat_server/src/application/runtime_workers.rs` | 读缓存、账本对账 worker 与回归测试矩阵已落地。 | 历史完成项迁移（2026-04-08） | `pay-wallet-observability-dashboard-baseline`；`pay-wallet-reconcile-parameter-tuning`；`pay-wallet-reconcile-ops-query-surface` |

### B3. Debate / Ops / Room API
| 模块 | 结论 | 代码证据 | 验证结论 | 归档来源 | 关联待办 |
|---|---|---|---|---|---|
| debate-ops-topics-create-hardening | `POST /api/debate/ops/topics` 全链路优化已落地。 | `chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/models/debate/ops.rs`、`chat/migrations/20260407224500_ops_debate_topic_create_hardening.sql` | route + service 回归测试已通过。 | 历史完成项迁移（2026-04-08） | （无） |
| api058-rbac-roles-governance-phase-closure | `GET /api/debate/ops/rbac/roles` 阶段性收口已完成并归档。 | `chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/models/rbac.rs`、`chat/migrations/20260408042000_ops_rbac_audits.sql` | OpenAPI、限流、审计落库与前后端契约同步已完成。 | 当前开发计划阶段收口（2026-04-08） | （无） |
| api059-rbac-roles-write-governance-phase-closure | `PUT /api/debate/ops/rbac/roles/:user_id` 阶段性收口已完成（S0~S3-8：输入边界、原子写、幂等、受限委派、415/422 观测、If-Match 条件写与服务端强制、审计 outbox worker + 成功同事务入队、Owner 自写 warning、trusted proxy 来源治理）。 | `chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/handlers/debate.rs`、`chat/chat_server/src/models/rbac.rs`、`chat/chat_server/src/application/request_guard.rs`、`chat/chat_server/src/config.rs`、`frontend/packages/ops-domain/src/index.ts`、`frontend/packages/app-shell/src/pages/OpsConsolePage.tsx` | `ops_rbac_roles_user_id_route_should` 路由回归组通过（30 条）；`request_rate_limit_ip_key_with_user_fallback_should` 单测通过；`module-turn-harness --strict` 全量门禁通过并产出工件。 | 当前开发计划阶段收口（2026-04-09） | `api059-rbac-write-trusted-proxy-production-rollout`；`api059-rbac-write-forwarded-header-governance-rollout`；`api059-rbac-write-observability-and-load-baseline` |
| api060-rbac-roles-delete-governance-phase-closure | `DELETE /api/debate/ops/rbac/roles/:user_id` 本地阶段收口已完成（S1：invalid If-Match 回归、错误优先级契约冻结、revoke 观测信号补强；S2：strict/delete 去噪评审结论归档；S3：环境执行清单已形成）。 | `chat/chat_server/src/handlers/debate.rs`、`chat/chat_server/src/handlers/debate_ops.rs`、`docs/learning/Restful_Api/060_delete_api_debate_ops_rbac_roles_user_id.md` | `delete_ops_rbac_roles_user_id_route_should` 回归通过；`ops_rbac_roles_user_id_route_should` 回归通过；`module-turn-harness --strict` 门禁通过并产出工件。 | 当前开发计划阶段收口（2026-04-09） | `api060-rbac-delete-trusted-proxy-production-rollout`；`api060-rbac-delete-forwarded-header-governance-rollout`；`api060-rbac-delete-observability-and-load-baseline`；`api060-rbac-delete-semantic-strategy-observation` |
| api061-judge-reviews-governance-phase-closure | `GET /api/debate/ops/judge-reviews` 本地阶段收口已完成（S1：OpenAPI 错误契约补齐 + route/model 回归补齐；S2：接口观测日志补齐 + `winner_pass_missing` 异常规则落地；S2-3：读限流评估结论 No-Go 后置）。 | `chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/handlers/debate.rs`、`chat/chat_server/src/models/judge/request_report_query.rs`、`chat/chat_server/src/models/judge/tests/request_judge_report_query.rs`、`docs/learning/Restful_Api/061_get_api_debate_ops_judge_reviews.md` | `get_ops_judge_reviews_route_should*` 回归通过（6 条）；`list_judge_reviews_by_owner_should*` 回归通过（4 条）；`get_latest_judge_report_should*` 回归通过（4 条）；`module-turn-harness` 全量门禁通过并产出工件。 | 当前开发计划阶段收口（2026-04-09） | `api061-judge-reviews-pagination-upgrade-evaluation`；`api061-judge-reviews-threshold-configurability`；`api061-judge-reviews-query-performance-baseline`；`api061-judge-reviews-permission-status-semantics-review`；`api061-judge-reviews-read-rate-limit-rollout-decision` |
| api062-judge-final-dispatch-failure-stats-governance-phase-closure | `GET /api/debate/ops/judge-final-dispatch/failure-stats` 本地阶段收口已完成（S1：OpenAPI 错误契约补齐 + route/model 回归补齐；S2：结构化字段优先分类 + 接口观测日志补齐；S3：容量/语义/增强项后置）。 | `chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/handlers/debate.rs`、`chat/chat_server/src/models/judge/request_report_query.rs`、`chat/chat_server/src/models/judge/tests/request_judge_report_query.rs`、`docs/learning/Restful_Api/062_get_api_debate_ops_judge_final_dispatch_failure_stats.md` | `get_ops_judge_final_dispatch_failure_stats_route_should*` 回归通过（5 条）；`get_judge_final_dispatch_failure_stats_by_owner_should*` 回归通过（5 条）；`get_latest_judge_report_should_return_degraded_with_structured_final_failure` 回归通过（1 条）；`module-turn-harness` dry-run 工件已归档。 | 当前开发计划阶段收口（2026-04-09） | `api062-failure-stats-alert-threshold-baseline`；`api062-failure-stats-read-rate-limit-rollout-decision`；`api062-failure-stats-permission-status-semantics-review`；`api062-failure-stats-failure-type-filter-evaluation`；`api062-failure-stats-query-performance-baseline` |

### B4. 基础设施与工具链
| 模块 | 结论 | 代码证据 | 验证结论 | 归档来源 | 关联待办 |
|---|---|---|---|---|---|
| workspace-removal-closure | workspace 概念已完成清理并切到单租户语义。 | `scripts/quality/verify_chat_migrations_fresh.sh` | fresh migration 验证脚本可用于确认无 `ws_id` 列与 `workspaces` 表。 | 历史完成项迁移（2026-04-08） | （无） |

## Z. 历史完成归档（待迁移）
- 下方内容保留旧结构，仅用于查询和后续分批迁移。
- 新增完成项不要继续写入下方旧结构。

### B1. 产品主链路
| 模块 | 结论 | 代码证据 | 来源 |
|---|---|---|---|
| v2-m0-chat-group-membership-model | 群聊成员模型与主流程可用。 | `chat/chat_server/src/handlers/chat.rs` | 产品开发计划（统一版） |
| v2-m1-home-ia-and-entry-closure | 首页入口与主导航闭环已落地。 | `chatapp/src/views/Home.vue`（legacy，已删除） | 产品开发计划（统一版） |
| v2-m3-room-realtime-consistency-hardening | 房间实时同步与回补链路已落地。 | `chatapp/src/views/DebateRoom.vue`（legacy，已删除） | 产品开发计划（统一版） |
| v2-m5-ai-judge-runtime-sla-hardening | 判决自动触发+补偿触发链路已落地。 | `chat/chat_server/src/models/judge_dispatch.rs` | 产品开发计划（统一版） |
| v2-m6-draw-rematch-finalization-hardening | draw 投票与 rematch 闭环已落地。 | `chat/chat_server/src/handlers/debate_vote.rs` | 产品开发计划（统一版） |
| v2-m7-ops-scheduled-session-management | Ops 场次管理与状态推进 worker 已落地。 | `chat/chat_server/src/handlers/debate_ops.rs` | 产品开发计划（统一版） |
| v2-m8-judge-observability-and-ops-dashboard | 裁判观测与运维面板基础能力已落地。 | `chatapp/src/views/DebateOpsAdmin.vue`（legacy，已删除） | 产品开发计划（统一版） |
| v2-m9-fairness-and-evidence-governance | 公平性与证据治理主能力已落地。 | `chat/chat_server/src/models/judge/` | 产品开发计划（统一版） |
| v2-m11-rbac-for-ops-and-governance | Ops RBAC 权限治理已落地。 | `chat/chat_server/src/handlers/ops_roles.rs` | 产品开发计划（统一版） |
| workspace-removal-closure | workspace 概念已完成清理并切到单租户语义。 | `scripts/quality/verify_chat_migrations_fresh.sh` | Workspace 彻底删除执行计划 |

### B2. AI裁判能力
| 模块 | 结论 | 代码证据 | 来源 |
|---|---|---|---|
| ai_judge_service_v3_dispatch_callback_closure | v3 phase/final 派发与回调闭环已落地。 | `ai_judge_service/app/app_factory.py` | AI裁判开发计划 v3 |
| ai_judge_service_v3_phase_m4_baseline_pipeline | A2/A3/A4 总结与检索增强链路已落地。 | `ai_judge_service/app/phase_pipeline.py` | AI裁判开发计划 v3 |
| ai_judge_service_v3_phase_m5_agent2_bidirectional | A5/A6/A7/A8 双向评分链路已落地。 | `ai_judge_service/app/phase_pipeline.py` | AI裁判开发计划 v3 |
| ai_judge_service_v3_final_m6_a10_style_fact_lock | A9/A10 终局聚合与展示重写已落地。 | `ai_judge_service/app/phase_pipeline.py` | AI裁判开发计划 v3 |
| chat_server_v3_final_report_query_surface_m6 | finalReportV3 查询面已落地。 | `chat/chat_server/src/handlers/debate.rs` | AI裁判开发计划 v3 |
| ai_judge_service_v3_final_m7_contract_guard | final 合同字段阻断与审计告警已落地。 | `ai_judge_service/app/app_factory.py` | AI裁判开发计划 v3 |
| chat_server_v3_m7_final_dispatch_diagnostics | finalDispatchDiagnostics 查询透出已落地。 | `chat/chat_server/src/handlers/debate_ops.rs` | AI裁判开发计划 v3 |
| chat_server_v3_m7_contract_failure_type_mapping | contractFailureType 结构化映射已落地。 | `chat/chat_server/src/models/judge/contract_failure.rs` | AI裁判开发计划 v3 |
| chat_server_v3_m7_ops_failure_stats_aggregation | failure-stats 运维聚合接口已落地。 | `chat/chat_server/src/handlers/debate_ops.rs` | AI裁判开发计划 v3 |
| chat_server_v3_m8_trace_replay_ops_query | judge-trace-replay 聚合接口已落地。 | `chat/chat_server/src/handlers/debate_ops.rs` | AI裁判开发计划 v3 |
| chat_server_v3_m8_replay_preview_endpoint | judge-replay/preview 无副作用回放预览已落地。 | `chat/chat_server/src/handlers/debate_ops.rs` | AI裁判开发计划 v3 |
| chat_server_v3_m8_replay_execute_audit | judge-replay/execute 与审计落库已落地。 | `chat/chat_server/src/handlers/debate_ops.rs` | AI裁判开发计划 v3 |
| chatapp_v3_m8_ops_replay_batch_filter_and_bulk_execute | 前端批量回放与二次筛选已落地。 | `chatapp/src/views/DebateOpsAdmin.vue`（legacy，已删除） | AI裁判开发计划 v3 |
| chatapp_v3_m8_replay_actions_filter_and_pagination_quick_ops | 前端过滤分页与快捷操作已落地。 | `chatapp/src/store/index.js`（legacy，已删除） | AI裁判开发计划 v3 |
| ai-judge-bm25-lexical-upgrade | file lexical 检索已切到 bm25s，轻量 RAG 路线已落地。 | `ai_judge_service/app/lexical_retriever.py` | AI裁判RAG轻量重建计划 |

### B3. 认证治理
| 模块 | 结论 | 代码证据 | 来源 |
|---|---|---|---|
| auth-v2-consistency-soft-merge | 认证 V2 软合并策略与兼容窗口已落地。 | `chat/chat_server/src/handlers/auth.rs` | 登录方式改造后一致性收口方案 |
| auth-analytics-hash-fallback-tests | 认证埋点 hash 降级测试已落地。 | `chatapp/src/analytics/event.test.js`（legacy，已删除） | 产品开发计划（统一版） |
| auth-phone-required-hardening | 手机号门禁与受保护接口约束已落地。 | `chat/chat_server/src/middlewares/phone_bound.rs` | 产品开发计划（统一版） |
| auth-v2-password-set-flow | 后置设置密码核心链路已落地（接口、前端入口、短信校验）。 | `chat/chat_server/src/handlers/auth.rs`、`chatapp/src/views/Me.vue`（legacy，已删除） | 产品开发计划（统一版）+登录方式改造后一致性收口方案 |
| auth-v2-password-set-flow-samples | set password 联调样例与前端用例已落地。 | `test.rest` | 登录方式改造后一致性收口方案 |
| auth-analytics-clickhouse-readside-v2 | auth summary read-side 兼容新埋点字段已落地。 | `chat/analytics_server/src/lib.rs` | 登录方式改造后一致性收口方案 |
| auth-v2-password-set-sms-verification | set_password_v2 的短信校验链路已落地。 | `chat/chat_server/src/handlers/auth.rs` | 登录方式改造后一致性收口方案 |
| auth-dev-super-account-bootstrap | 本地超级账号免注册直登能力已落地，支持开发联调快速登录。 | `chat/chat_server/src/lib.rs`、`chat/chat_server/src/models/rbac.rs` | 当前开发计划（Mac端联调） |
| frontend-auth-phone-bind-unblock | 绑定手机号页循环拦截问题已修复，绑定完成后可稳定进入主流程。 | `chatapp/src/router/index.ts`、`chatapp/src/store/index.ts`、`chatapp/src/store/actions-auth-ops.ts`（legacy，已删除；现行实现在 `frontend/packages/app-shell`） | 当前开发计划（Mac端联调） |
| auth-cors-credentials-fix | `withCredentials` 跨域登录链路已修复，登录/refresh cookie 可在 Mac 客户端正常工作。 | `chat/chat_server/src/lib.rs`、`chat/notify_server/src/lib.rs` | 当前开发计划（Mac端联调） |
| auth-signup-phone-consistency | `signup_phone_v2` 一致性与可用性改造已落地（验证码原子核销、并发冲突 409 归一、建号+会话同事务、审计 best-effort）。 | `chat/chat_server/src/handlers/auth.rs`、`chat/chat_server/src/models/user.rs`、`chat/chat_server/src/redis_store.rs` | 当前开发计划（`POST /api/auth/v2/signup/phone` 一致性与可用性优化） |
| auth-refresh-hardening | `POST /api/auth/refresh` 一致性与安全性治理已落地（并发宽限分级、DB 权威裁决、outbox 补偿、错误码细化、token_version Redis-first、TTL 下限、CSRF 边界、可观测性增强）。 | `chat/chat_server/src/handlers/auth.rs`、`chat/chat_server/src/application/runtime_workers.rs`、`chat/chat_server/src/lib.rs`、`chat/migrations/20260402150000_auth_refresh_consistency_outbox.sql` | 当前开发计划（`POST /api/auth/refresh` 全链路优化） |
| auth-logout-all-hardening | `POST /api/auth/logout-all` 全链路优化已落地（事务内 outbox 持久化、目标态响应契约、意图校验对齐、短时幂等闸门、前端 logoutAll 并发门控、专项可观测性分桶与回归测试补齐）。 | `chat/chat_server/src/handlers/auth.rs`、`chatapp/src/store/index.ts`（legacy，已删除；现行实现在 `frontend/packages/auth-sdk`） | 当前开发计划（`POST /api/auth/logout-all` 全链路优化） |
| auth-session-revoke-hardening | `DELETE /api/auth/sessions/{sid}` 全链路优化已落地（原子 CTE 撤销、sid 索引 outbox 补偿、DLQ+replay、响应契约扩展、审计落库、专项指标、限频与专项回归测试）。 | `chat/chat_server/src/handlers/auth.rs`、`chat/migrations/20260402182000_auth_session_revoke_hardening.sql` | 当前开发计划（`DELETE /api/auth/sessions/{sid}` 全链路优化） |
| auth-sms-send-hardening | `POST /api/auth/v2/sms/send` 全链路优化已落地（错误语义 400/429/401、原子发码与冷却收敛、provider 受理记录+delivery callback、生产 fallback 收敛、可信代理校验、HMAC 审计哈希、专项指标与回归测试补齐）。 | `chat/chat_server/src/handlers/auth.rs`、`chat/chat_server/src/redis_store.rs`、`chat/chat_server/src/error.rs`、`chat/chat_server/src/openapi.rs`、`chat/migrations/20260402203000_auth_sms_send_hardening.sql` | 当前开发计划（`POST /api/auth/v2/sms/send` 全链路优化） |
| auth-sessions-list-hardening | `GET /api/auth/sessions` 全链路优化已落地（cursor 分页、`status/isCurrent/sessionRevision` 契约、sid 二次活跃校验、用户/IP 双限频、retention cleanup worker、专项指标、OpenAPI 400/401/429/500 覆盖与回归测试）。 | `chat/chat_server/src/handlers/auth.rs`、`chat/chat_core/src/middlewares/auth.rs`、`chat/chat_core/src/middlewares/mod.rs`、`chat/chat_server/src/application/runtime_workers.rs`、`chat/chat_server/src/lib.rs` | 当前开发计划（`GET /api/auth/sessions` 全链路优化） |
| auth-tickets-hardening | `POST /api/tickets` 全链路优化已落地（session-scoped claims: `sid/ver/jti`、claims 去 PII、user/IP 双限频、`500 tickets_issue_failed` 语义、OpenAPI `200/401/403/429/500`、file/notify 消费侧会话一致性校验、WS 子协议收敛为 `notify-ticket.<jwt>`、jti/sid 哈希化追踪与回归测试）。 | `chat/chat_server/src/handlers/ticket.rs`、`chat/chat_server/src/middlewares/ticket.rs`、`chat/chat_core/src/utils/jwt.rs`、`chat/notify_server/src/middlewares.rs`、`chat/notify_server/src/lib.rs`、`chat/notify_server/src/ws.rs`、`chat/analytics_server/src/lib.rs` | 当前开发计划（`POST /api/tickets` 全链路优化） |
| pay-iap-products-list-hardening | `GET /api/pay/iap/products` 全链路优化已落地（`activeOnly=false` 权限收敛、OpenAPI 错误契约补齐、`items/revision/emptyReason` 响应升级、本地缓存+revision 失效、用户/IP 双限频、专项指标日志、排序稳定与回归测试矩阵）。 | `chat/chat_server/src/handlers/payment.rs`、`chat/chat_server/src/models/payment/query_ops.rs`、`chat/chat_server/src/models/payment/types.rs`、`chat/chat_server/src/openapi.rs` | 当前开发计划（`GET /api/pay/iap/products` 全链路优化） |
| pay-iap-order-probe-hardening | `GET /api/pay/iap/orders/by-transaction` 全链路优化已落地（OpenAPI 400/401/403/409/429/500 契约补齐、稳定错误码、用户/IP 双限频、`probeStatus/nextRetryAfterMs` 响应语义、transaction 短 TTL probe 缓冲、verify 后缓存失效、`wallet_ledger` partial index、专项指标日志与回归测试矩阵）。 | `chat/chat_server/src/handlers/payment.rs`、`chat/chat_server/src/models/payment/query_ops.rs`、`chat/chat_server/src/models/payment/types.rs`、`chat/chat_server/src/models/payment/order_ops.rs`、`chat/chat_server/src/openapi.rs`、`chat/migrations/20260402224000_iap_order_probe_index.sql` | 当前开发计划（`GET /api/pay/iap/orders/by-transaction` 全链路优化） |
| pay-iap-verify-hardening | `POST /api/pay/iap/verify` 全链路优化已落地（OpenAPI 响应补齐 `200/400/401/403/404/409/429/500`、稳定错误码、可重试错误 `retryAfterMs`、事务外验票+事务内二次复核、用户维度幂等键、冲突结果直返、三层限流、verify 专项指标日志、SHA256 receipt hash、handler 回归矩阵）。 | `chat/chat_server/src/handlers/payment.rs`、`chat/chat_server/src/models/payment/order_ops.rs`、`chat/chat_server/src/models/payment/helpers.rs`、`chat/chat_server/src/models/payment/types.rs`、`chat/chat_server/src/models/payment.rs`、`chat/chat_server/src/models/mod.rs`、`chat/chat_server/src/openapi.rs` | 当前开发计划（`POST /api/pay/iap/verify` 全链路优化） |
| pay-wallet-hardening | `GET /api/pay/wallet` 全链路优化已落地（OpenAPI 响应补齐 `200/401/403/429/500`、user/IP 双限流、no-store 响应头、wallet 指标日志分桶、`walletRevision/walletInitialized` 响应语义、200ms 短窗口读缓存+写后失效、余额账本周期对账 worker 与审计表、handler/model 回归测试矩阵）。 | `chat/chat_server/src/handlers/payment.rs`、`chat/chat_server/src/models/payment/query_ops.rs`、`chat/chat_server/src/models/payment/types.rs`、`chat/chat_server/src/models/payment/order_ops.rs`、`chat/chat_server/src/models/debate/message_pin.rs`、`chat/chat_server/src/application/runtime_workers.rs`、`chat/migrations/20260403000000_wallet_balance_reconcile.sql` | 当前开发计划（`GET /api/pay/wallet` 全链路优化） |
| pay-wallet-ledger-hardening | `GET /api/pay/wallet/ledger` 全链路优化已落地（OpenAPI 补齐 `200/400/401/403/429/500`、user/IP 双限流、no-store 响应头、`lastId<=i64::MAX` 显式校验、统一错误码、`items/nextLastId/hasMore` 分页 envelope、`metadata` JSON 化、ledger 专项指标日志、`wallet_ledger(user_id,id DESC)` 索引与 handler 回归测试矩阵）。 | `chat/chat_server/src/handlers/payment.rs`、`chat/chat_server/src/models/payment/query_ops.rs`、`chat/chat_server/src/models/payment/types.rs`、`chat/chat_server/src/models/payment/tests.rs`、`chat/chat_server/src/openapi.rs`、`chat/migrations/20260403020000_wallet_ledger_user_id_id_desc_index.sql` | 当前开发计划（`GET /api/pay/wallet/ledger` 全链路优化） |

### B4. 工具链
| 模块 | 结论 | 代码证据 | 来源 |
|---|---|---|---|
| v2-d-stage-acceptance-gate-tooling | V2-D 阶段验收脚本与测试已落地。 | `scripts/release/v2d_stage_acceptance_gate.sh` | V2-D 阶段验收执行手册 |
| appstore-preflight-tooling | App Store preflight 自动检查脚本已落地。 | `scripts/release/appstore_preflight_check.sh` | App Store 发布 Runbook v2 |
| ai-judge-m7-stage-gate-tooling | AI 裁判 M7 阶段门禁脚本已落地。 | `scripts/release/ai_judge_m7_stage_acceptance_gate.sh` | AI裁判 M7 阶段验收报告 |
| replay-actions-perf-tooling | Replay Actions baseline/compare/suite/gate 工具链已落地。 | `chat/scripts/ai_judge_replay_actions_perf_regression_gate.sh` | AI裁判 ReplayActions 性能回归手册 |
| supply-chain-chaos-tooling | 供应链预发故障注入脚本与测试已落地。 | `scripts/release/supply_chain_preprod_chaos_drill.sh` | 供应链预发故障注入 Runbook |

### B5. 实时链路稳态化阶段成果
| 模块 | 结论 | 代码证据 | 来源 |
|---|---|---|---|
| debate-ws-reliability-refactor | 辩论实时已收敛到 WS；`syncRequired` 已切换为“先快照回补再重连”；辩论 SSE 入口已下线。 | `chatapp/src/views/DebateRoom.vue`（legacy，已删除）、`chat/notify_server/src/ws.rs` | 本地阶段实时链路重构计划（WS-only） |
| debate-ws-kafka-readiness-phase5-8 | Kafka readiness 已具备 notify 多实例信号聚合、DLQ count/age/progress/rate 四维门禁、ACK 防漂移与基线纠偏基础能力。 | `chat/chat_server/src/models/kafka_dlq.rs`、`chat/notify_server/src/ws.rs`、`chatapp/src/debate-room-utils.js`（legacy，已删除） | 本地阶段实时链路重构计划（先稳后 Kafka） |
| debate-ws-kafka-readiness-phase6-ack-drift-regression | phase6 ACK 漂移前置验收已脚本化并通过；future `lastAckSeq` clamp 后增量流持续下发具备回归保护。 | `chat/scripts/debate_ws_ack_drift_regression.sh`、`chat/notify_server/src/ws.rs` | 当前开发计划（Phase6 决策闭环版） |
| debate-ws-kafka-readiness-phase6-consumer-closed-loop | phase6 本地闭环验收完成：consumer 四事件业务校验+effect 审计、notify ingress 解析回归、DLQ replay rate 本地校准与 Go/No-Go 证据已产出。 | `chat/chat_server/src/event_bus.rs`、`chat/scripts/debate_kafka_phase6_closed_loop.sh` | 当前开发计划（Phase6 决策闭环版） |
| events-sse-hardening-phase1 | `GET /events` 全链路加固已完成：SSE replay、lagged syncRequired、连接配额与回收、结构化鉴权错误、QoS 关键事件优先、单主入口策略与观测计数。 | `chat/notify_server/src/sse.rs`、`chat/notify_server/src/middlewares.rs`、`chat/notify_server/src/lib.rs`、`chat/notify_server/src/notif.rs` | 当前开发计划（API 086 / EV-01~EV-10 方案A） |
| global-ws-hardening-phase1 | `GET /ws` 全链路加固已完成：`lastEventId` replay、`Lagged -> SyncRequired`、每用户连接配额、heartbeat+idle 收敛、debate 事件过滤、`Sec-WebSocket-Protocol` 鉴权、WS/Auth 分维指标、QoS 降级窗口。 | `chat/notify_server/src/ws.rs`、`chat/notify_server/src/middlewares.rs`、`chat/notify_server/src/lib.rs` | 当前开发计划（API 087 / GW-01~GW-10 方案A） |
| debate-room-ws-hardening-phase1 | `GET /ws/debate/:session_id` 全链路加固已完成：成员权限校验、回放截断显式 `replay_truncated`、连接配额治理、子协议鉴权迁移、debate_ws 专项指标、`syncRequired` reason 全量计数与 gap 感知节流、恢复契约增强（`mustSnapshot/reconnectAfterMs`）、ACK `localStorage` 持久化、replay key TTL/LRU 生命周期治理。 | `chat/notify_server/src/ws.rs`、`chat/notify_server/src/lib.rs`、`chat/notify_server/src/middlewares.rs`、`chatapp/src/debate-room-utils.ts`、`chatapp/src/views/DebateRoom.vue`（legacy，已删除；现行实现在 `frontend/packages/realtime-sdk` 与 `frontend/packages/app-shell/src/pages/DebateRoomPage.tsx`） | 当前开发计划（API 088 / DWS-01~DWS-10 方案A） |

### B6. 数据库-缓存一致性治理收口（来源：当前开发计划）
| 模块 | 结论 | 代码证据 | 来源 |
|---|---|---|---|
| B1-auth-db-authoritative-consistency | 鉴权链路已收敛为 DB 权威判定，phase 收口完成。 | `chat/chat_server/src/handlers/auth.rs` | 当前开发计划（数据库-缓存一致性治理） |
| B1-auth-cache-invalidation-retry-metrics | 缓存失效失败重试与指标闭环已完成。 | `chat/chat_server/src/handlers/auth.rs` | 当前开发计划（数据库-缓存一致性治理） |
| B1-auth-cache-invalidation-db-outbox | token_version 失效重试已升级为 DB 持久化 outbox 队列。 | `chat/chat_server/src/handlers/auth.rs` | 当前开发计划（数据库-缓存一致性治理） |
| B2-notify-replay-consistency 系列 | notify 回放一致性、syncRequired 指令化与节流已全部收口。 | `chat/notify_server/src/ws.rs` | 当前开发计划（数据库-缓存一致性治理） |
| B3-ai-judge-idempotency-outbox-consistency 系列 | AI Judge 幂等 Lua 原子判定、outbox 并发一致性 gate 与报告链路已收口。 | `ai_judge_service/app/trace_store.py`、`ai_judge_service/scripts/b3_consistency_gate.py` | 当前开发计划（数据库-缓存一致性治理） |
| B3 报告治理（目录/命名/保留/冲突） | 报告目录职责拆分、命名与保留策略、冲突重试、防覆盖能力已全部落地。 | `ai_judge_service/app/b3_consistency_gate.py` | 当前开发计划（数据库-缓存一致性治理） |
| B3 周期归档与维护自动化 | 周期归档脚本与本地维护入口已落地，可 dry-run / apply。 | `ai_judge_service/scripts/archive_consistency_reports.py`、`ai_judge_service/scripts/run_consistency_maintenance_local.sh` | 当前开发计划（数据库-缓存一致性治理） |
| B3 并发冲突压测与准入评估 | 并发冲突压测报告与 DB outbox 准入评估报告已产出，结论 Go。 | `ai_judge_service/scripts/b3_report_collision_stress.py`、`docs/consistency_reports/AI裁判B3-DB-outbox迁移准入评估-20260331.md` | 当前开发计划（数据库-缓存一致性治理） |

### B7. 前端重构与 TypeScript 迁移（来源：当前开发计划）
| 模块 | 结论 | 代码证据 | 来源 |
|---|---|---|---|
| frontend-react-ts-monorepo-bootstrap | 前端主干已完成 React+TypeScript monorepo 化，Web/Mac 双端入口与共享层可稳定运行。 | `frontend/package.json`、`frontend/apps/web/src/main.tsx`、`frontend/apps/desktop/src/main.tsx`、`frontend/packages/app-shell/src/AppRoot.tsx` | 前端开发计划（三端重构蓝图） |
| frontend-auth-home-lobby-room-judge-wallet-ops-closure | PRD 主流程在 Web+Mac 已形成可回归闭环（认证、Lobby、Room、Judge/Draw、Wallet、Ops）。 | `frontend/packages/app-shell/src/pages/LoginPage.tsx`、`frontend/packages/app-shell/src/pages/DebateLobbyPage.tsx`、`frontend/packages/app-shell/src/pages/DebateRoomPage.tsx`、`frontend/packages/app-shell/src/pages/WalletPage.tsx`、`frontend/packages/app-shell/src/pages/OpsConsolePage.tsx`、`frontend/tests/e2e/auth-smoke.spec.ts` | 前端开发计划（三端重构蓝图） |
| frontend-phase6-startup-script-cutover | 启停脚本、回归脚本与门禁路径已切换至 `frontend` 主线，不再依赖旧前端目录。 | `start.sh`、`stop.sh`、`frontend/playwright.config.ts`、`skills/post-module-test-guard/scripts/run_test_gate.sh` | 前端开发计划（三端重构蓝图） |
| frontend-phase6-delete-legacy-chatapp-tauri | 旧 Tauri 实现已完成净删除，桌面端统一到 `frontend/apps/desktop/src-tauri`。 | `frontend/apps/desktop/src-tauri/src/main.rs`、`frontend/apps/desktop/src-tauri/src/lib.rs` | 前端开发计划（三端重构蓝图） |
| frontend-phase6-delete-legacy-chatapp-root | 旧 Vue/JS 前端目录 `chatapp` 已整目录净删除，仓库前端主线已收敛为 React/TS。 | `frontend/apps/web/`、`frontend/apps/desktop/`、`frontend/packages/` | 前端开发计划（三端重构蓝图） |

### B8. Restful API 链路优化（来源：当前开发计划）
| 模块 | 结论 | 代码证据 | 来源 |
|---|---|---|---|
| debate-topics-list-hardening | `GET /api/debate/topics` 全链路优化已落地（`activeOnly=false` 权限收敛、OpenAPI 错误契约补齐、user/IP 双限频、cursor 分页、稳定排序、category 归一化、索引增强、专项指标日志、`items/hasMore/nextCursor/revision` 响应升级、回归测试补齐）。 | `chat/chat_server/src/handlers/debate.rs`、`chat/chat_server/src/models/debate.rs`、`chat/chat_server/src/models/debate/helpers.rs`、`chat/chat_server/src/models/debate/ops.rs`、`chat/chat_server/src/models/debate/tests/ops_and_listing.rs`、`chat/chat_server/src/openapi.rs`、`chat/migrations/20260404010000_debate_topics_list_hardening.sql` | 当前开发计划（`GET /api/debate/topics` DTOP-01~DTOP-10 方案A） |
| debate-ops-topics-create-hardening | `POST /api/debate/ops/topics` 全链路优化已落地（`Idempotency-Key` 回放、user/ip 双限频、创建审计、`contextSeed` 上限、category 白名单、`LOWER(BTRIM(title))+category` 重复防护、事务内并发锁、OpenAPI `201/400/401/403/404/409/429/500` 补齐、route+service 回归测试通过）。 | `chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/models/debate/ops.rs`、`chat/chat_server/src/models/debate/helpers.rs`、`chat/chat_server/src/application/request_guard.rs`、`chat/chat_server/src/models/debate/tests/ops_and_listing.rs`、`chat/migrations/20260407224500_ops_debate_topic_create_hardening.sql`、`chat/migrations/20260407231500_ops_debate_topic_category_dedupe_guard.sql` | 当前开发计划（`POST /api/debate/ops/topics` 全链路优化） |
| debate-ops-topics-update-hardening | `PUT /api/debate/ops/topics/{id}` 治理增强已落地（更新侧重复标题防护〔排除自身〕、可选 `expectedUpdatedAt` 乐观并发控制、`safe_u64_to_i64` 边界安全转换、更新审计 `action=update`、OpenAPI `401/403/422/500` 契约补齐、更新冲突/版本冲突/审计落库回归测试通过）。 | `chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/models/debate.rs`、`chat/chat_server/src/models/debate/ops.rs`、`chat/chat_server/src/models/debate/tests/ops_and_listing.rs`、`chat/migrations/20260408005000_ops_debate_topic_update_audit_action.sql` | 当前开发计划（`PUT /api/debate/ops/topics/{id}` 全链路优化） |
| debate-ops-sessions-create-hardening | `POST /api/debate/ops/sessions` 全链路优化已落地（OpenAPI 响应谱系补齐、user/ip 双限频、`Idempotency-Key` 幂等回放与 in-flight 冲突治理、事务化创建链路、`topicId` 安全转换、创建审计落库、`endAt` 未来时态约束、关键 model/route 回归测试补齐）。 | `chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/handlers/debate.rs`、`chat/chat_server/src/models/debate/ops.rs`、`chat/chat_server/src/models/debate/tests/ops_and_listing.rs`、`chat/migrations/20260408013000_ops_debate_session_create_hardening.sql` | 当前开发计划（`POST /api/debate/ops/sessions` 全链路优化） |
| debate-ops-sessions-update-hardening | `PUT /api/debate/ops/sessions/{id}` 全链路优化已落地（OpenAPI 错误谱系补齐、user/ip 双限频、`expectedUpdatedAt` 乐观并发控制、`session_id` 安全转换、`db_now` 时间基准收敛、`lock_timeout` 冲突语义收敛、`joinable` 口径与 list 对齐、更新审计 `action=update` 落库、关键 model/route 回归测试补齐）。 | `chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/handlers/debate.rs`、`chat/chat_server/src/models/debate.rs`、`chat/chat_server/src/models/debate/ops.rs`、`chat/chat_server/src/models/debate/tests/ops_and_listing.rs`、`chat/migrations/20260408024000_ops_debate_session_update_audit_action.sql` | 当前开发计划（`PUT /api/debate/ops/sessions/{id}` 全链路优化） |
| debate-sessions-list-hardening | `GET /api/debate/sessions` 全链路优化已落地（`joinable` 容量语义收敛、OpenAPI 错误契约补齐、user/IP 双限频、status 白名单、from/to 时间窗校验、cursor 分页 envelope、稳定排序、动态 SQL 条件构建、复合索引增强、专项指标日志、会话计数旁路校验修复脚本、回归测试补齐）。 | `chat/chat_server/src/handlers/debate_room.rs`、`chat/chat_server/src/models/debate.rs`、`chat/chat_server/src/models/debate/helpers.rs`、`chat/chat_server/src/models/debate/tests/ops_and_listing.rs`、`chat/chat_server/src/models/mod.rs`、`chat/chat_server/src/openapi.rs`、`chat/migrations/20260404020000_debate_sessions_list_hardening.sql`、`chat/scripts/debate_sessions_count_reconcile.sh` | 当前开发计划（`GET /api/debate/sessions` DSES-01~DSES-10 方案A） |
| debate-session-join-hardening | `POST /api/debate/sessions/{id}/join` 全链路优化已落地（join 专项 user/session + ip/session 限频、OpenAPI 补齐 `401/403/429/500`、稳定冲突错误码、`side` 归一化、`FOR UPDATE NOWAIT + lock_timeout` 快速失败、DB `NOW()` 时间基准、可选 `Idempotency-Key` 扩展、join 专项指标分桶、outbox 失败显式错误码、会话计数巡检脚本 `--audit-out` 审计增强与回归测试补齐）。 | `chat/chat_server/src/handlers/debate_room.rs`、`chat/chat_server/src/models/debate.rs`、`chat/chat_server/src/models/debate/helpers.rs`、`chat/chat_server/src/models/debate/tests/session_actions.rs`、`chat/scripts/debate_sessions_count_reconcile.sh` | 当前开发计划（`POST /api/debate/sessions/{id}/join` DJOIN-01~DJOIN-10 方案A） |
| debate-messages-list-hardening | `GET /api/debate/sessions/{id}/messages` 全链路优化已落地（响应升级为 `items/hasMore/nextCursor/revision`、事务读一致性 `REPEATABLE READ + READ ONLY`、稳定冲突码 `debate_messages_read_forbidden`、`u64->i64` 安全转换、可读判定顺序优化、user/IP 双限频、OpenAPI `200/400/401/403/404/409/429/500` 补齐、专项指标日志、model/route 回归测试补齐、压测基线脚本新增）。 | `chat/chat_server/src/handlers/debate_room.rs`、`chat/chat_server/src/models/debate.rs`、`chat/chat_server/src/models/debate/helpers.rs`、`chat/chat_server/src/models/debate/message_pin.rs`、`chat/chat_server/src/models/debate/tests/session_actions.rs`、`chat/chat_server/src/models/debate/tests/lifecycle.rs`、`chat/chat_server/src/openapi.rs`、`chat/scripts/debate_messages_list_perf_baseline.sh` | 当前开发计划（`GET /api/debate/sessions/{id}/messages` DMSG-01~DMSG-10 方案A） |
| debate-message-create-hardening | `POST /api/debate/sessions/{id}/messages` 全链路优化已落地（稳定错误码、OpenAPI `201/400/401/403/404/409/429/500` 补齐、字符数长度语义、可选 `Idempotency-Key` 幂等回放、user/session + ip/session 双限频与本地 fallback、`message_count` 原子计数 phase 判定、create 专项指标分桶、`hot_score` 增量刷盘、ingress mismatch readiness 阻断、outbox 失败稳定码 `debate_message_outbox_enqueue_failed`、回归测试补齐）。 | `chat/chat_server/src/handlers/debate_room.rs`、`chat/chat_server/src/models/debate/message_pin.rs`、`chat/chat_server/src/models/debate/helpers.rs`、`chat/chat_server/src/application/request_guard.rs`、`chat/chat_server/src/application/runtime_workers.rs`、`chat/chat_server/src/models/kafka_dlq.rs`、`chat/chat_server/src/models/debate/tests/session_actions.rs`、`chat/migrations/20260404130000_debate_message_create_hardening.sql` | 当前开发计划（`POST /api/debate/sessions/{id}/messages` DPOST-01~DPOST-10 方案A） |
| debate-pins-list-hardening | `GET /api/debate/sessions/{id}/pins` 全链路优化已落地（OpenAPI `200/400/401/403/404/409/429/500` 补齐、user/session + ip/session 双限频、pins 专项指标与结构化日志、响应升级为 `items/hasMore/nextCursor/revision`、稳定排序 `pinned_at DESC,id DESC`、`u64->i64` 安全转换、`REPEATABLE READ + READ ONLY` 读事务、`LEFT JOIN` 历史降级可见、pins 专属冲突码 `debate_pins_read_forbidden`、复合索引迁移与 handler/model 回归测试补齐）。 | `chat/chat_server/src/handlers/debate_room.rs`、`chat/chat_server/src/models/debate.rs`、`chat/chat_server/src/models/debate/message_pin.rs`、`chat/chat_server/src/models/debate/tests/session_actions.rs`、`chat/chat_server/src/models/mod.rs`、`chat/migrations/20260405001000_debate_pins_list_hardening.sql` | 当前开发计划（`GET /api/debate/sessions/{id}/pins` DPIN-01~DPIN-10 方案A） |
| debate-message-pin-hardening | `POST /api/debate/messages/{id}/pin` 全链路优化已落地（OpenAPI `200/400/401/403/404/409/429/500` 补齐、user/message + ip/message 双限频、pin 专项指标日志、`message_id` 安全转换、DB `NOW()` 时钟基准、message 行级 `FOR UPDATE` 原子化防双 active、幂等事务锁与唯一冲突收敛、稳定冲突错误码、handler 回归测试矩阵、kafka-only 下 `debate_message_pinned` trigger 静默治理）。 | `chat/chat_server/src/handlers/debate_room.rs`、`chat/chat_server/src/models/debate.rs`、`chat/chat_server/src/models/debate/message_pin.rs`、`chat/migrations/20260405002000_debate_message_pinned_pg_notify_governance.sql` | 当前开发计划（`POST /api/debate/messages/{id}/pin` MPIN-01~MPIN-10 方案A） |
| debate-judge-job-request-hardening | `POST /api/debate/sessions/{id}/judge/jobs` 全链路优化已落地（OpenAPI `202/400/401/403/404/409/429/500` 补齐、幂等键治理与双 header 支持、持久化幂等回放表、user/session + ip/session 双限频、稳定冲突错误码、final enqueue 失败 `degraded` 可观测、自动触发 requester 审计语义收敛、reason 稳定语义升级、handler/model 回归测试补齐）。 | `chat/chat_server/src/handlers/debate_judge.rs`、`chat/chat_server/src/models/judge/request_report.rs`、`chat/chat_server/src/models/judge/tests/request_judge_job.rs`、`chat/migrations/20260405004000_judge_request_idempotency.sql` | 当前开发计划（`POST /api/debate/sessions/{id}/judge/jobs` JJOB-01~JJOB-10 方案A） |
| debate-judge-report-read-hardening | `GET /api/debate/sessions/{id}/judge-report` 全链路优化已落地（OpenAPI 错误谱系补齐、死参数移除、参赛者+ops 权限收敛、user/session + ip/session 双限频、`REPEATABLE READ READ ONLY` 读一致性、`status/statusReason/progress` 状态机升级、`error_code/contract_failure_type` 结构化落库、概览与 `/judge-report/final` 详情拆分、索引增强、handler/model 回归测试补齐）。 | `chat/chat_server/src/handlers/debate_judge.rs`、`chat/chat_server/src/models/judge/request_report_query.rs`、`chat/chat_server/src/models/judge/types.rs`、`chat/chat_server/src/openapi.rs`、`chat/chat_server/src/lib.rs`、`chat/chat_server/src/models/judge/tests/request_judge_report_query.rs`、`chat/migrations/20260405012000_judge_report_query_hardening.sql` | 当前开发计划（`GET /api/debate/sessions/{id}/judge-report` JREP-01~JREP-10 方案A） |
| debate-ops-rbac-me-hardening | `GET /api/debate/ops/rbac/me` 全链路优化已落地（Owner 真源从硬编码迁移为 `platform_admin_owners`、`grant_platform_admin` 同步 owner 真源、OpenAPI 补齐 `200/401/403/500`、route 级 `200/401/403` 回归补齐、告警接收人 Owner 来源统一到真源表）。 | `chat/chat_server/src/models/rbac.rs`、`chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/handlers/debate.rs`、`chat/chat_server/src/models/ops_observability.rs`、`chat/migrations/20260408034000_ops_platform_owner_source.sql` | 当前开发计划（`GET /api/debate/ops/rbac/me` 全链路优化） |
| api058-rbac-roles-governance-phase-closure | `GET /api/debate/ops/rbac/roles` 已完成阶段性收口（OpenAPI 与 route 矩阵对齐、RBAC 三接口限流与结构化错误模型统一、`ops_rbac_audits` 审计落库、`rbacRevision` 落地、默认 `piiLevel=minimal` + 显式 `full`、前后端契约同步）。剩余治理项已转入 `todo.md` 持续跟踪。 | `chat/chat_server/src/handlers/debate.rs`、`chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/models/rbac.rs`、`chat/chat_server/src/models/mod.rs`、`chat/migrations/20260408042000_ops_rbac_audits.sql`、`chat/scripts/ops_rbac_audits_query.sh`、`chat/scripts/ops_rbac_audits_retention.sh`、`frontend/packages/ops-domain/src/index.ts`、`frontend/packages/app-shell/src/pages/OpsConsolePage.tsx` | 当前开发计划（API058 阶段性收口，2026-04-08 已整合归档） |

## C. 每项最小证据（汇总）
- 服务端 v3 派发与回放：`ai_judge_service/app/app_factory.py`、`chat/chat_server/src/handlers/debate_ops.rs`。
- 前端 Ops 回放消费：`frontend/packages/ops-domain/src/index.ts`、`frontend/packages/app-shell/src/pages/OpsConsolePage.tsx`。
- 认证治理：`chat/chat_server/src/handlers/auth.rs`、`chat/chat_server/src/middlewares/phone_bound.rs`。
- Mac 端登录联调：`chat/chat_server/src/lib.rs`、`chat/chat_server/src/models/rbac.rs`、`chat/notify_server/src/lib.rs`、`frontend/packages/app-shell/src/pages/LoginPage.tsx`。
- 发布门禁脚本：`scripts/release/appstore_preflight_check.sh`、`scripts/release/v2d_stage_acceptance_gate.sh`。
- 回归工具链：`chat/scripts/ai_judge_replay_actions_perf_regression_suite.sh`、`chat/scripts/ai_judge_replay_actions_perf_regression_gate.sh`。
- 实时 phase6 工具链：`chat/scripts/debate_ws_ack_drift_regression.sh`、`chat/scripts/debate_kafka_phase6_closed_loop.sh`。

## D. 合并来源映射（标题级）
| 原来源标题 | 合并后条目归属 |
|---|---|
| 产品开发计划（统一版） | 产品主链路、认证治理、发布门禁工具链 |
| AI裁判开发计划 v3（完整覆盖更新版） | AI裁判 M0-M8 已落地能力 |
| AI裁判 Replay Actions 性能回归手册（M8） | Replay Actions 性能工具链 |
| 登录方式改造后一致性收口方案（软合并登录） | 认证治理收口条目 |
| Workspace 彻底删除执行计划（最终版） | workspace-removal-closure |
| App Store 发布 Runbook v2 | appstore-preflight-tooling |
| V2-D 阶段验收执行手册（预发） | v2-d-stage-acceptance-gate-tooling |
| 供应链预发故障注入 Runbook v1 | supply-chain-chaos-tooling |
| AI裁判RAG轻量重建计划 | ai-judge-bm25-lexical-upgrade |
| 本地阶段实时链路重构计划（无兼容负担版） | 实时链路稳态化阶段成果 |
