# todo.md

## A. P0 发布阻塞

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| v2-m4-iap-storekit-production-and-wallet-closure | 仍缺真机交易闭环证据；本地默认配置与夹具仍保留 mock 形态。 | 形成“购买->验单->到账->置顶消费”四证合一归档（前端录屏、后端订单、钱包账本、Apple 交易记录），并固定生产配置样本。 | `bash scripts/release/appstore_preflight_check.sh --runtime-env production --chat-config <prod-chat.yml> --tauri-app-config <prod-app.yml> --ai-judge-env <prod-ai.env>`；归档可审计证据索引。 |
| v2-d-stage-acceptance-gate | 缺预发真实 L1/L2/L3/L4 + Soak + Spike 证据回填；当前仓库仅见样例与本机样本。 | 生成预发正式验收报告，包含阈值对比、失败归因、放行结论，并沉淀可复用 evidence 文件。 | `bash scripts/release/collect_v2d_regression_evidence.sh --output docs/loadtest/evidence/v2d_regression.env` + `bash scripts/release/v2d_stage_acceptance_gate.sh --regression-evidence docs/loadtest/evidence/v2d_regression.env --load-summary docs/loadtest/evidence/v2d_preprod_summary.env --report-out docs/loadtest/evidence/v2d_stage_acceptance_report.md` |
| v2-m10-release-readiness-and-appstore-runbook | 提审材料、上线演练、回滚演练证据未封板。 | 提审材料齐套并可复核；上线与回滚演练均有时间戳、操作日志与结果证据。 | 运行 preflight 并输出 PASS；完成发布 checklist 的证据索引审计。 |
| v2-m2-lobby-search-and-join-flow-environment-e2e | 联网环境 Playwright 实跑证据缺失。 | 在可联网环境完成 lobby E2E 实跑，沉淀 `playwright-report`、`test-results`、trace。 | `cd e2e && npm ci && npx playwright install --with-deps && npm run test:lobby`；将报告链接写入 evidence 索引。 |

## B. AI 裁判收口项

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| chat_server_v3_m7_contract_failure_fallback_and_consumer_alignment | 已有 unknown fallback 与消费提示实现，但缺统一验收定稿。 | 统一失败语义对照表并完成消费侧文档/展示一致性验收。 | 回归 `failure-stats` 与消费端展示链路；补齐验收记录。 |
| chat_server_v3_m8_replay_actions_ops_and_diagnostics_unify | 运维闭环能力已落地，缺统一收口验收。 | replay 定位、预览、执行、审计、查询链路形成单次验收报告。 | 通过 `/api/debate/ops/judge-replay/actions`、`/preview`、`/execute` 的联调脚本并归档结果。 |
| frontend_v3_m8_ops_replay_consumer_integration | 前端消费接入已完成，缺联调封板证据。 | 前后端联调通过并固定 UI 行为基线（过滤、分页、批量、错误提示）。 | 前端 E2E/手工回归证据 + 后端接口响应快照。 |
| ai-judge-ops-replay-actions-server-filter | 服务端过滤与跨分页一致性已实现，缺统一验收报告。 | 指定筛选组合下 count/list 一致性验收通过并可复现。 | 增补边界回归报告并归档脚本输出。 |
| chat_server_v3_m8_replay_actions_index_and_filter_boundary_tests | 已补索引与边界测试，缺阶段验收归档。 | 索引命中与边界回归结论写入阶段验收总报告。 | 执行对应测试集并将结果链接到验收索引。 |
| chat_server_v3_m8_replay_actions_explain_analyze_baseline | baseline/compare 工具已完成，缺真实 before/after 结果。 | 形成真实库 baseline+compare 报告并输出结论。 | `bash chat/scripts/ai_judge_replay_actions_explain_baseline.sh ...` 与 `..._compare.sh ...` |
| chat_server_v3_m8_replay_actions_pg_trgm_keyword_optimization | 迁移具备条件分支，缺真实库权限场景与收益证明。 | 在具备/不具备 pg_trgm 权限的环境均完成验证并沉淀结论。 | 执行迁移与 explain 对比；补充权限受限场景验证记录。 |
| chat_server_v3_m8_replay_actions_perf_regression_toolkit | suite+gate 已落地，尚未接入真实数据与验收流水线。 | 真实库多轮采样通过；`gate_result.json` 接入后端验收流水线。 | `bash chat/scripts/ai_judge_replay_actions_perf_regression_suite.sh ...` + `bash chat/scripts/ai_judge_replay_actions_perf_regression_gate.sh --suite-output-dir <dir> --output-dir <dir>/gate` |
| M9-final-acceptance-integration | 依赖 M7/M8 全量收口后才可执行。 | 输出最终验收整合文档（不含灰度/回滚编排），完成 Go/No-Go 输入物封板。 | 复核 M7/M8 收口项全部满足后生成 M9 报告。 |
| ai_judge_service_token_budget | token budget 与 tokenClipSummary 功能已在工作区落地，但缺线上抽样对账与阈值化治理。 | 完成线上 usage 抽样对账，建立预算告警阈值并输出成本/时延曲线结论。 | 运行单测 `ai_judge_service/tests/test_token_budget.py` + 生产样本对账脚本/报表归档。 |

## C. 完成定义与证据规范
- 每个条目必须同时满足：功能可复现、证据可追溯、结论可复核。
- 证据最少包含：执行命令、执行时间、输入配置版本、结果文件路径。
- 对外部环境依赖项（预发/真机/提审）必须保留原始报告与摘要结论两份材料。

## D. 执行顺序（P0 -> P1）与依赖
1. P0-1：`v2-d-stage-acceptance-gate`（给发布链路提供基础阈值证据）。
2. P0-2：`v2-m4-iap-storekit-production-and-wallet-closure`（支付与置顶闭环证据）。
3. P0-3：`v2-m10-release-readiness-and-appstore-runbook`（提审材料与演练封板）。
4. P0-4：`v2-m2-lobby-search-and-join-flow-environment-e2e`（补全环境侧 E2E 归档）。
5. P1-1：AI 裁判 M7/M8 收口项（failure 语义、replay 联调、真实库性能回归）。
6. P1-2：`M9-final-acceptance-integration`（依赖前述 AI 收口项完成）。
7. P1-3：`ai_judge_service_token_budget` 线上化治理（与 M9 并行可行，但不阻塞 P0 发布链路）。

## E. 合并来源映射（标题级）
| 原来源标题 | 合并后条目归属 |
|---|---|
| 产品开发计划（统一版） | P0 发布阻塞四项 |
| AI裁判开发计划 v3（完整覆盖更新版） | M7/M8/M9 收口项 |
| AI裁判 Replay Actions 性能回归手册（M8） | ReplayActions 真实库验收与流水线接入 |
| App Store 发布 Runbook v2 | 发布预检与提审封板项 |
| V2-D 阶段验收执行手册（预发） | V2-D 预发证据收口项 |
| v2-m2 phase3 UI 端到端回归验收 | Lobby 环境 E2E 证据收口项 |

### 已完成/未完成矩阵（实时链路）

| 模块 | 优先级 | 状态 | 说明 |
|---|---|---|---|
| debate-ws-reliability-refactor | P0 | 已完成 | 辩论实时已收敛到 WS；HTTP 命令链路保持不变；SSE 辩论事件已下线。 |
| debate-ws-kafka-readiness-phase6-ack-drift-regression | P0 | 已完成 | ACK 漂移前置验收脚本与 notify future `lastAckSeq` clamp 回归已落地并通过门禁。 |
| debate-ws-kafka-readiness-phase6-consumer-closed-loop | P0 | 已完成 | Kafka consumer 四事件闭环、notify ingress 回归、DLQ replay rate 本地校准与 Go/No-Go 证据已完成。 |
| debate-ws-kafka-only-switch-drill | P0 | 待执行 | phase6 后续动作：debate 路径 kafka-only 演练与 readiness 前后快照留证。 |
| debate-pg-listener-channel-migration-plan | P1 | 待执行 | 需补齐 PG listener 剩余通道迁移清单（chat/ops 分批）与优先级。 |
| debate-dlq-replay-rate-recalibration-real-samples | P1 | 待执行（等待样本） | 当前本地样本不足，`min_replay_actions_per_minute` 维持 0.0，待真实 replay 样本后重跑校准。 |

### 下一开发模块（已锁定）

| 模块 | 目标 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-ws-kafka-only-switch-drill | 在本地完成 debate 路径 kafka-only 切换演练并形成 readiness 证据闭环。 | 演练前后 readiness 快照、关键事件链路验证、异常降级路径均可复现并归档。 | `bash chat/scripts/debate_kafka_phase6_closed_loop.sh`（基线）+ kafka-only 演练脚本/命令 + `/ops/kafka/readiness` 快照对比。 |

### 下一开发模块建议（滚动）

1. 执行 debate 路径 kafka-only 切换演练并记录 readiness 前后快照
2. 补齐 PG listener 剩余通道迁移清单与优先级
3. 在出现真实 DLQ replay 样本后重跑阈值校准并更新 Go/No-Go 结论

## F. 当前开发计划收口后续（数据库-缓存一致性）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| b3-outbox-switch-implementation-plan | 准入评估已完成，但 DB outbox 切换实施计划尚未形成。 | 输出字段映射、写入替换点、回放校验、回滚策略四部分实施文档。 | 在 `docs/consistency_reports/` 产出实施计划文档并完成评审。 |
| b3-redis-collision-stress-high-scale-non-sandbox | 当前会话受沙箱权限限制，未形成 redis 多 worker 放大量化样本。 | 在非受限环境产出 redis 并发冲突压测（建议 workers>=32）并形成报告。 | `cd ai_judge_service && ../scripts/py scripts/b3_report_collision_stress.py --workers 32 --mode redis` |
| b3-maintenance-weekly-adoption | 维护脚本已具备，但尚未固定周期开启与阈值复盘。 | 将维护脚本纳入每周例行流程，连续一周保留执行日志与结论。 | `bash ai_judge_service/scripts/run_consistency_maintenance_local.sh --mode dry-run` 并归档日志到 `docs/consistency_reports/` |
### 模块完成同步历史

- 2026-03-29：推进 `debate-ws-reliability-refactor`；完成辩论实时链路稳态化：WS ACK + syncRequired 恢复指令 + 前端快照回补重连 + notify listener 自恢复循环。
- 2026-03-29：推进 `debate-ws-kafka-readiness`；完成 WS 稳态后 Kafka 前置整理：新增 DebateMessageCreated outbox、consumer 非空分发校验、ops/kafka/readiness 门禁与 outbox 指标输出。
- 2026-03-29：推进 `debate-ws-kafka-readiness`；完成 phase3：notify_server 支持 Kafka consumer ingress、可配置 kafka-only 模式、PG/Kafka 统一分发主干，并补齐 pinned 事件 pin_id 契约。
- 2026-03-29：推进 `debate-ws-kafka-readiness`；完成 phase4：chat_server Kafka consumer 四类事件分支已补齐事务内一致性校验与幂等副作用审计（kafka_consume_worker_effects），并新增重复消费验证测试。
- 2026-03-30：推进 `debate-ws-kafka-readiness`；phase4 门禁收敛：consumer runtime metrics 与 pending DLQ 已接入 /ops/kafka/readiness，切换判定从静态配置升级为运行时证据门禁。
- 2026-03-30：推进 `debate-ws-kafka-readiness`；phase4 指标门禁补测完成：新增 readiness blockers 单测覆盖 consumer commit/process/drop 与 pending-dlq，门禁规则具备持续回归保护。
- 2026-03-30：推进 `debate-ws-kafka-readiness`；phase5 信号化门禁：notify_server 已上报 Kafka 消费运行信号，chat_server readiness 基于跨服务信号做 kafka-only/commit-heartbeat 阻塞判定。
- 2026-03-30：推进 `debate-ws-kafka-readiness`；phase5-2 低流量误报收敛：notify runtime signal 新增 receive 心跳与周期活性刷新，readiness 仅在 receive recent + commit stale 时阻塞。
- 2026-03-30：推进 `debate-ws-kafka-readiness`；phase5-3 完成：readiness升级为多实例notify信号聚合判定；notify runtime signal改为实例级键；新增多实例放行回归测试并通过全量门禁
- 2026-03-30：推进 `debate-ws-kafka-readiness`；phase5-4 完成：notify runtime signal 增加陈旧实例TTL清理与实例键命名单测，readiness多实例聚合链路补齐生命周期治理
- 2026-03-30：推进 `debate-ws-kafka-readiness`；phase5-5 完成：DLQ replay执行进度并入readiness判定与观测字段，新增‘pending但回放停滞’阻塞语义与回归测试
- 2026-03-30：推进 `debate-ws-kafka-readiness`；phase5-6 完成：pending DLQ门禁改为可配置阈值（count/age）阻塞，新增观测字段与阈值评估单测，支持渐进式Kafka切换策略
- 2026-03-30：推进 `debate-ws-kafka-readiness`；phase5-7：新增 pending DLQ 回放速率门控（窗口期 actions/min）与 readiness 可观测字段；默认阈值关闭，支持后续渐进开启。
- 2026-03-30：推进 `debate-ws-kafka-readiness`；phase5-8：完成 ACK 稳态化修复（服务端 clamp lastAckSeq + 拒绝未来 ACK；客户端 welcome/syncRequired 基线强制回退）并与 DLQ replay rate readiness 门禁联动收口。
- 2026-03-31：推进 `debate-ws-kafka-readiness-phase6-ack-drift-regression`；完成 ACK 漂移前置验收脚本与 notify clamp 回归测试，形成一键回归入口。
- 2026-03-31：推进 `debate-ws-kafka-readiness-phase6-consumer-closed-loop`；完成 Kafka consumer 四事件闭环、notify ingress 回归、DLQ replay rate 本地校准与 phase6 本地 Go/No-Go 证据归档。

- 2026-04-01：推进 `frontend-auth-phone-bind-unblock`；修复 Mac 客户端手机号绑定卡住：登录态判定改为 token 驱动，绑定后用户态强制归一，消除 /bind-phone 循环拦截。
- 2026-04-01：推进 `auth-cors-credentials-fix`；修复登录 CORS 阻断：chat/notify 改为本地来源白名单 + credentials，并显式声明 allow_headers 白名单，恢复 Mac 客户端超级账号登录。
## G. 前端重构收口待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| frontend-release-candidate-acceptance-web-mac | React/TS 主线与 Phase6 净删除已完成，但上线前 RC（Web+Mac）验收清单尚未封板。 | 完成 1280/1440/1728 三档分辨率走查、键盘可达性复核、发布候选清单（环境变量/构建命令/回归命令/回滚步骤）并归档到 `docs/dev_plan`。 | `cd frontend && pnpm typecheck && pnpm lint && pnpm test && pnpm e2e:smoke:web && pnpm e2e:smoke:desktop && pnpm e2e:auth-error:web && pnpm e2e:auth-error:desktop`；人工走查记录归档。 |
| frontend-prelaunch-performance-baseline | 前端主流程功能稳定，但缺少上线前性能基线（首屏、路由切换、Room 长列表）证据。 | 输出 Web/Mac 端性能基线报告（关键页面 `p95/p99`、首屏可交互时间、关键交互耗时）并给出优化建议。 | `cd frontend && pnpm --filter @echoisle/web build` + 浏览器 Performance 录制 + 桌面端启动与页面切换基线采样，报告归档至 `docs/loadtest/evidence/`。 |
| frontend-observability-and-fault-drill | 前端可观测与异常演练已有基础，但值班视角的前端故障演练未形成固定证据。 | 完成一次“后端 429/500 + 网络抖动 + 票据失效”前端演练，形成错误提示、重试策略、降级行为一致性记录。 | 使用现有 Playwright `@auth-error` 套件 + 手工故障注入回归，归档截图/trace/结论到 `docs/consistency_reports/`。 |

## H. 认证链路后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| auth-signup-phone-password-policy | 本轮 `signup_phone_v2` 优化已完成，但密码策略按决策暂未实施。 | 增加密码复杂度/弱口令校验，并补齐成功/失败/边界测试。 | `cd chat && cargo test -p chat-server handlers::auth::tests:: -- --nocapture` + 密码策略专项用例通过。 |
| auth-signup-phone-audit-outbox | 审计已改为 best-effort，但未实现异步补偿链路。 | 设计并落地审计 outbox（或等效异步补偿），主链路可用性与审计完整性同时满足。 | 断库/降级演练下注册成功率与审计补偿结果对账通过。 |
| auth-signup-phone-hotspot-load-observability | 功能修复已完成，缺高并发热点手机号压测与指标基线。 | 产出热点手机号并发压测报告，明确 `success rate`、`fail reason`、`latency p95/p99` 基线。 | 执行压测脚本并归档到 `docs/loadtest/evidence`，报告含阈值与结论。 |

## 8. 优化执行矩阵（覆盖更新）

- 同步时间: 2026-04-01 04:51:38
- 本次优化模块: `frontend-mac-shell-polish`
- 本次回写阶段: `FE-MAC-P1`
- 阶段完成度: 1/1

### 8.1 阶段状态
- [x] 阶段 FE-MAC-P1 | 状态: 已完成 | 目标: 待补充标题

### 8.2 判定口径
- 已完成：阶段关键交付项已经落地并有测试/验证证据。
- 进行中：已开始改动但仍有关键交付项未闭环。
- 阻塞：存在外部依赖或关键风险暂未解除。
- 未开始：阶段尚未进入实施。

### 8.3 覆盖策略
- 本节每次优化模块完成后覆盖更新，避免旧状态残留。
- 当前章节重写白名单：`8,9`。

## 9. 下一步优化建议（覆盖更新）

下一步建议：全部阶段已完成，进入上线前稳定性与性能优化。

执行动作：
1. 进入上线前收口：性能压测、故障演练、可观测性补齐。
2. 将本计划升级为第二版，按线上问题与业务反馈定义新阶段。

---

## 10. 优化回写记录（自动）

### 2026-04-01 04:51:38 | frontend-mac-shell-polish
- 阶段: FE-MAC-P1
- 完成状态: 已完成
- 本次摘要: 完成 mac 端第一轮视觉重构：统一设计 token，重构 Sidebar/Home/Lobby/Login，补充首页/登录 e2e 回归。
- 调整原因: 无
- 下一步建议: 全部阶段已完成，进入上线前稳定性与性能优化。

## I. auth-refresh 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| auth-refresh-outbox-fault-injection-evidence | refresh outbox 代码已落地，但“Redis 真故障->恢复”压测与补偿闭环证据尚未归档。 | 形成可复核的故障注入报告：包含故障窗口、outbox 堆积/清空曲线、最终一致性对账结论。 | 本地联调执行 refresh + Redis 故障注入脚本，归档命令、时间戳、指标截图与报告到 `docs/consistency_reports/`。 |
| auth-refresh-grace-window-baseline | 并发双刷宽限策略已实现，缺少 grace 窗口外 replay 的并发基线与参数建议。 | 输出并发压测基线（误判率、升级率、p95/p99），并给出 grace 秒数调优建议。 | 并发压测同一 refresh cookie 场景，分别统计窗口内/窗口外行为并归档报告。 |
| auth-refresh-frontend-error-policy-alignment | 后端新增 refresh 语义错误码已上线，前端恢复策略矩阵尚未联调封板。 | 前后端对 `auth_refresh_conflict_retry/auth_refresh_expired/auth_refresh_replayed/auth_refresh_degraded_retryable` 行为一致并有联调记录。 | 前端联调脚本 + 手工回归，归档错误码->动作映射与结果快照。 |

## J. auth-logout-all 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| auth-logout-all-redis-fault-injection-evidence | `logout-all` 代码已具备 outbox + best-effort 双轨收敛，但真实 Redis 故障注入证据未归档。 | 形成可复核的故障注入报告：覆盖断连窗口、outbox 堆积/清空曲线、最终一致性对账结论。 | 本地联调执行 `logout-all + Redis 故障注入`，归档命令、时间戳、指标截图与报告到 `docs/consistency_reports/`。 |
| auth-logout-all-multi-client-contract-alignment | Web 已消费新字段，非 Web 客户端对 `serverRevocation/degraded/warnings` 语义尚未联调封板。 | 跨端消费策略一致，提示文案与重试策略统一，并形成联调记录。 | 客户端联调脚本 + 手工回归，归档“字段->动作映射”与结果快照。 |
| auth-logout-all-observability-dashboard-baseline | 指标埋点已落地，但 dashboard 与告警阈值未形成正式基线。 | 建立 `logout_all_*` 指标看板与告警阈值，完成值班演练与验收记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班演练复盘归档。 |

## K. auth-session-revoke 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| auth-session-revoke-dlq-replay-ops-surface | 已有 `replay_auth_refresh_consistency_outbox_dlq_once` 内部能力，但缺少受控运维入口与操作审计闭环。 | 提供受控 replay 运维入口（API/脚本二选一）与审计记录，支持按 source/scope/key 条件重放。 | 通过本地联调验证“筛选 -> replay -> 审计追踪”完整闭环，并归档执行记录。 |
| auth-session-revoke-redis-fault-injection-evidence | 代码与测试已覆盖降级/补偿路径，但真实 Redis 故障注入证据尚未归档。 | 形成可复核故障注入报告：故障窗口、outbox 堆积/清空曲线、最终一致性对账结论。 | 本地执行 revoke + Redis 故障注入，归档命令、时间戳、指标截图与报告到 `docs/consistency_reports/`。 |
| auth-session-revoke-multi-client-contract-alignment | 后端已返回 `revoked/affectedCount/result`，跨端消费策略与文案尚未统一封板。 | 完成多客户端对新响应字段的提示文案、重试/刷新策略联调，并沉淀映射表。 | 客户端联调脚本 + 手工回归，归档“字段->动作映射”与结果快照。 |

## L. auth-sms-send 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| auth-sms-send-multi-client-contract-alignment | 后端已新增 `providerMessageId/providerAcceptedAt` 与细分错误语义，跨端消费策略尚未联调封板。 | Web/Mac/移动端统一“字段/错误码 -> 提示文案 -> 重试动作”映射并形成联调记录。 | 客户端联调脚本 + 手工回归，归档契约映射与结果快照。 |
| auth-sms-send-redis-fault-injection-evidence | 发送链路降级策略已落地，但 Redis 故障注入与阈值压测证据尚未归档。 | 形成可复核故障注入报告：故障窗口、成功率、`reason` 分桶、p95/p99 与阈值建议。 | 本地执行 `sms/send + Redis 故障注入`，归档命令、时间戳、指标截图与报告到 `docs/consistency_reports/`。 |
| auth-sms-send-callback-anti-replay | callback 目前仅共享密钥校验，尚未加入签名与时间窗防重放机制。 | 落地签名+时间窗+nonce 校验，并补齐成功/失败/重放攻击回归测试。 | `cd chat && cargo test -p chat-server handlers::auth::tests:: -- --nocapture` + callback 防重放专项用例通过。 |
| auth-sms-send-provider-routing-and-circuit-breaker | 已具备 provider 接口与 callback 闭环，但多 provider 路由与熔断未实现。 | 完成 provider 路由、健康探测、熔断/回退策略与监控告警基线。 | provider 故障演练与切换验证通过，归档运行日志与指标快照。 |

## M. auth-sessions-list 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| auth-sessions-list-multi-client-contract-alignment | 后端已新增 `status/isCurrent/sessionRevision/hasMore/nextCursor` 与 `429` 语义，跨端消费策略尚未联调封板。 | Web/Mac/移动端统一“字段/错误码 -> 提示文案 -> 重试动作 -> 收敛策略”映射并形成联调记录。 | 客户端联调脚本 + 手工回归，归档契约映射与结果快照。 |
| auth-sessions-list-load-baseline-and-rate-limit-tuning | 分页与双限频能力已落地，但缺少会话规模压测与阈值调优证据。 | 形成可复核压测报告：不同会话规模下 `p95/p99`、返回条目分布、限频命中率与阈值建议。 | 执行列表接口专项压测并归档命令、时间戳、结果报告到 `docs/loadtest/evidence/`。 |
| auth-sessions-list-observability-dashboard-baseline | 指标与结构化日志已落地，但 dashboard 与告警阈值未固化。 | 建立 `auth_sessions_list_*` 与 retention worker 指标看板，完成告警阈值与值班演练记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |

## N. pay-iap-products-list 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| pay-iap-products-multi-client-contract-alignment | 后端已升级 `GET /api/pay/iap/products` 响应契约为 `items/revision/emptyReason`，跨端消费策略尚未联调封板。 | Web/Mac/移动端统一“字段/错误码 -> 提示文案 -> 重试动作”映射并形成联调记录。 | 客户端联调脚本 + 手工回归，归档契约映射与结果快照。 |
| pay-iap-products-load-baseline-and-observability-dashboard | 读限频、缓存与指标已落地，但压测基线与告警阈值未形成正式报告。 | 产出 `p95/p99`、缓存命中率、限频命中率基线报告，建立 `iap_products_list_*` 看板与阈值。 | 执行列表接口专项压测并归档到 `docs/loadtest/evidence/`，导出看板配置与告警演练记录。 |

## O. pay-iap-order-probe 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| pay-iap-order-probe-multi-client-contract-alignment | 后端已升级 `GET /api/pay/iap/orders/by-transaction` 契约（`probeStatus/nextRetryAfterMs` + 稳定错误码），跨端消费策略尚未联调封板。 | Web/Mac/移动端统一“字段/错误码 -> 提示文案 -> 重试动作”映射并形成联调记录。 | 客户端联调脚本 + 手工回归，归档契约映射与结果快照。 |
| pay-iap-order-probe-rate-limit-and-retry-baseline | 用户/IP 双限频与重试建议字段已落地，但阈值与退避策略缺少真实样本基线。 | 形成可复核报告：`p95/p99`、限频命中率、`not_found/pending_credit` 占比、`nextRetryAfterMs` 调参建议。 | 执行 probe 接口专项压测并归档命令、时间戳、结果报告到 `docs/loadtest/evidence/`。 |
| pay-iap-order-probe-observability-dashboard-baseline | 指标与结构化日志已落地，但 dashboard 与告警阈值未固化。 | 建立 `iap_order_probe_*` 看板与告警阈值，完成一次值班演练与复盘记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |

## P. pay-iap-verify 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| pay-iap-verify-multi-client-contract-alignment | 后端已升级 `POST /api/pay/iap/verify` 契约（稳定错误码 + `retryAfterMs` + 冲突结果直返），跨端消费策略尚未联调封板。 | Web/Mac/移动端统一“错误码/字段 -> 提示文案 -> 重试动作”映射并形成联调记录。 | 客户端联调脚本 + 手工回归，归档契约映射与结果快照。 |
| pay-iap-verify-rate-limit-and-retry-baseline | 三层限流与可重试语义已落地，但阈值与退避策略缺真实样本基线。 | 形成可复核报告：`p95/p99`、限频命中率、冲突复用命中率、`retryAfterMs` 调参建议。 | 执行 verify 接口专项压测并归档命令、时间戳、结果报告到 `docs/loadtest/evidence/`。 |
| pay-iap-verify-observability-dashboard-baseline | verify 专项指标与日志已落地，但 dashboard 与告警阈值未固化。 | 建立 `iap_verify_*` 看板与告警阈值，完成一次值班演练与复盘记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |

## Q. pay-wallet 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| pay-wallet-observability-dashboard-baseline | `GET /api/pay/wallet` 指标与结构化日志已落地，但 dashboard 与告警阈值尚未固化。 | 建立 `wallet_balance_*` 指标看板与告警阈值，完成一次值班演练与复盘记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |
| pay-wallet-reconcile-parameter-tuning | 钱包余额对账 worker 已上线（间隔/采样可配置），但缺少真实样本下的参数调优基线。 | 形成可复核报告：不同间隔与采样量下的扫描开销、mismatch 检出率、告警噪声建议。 | 执行对账 worker 参数压测与样本回放，归档命令、时间戳与报告到 `docs/consistency_reports/`。 |
| pay-wallet-reconcile-ops-query-surface | 对账差异目前已审计落库，但缺少 ops 查询/导出能力，排障仍需直查数据库。 | 提供受控查询面（API 或脚本）支持按用户/时间窗口检索 mismatch 审计记录。 | 本地联调验证“查询 -> 过滤 -> 导出”闭环，并归档执行记录。 |

## R. pay-wallet-ledger 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| pay-wallet-ledger-observability-dashboard-baseline | `GET /api/pay/wallet/ledger` 指标与结构化日志已落地，但 dashboard 与告警阈值尚未固化。 | 建立 `pay_wallet_ledger_*` 指标看板与告警阈值，完成一次值班演练与复盘记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |
| pay-wallet-ledger-index-performance-baseline | `wallet_ledger(user_id,id DESC)` 索引已新增，但缺少真实数据规模下 explain 与延迟基线报告。 | 形成可复核性能报告：索引命中、`p95/p99`、不同 `limit/lastId` 组合表现与调优建议。 | 执行 explain + 压测，归档命令、时间戳与报告到 `docs/loadtest/evidence/`。 |
| pay-wallet-ledger-multi-client-contract-alignment | 后端已切换分页 envelope 与 metadata JSON，跨端消费策略尚未联调封板。 | Web/Mac/移动端统一 `items/nextLastId/hasMore` 与错误码映射策略，形成联调记录。 | 客户端联调脚本 + 手工回归，归档契约映射与结果快照。 |

## S. events-sse-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| events-sse-replay-cross-process-persistence | 当前 replay 为内存窗口，实例重启或多实例下无法跨进程续传。 | 形成跨进程可用的 replay 持久化方案并落地（或明确范围内不做并固化产品策略）。 | 断线重连与服务重启场景联调，验证 replay 命中/缺口语义与回补路径。 |
| events-sse-observability-dashboard-baseline | SSE 指标计数已落地，但看板与告警阈值尚未封板。 | 建立 `/events` 专项 dashboard 与告警阈值，完成一次值班演练与复盘。 | 导出看板配置 + 告警演练记录 + 复盘文档归档。 |
| events-sse-sync-required-client-alignment | 服务端已输出 `SyncRequired`，跨端自动快照补拉策略尚未统一封板。 | Web/Mac/移动端统一 `SyncRequired -> 快照补拉 -> 继续监听` 行为矩阵并联调通过。 | 客户端联调脚本 + 手工回归，归档“事件->动作映射”与结果快照。 |
| events-sse-qos-phase2-priority-queue | QoS 当前为“关键优先保留”第一阶段，尚未形成硬优先级调度。 | 完成多级优先队列或等效策略，实现高压下关键事件更稳定送达。 | 压测对比改造前后关键事件送达率与延迟分位，输出报告。 |

## T. global-ws-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| global-ws-replay-cross-process-persistence | `GET /ws` 当前 replay 仍为内存窗口，实例重启或多实例下无法跨进程续传。 | 形成跨进程可用的 replay 持久化方案并落地（或明确范围内不做并固化产品策略）。 | 断线重连与服务重启场景联调，验证 replay 命中/缺口语义与回补路径。 |
| global-ws-observability-dashboard-baseline | WS 指标计数已落地，但看板与告警阈值尚未封板。 | 建立 `/ws` 专项 dashboard 与告警阈值，完成一次值班演练与复盘。 | 导出看板配置 + 告警演练记录 + 复盘文档归档。 |
| global-ws-sync-required-and-stream-idle-client-alignment | 服务端已输出 `SyncRequired/StreamIdle`，跨端自动补拉与状态展示策略尚未统一封板。 | Web/Mac/移动端统一 `SyncRequired/StreamIdle -> 客户端动作` 行为矩阵并联调通过。 | 客户端联调脚本 + 手工回归，归档“事件->动作映射”与结果快照。 |
| global-ws-qos-phase2-priority-queue | QoS 当前为“降级窗口+关键优先保留”第一阶段，尚未形成硬优先级调度。 | 完成多级优先队列或等效策略，实现高压下关键事件更稳定送达。 | 压测对比改造前后关键事件送达率与延迟分位，输出报告。 |

## U. debate-room-ws-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-room-ws-replay-cross-process-fallback | 房间 WS 已支持 DB+内存回放，但 DB 不可用时的内存 fallback 仍为实例本地态，跨实例连续性不足。 | 明确并落地跨进程 replay 持久化方案，或正式固化“DB+快照兜底”产品约束并补齐验证文档。 | 多实例/重启联调：验证 fallback 场景下的恢复语义与 `syncRequired` 一致性，归档报告到 `docs/consistency_reports/`。 |
| debate-room-ws-observability-dashboard-baseline | debate_ws 专项指标已落地，但看板、阈值与值班演练尚未封板。 | 建立 `debate_ws_*` 与 `sync_required_reason_*` 看板与告警阈值，形成一次值班演练记录。 | 导出看板配置 + 告警演练记录 + 复盘文档归档。 |
| debate-room-ws-multi-client-recovery-alignment | Web 端已消费 `mustSnapshot/reconnectAfterMs`，跨端恢复动作矩阵尚未联调封板。 | Web/Mac/移动端统一“reason -> 快照/重连/提示”策略并完成联调验收。 | 客户端联调脚本 + 手工回归，归档“reason->动作映射”与结果快照。 |

## V0. debate-judge-report 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-judge-report-performance-baseline | API027 代码级优化已完成，但缺少预发/生产真实数据规模下 `EXPLAIN + p95/p99` 基线归档。 | 形成可复核性能报告：索引命中、`p95/p99`、不同场次规模下查询延迟与调优建议。 | 执行 explain 与压测并归档到 `docs/loadtest/evidence/`。 |
| debate-judge-report-observability-dashboard-baseline | 读链路指标已落地，但看板与告警阈值未封板。 | 建立 `judge_report_read_*` 指标看板与告警阈值，完成一次值班演练与复盘。 | 导出看板配置 + 告警演练记录 + 复盘文档归档。 |
| debate-judge-report-multi-client-contract-alignment | 后端契约已升级为 `statusReason/progress/finalReportSummary` + `/judge-report/final`，跨端消费策略尚未统一封板。 | Web/Mac/移动端统一“字段/错误码 -> 提示文案 -> 重试动作”映射并完成联调验收。 | 客户端联调脚本 + 手工回归，归档契约映射与结果快照。 |

## V. api-tickets-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api-tickets-sse-query-token-risk-phase2 | `GET /events` 仍使用 query token，虽已做会话一致性校验与日志脱敏，但 URL 暴露面未彻底消除。 | 明确并落地 SSE query token Phase2 治理方案（例如更严格代理脱敏、短链路票据策略或替代鉴权通道），并形成风险复评结论。 | 进行代理/网关日志抽样检查 + 安全回归演练，归档报告到 `docs/consistency_reports/`。 |
| api-tickets-observability-dashboard-baseline | tickets 计数与结构化日志已落地，但专项 dashboard 与告警阈值尚未封板。 | 建立 `tickets_issue_*` 指标看板与告警阈值，完成一次值班演练与复盘记录。 | 导出看板配置 + 告警演练记录 + 复盘文档归档。 |
| api-tickets-config-centralization | ticket TTL 当前通过环境变量读取，尚未统一纳入 `AppConfig` YAML 配置体系。 | 完成 `file/notify` TTL 的配置中心化（YAML+默认值+边界校验）并保持现有行为兼容。 | `cargo test -p chat-server handlers::ticket::tests:: -- --nocapture` + 配置加载用例通过并归档。 |

## W. debate-topics-list-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-topics-list-client-contract-alignment | `GET /api/debate/topics` 已从裸数组升级为 envelope，跨端消费策略尚未联调封板。 | Web/Mac/移动端统一 `items/hasMore/nextCursor/revision` 解析与 UI 行为，并形成联调记录。 | 客户端联调脚本 + 手工回归，归档“字段->动作映射”与结果快照。 |
| debate-topics-list-observability-dashboard-baseline | `debate_topics_list_*` 指标与结构化日志已落地，但 dashboard 与告警阈值尚未固化。 | 建立 topics 列表专项看板与告警阈值，完成一次值班演练与复盘记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |
| debate-topics-list-revision-semantics-upgrade | 当前 `revision=MAX(updated_at)` 为轻量语义，不是强一致单调版本号。 | 若后续存在强一致增量同步需求，完成 revision 版本序列化方案设计与落地。 | 设计评审通过 + 回归测试验证“并发更新下 revision 单调性”并归档。 |

## X. debate-sessions-list-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-sessions-list-rate-limit-tuning-baseline | `GET /api/debate/sessions` user/IP 双限频已落地，但阈值仍为工程初值，缺真实流量回标。 | 形成可复核报告：不同阈值下命中率、误杀率、`p95/p99` 与建议参数区间。 | 执行 sessions 列表专项压测并归档命令、时间戳、结果报告到 `docs/loadtest/evidence/`。 |
| debate-sessions-list-observability-dashboard-baseline | `debate_sessions_list_*` 指标与结构化日志已落地，但 dashboard 与告警阈值尚未固化。 | 建立 sessions 列表专项看板与告警阈值，完成一次值班演练与复盘记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |
| debate-sessions-count-reconcile-automation | 会话计数一致性修复当前通过脚本手工触发，未接入周期作业。 | 将 `debate_sessions_count_reconcile.sh` 纳入定时任务或 ops 编排，并形成巡检/告警闭环。 | 运行一周周期任务并归档执行日志、漂移检测率与修复记录。 |

## Y. debate-session-join-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-session-join-rate-limit-tuning-baseline | `POST /api/debate/sessions/{id}/join` 限频已落地，但阈值仍为工程初值，缺真实流量回标。 | 形成可复核报告：不同阈值下命中率、误杀率、冲突占比与 `p95/p99` 建议区间。 | 执行 join 接口专项压测并归档命令、时间戳、结果报告到 `docs/loadtest/evidence/`。 |
| debate-session-join-hotspot-lock-contention-baseline | `FOR UPDATE NOWAIT + lock_timeout` 已上线，但缺热点并发冲突/延迟数据基线。 | 形成热点场次压测报告：`debate_join_lock_timeout` 占比、成功率、退避建议与容量结论。 | 使用同 session 高并发脚本压测并归档报告到 `docs/consistency_reports/`。 |
| debate-session-join-observability-dashboard-baseline | join 指标与冲突分桶已落地，但 dashboard 与告警阈值尚未封板。 | 建立 `debate_session_join_*` 与冲突原因分桶看板，完成一次值班演练与复盘。 | 导出看板配置 + 告警演练记录 + 复盘文档归档。 |

## Z. debate-messages-list-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-messages-list-rate-limit-tuning-baseline | `GET /api/debate/sessions/{id}/messages` 双限频已落地，但阈值仍为工程初值，缺真实样本回标。 | 形成可复核报告：不同阈值下命中率、误杀率、`p95/p99` 与建议参数区间。 | 执行 messages 列表专项压测并归档命令、时间戳、结果报告到 `docs/loadtest/evidence/`。 |
| debate-messages-list-perf-baseline-evidence | 压测脚本已新增，但尚未产出正式基线报告。 | 输出包含吞吐、成功率、429 占比、`p95/p99` 的基线报告并沉淀证据索引。 | `bash chat/scripts/debate_messages_list_perf_baseline.sh --session-id <id> --token <token> --total-requests <n> --concurrency <n> --output <report.md>` 并归档。 |
| debate-messages-list-observability-dashboard-baseline | `debate_messages_list_*` 指标与结构化日志已落地，但 dashboard 与告警阈值尚未封板。 | 建立 messages 列表专项看板与告警阈值，完成一次值班演练与复盘记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |

## AA. debate-message-create-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-message-create-idempotency-retention | `debate_message_idempotency_keys` 已上线但缺少自动清理策略，长期运行存在表增长风险。 | 增加定时清理/归档策略（按 `created_at` TTL），并形成容量与保留策略说明。 | 新增清理任务并在测试环境跑通，归档执行日志与清理统计。 |
| debate-message-create-hot-score-flush-observability | `hot_score` 已改为增量异步 flush，但缺少 flush 延迟分位数与堆积告警阈值。 | 建立 `hot_score_delta_flush` 专项指标看板与告警阈值，完成一次值班演练。 | 导出看板配置 + 告警演练记录 + 一次复盘文档归档。 |
| debate-message-create-ingress-switch-drill | ingress mismatch readiness 阻断已落地，但缺少跨服务切换演练与操作手册证据。 | 形成 chat/notify 实时入口切换演练文档与前后快照证据（包含失败路径与恢复步骤）。 | 执行一次切换演练并归档 `/ops/kafka/readiness` 前后快照与操作日志。 |

## AB. debate-pins-list-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-pins-list-rate-limit-tuning-baseline | `GET /api/debate/sessions/{id}/pins` 双限频已落地，但阈值仍为工程初值，缺真实流量回标。 | 形成可复核报告：不同阈值下命中率、误杀率、`p95/p99` 与建议参数区间。 | 执行 pins 列表专项压测并归档命令、时间戳、结果报告到 `docs/loadtest/evidence/`。 |
| debate-pins-list-observability-dashboard-baseline | `debate_pins_list_*` 指标与结构化日志已落地，但 dashboard 与告警阈值尚未封板。 | 建立 pins 列表专项看板与告警阈值，完成一次值班演练与复盘记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |
| debate-pins-list-index-benefit-baseline | 复合索引与 active partial index 已落地，但缺少真实大样本 explain/延迟收益报告。 | 输出可复核性能报告：索引命中、`activeOnly=true/false` 下 `p95/p99` 对比与调优建议。 | 执行 explain + 压测并归档命令、时间戳与报告到 `docs/loadtest/evidence/`。 |

## AC. debate-message-pin-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-message-pin-rate-limit-tuning-baseline | `POST /api/debate/messages/{id}/pin` 双限频已落地，但阈值仍为工程初值，缺真实流量回标。 | 形成可复核报告：不同阈值下命中率、误杀率、`p95/p99` 与建议参数区间。 | 执行 pin 接口专项压测并归档命令、时间戳、结果报告到 `docs/loadtest/evidence/`。 |
| debate-message-pin-observability-dashboard-baseline | pin 指标与结构化日志已落地，但 dashboard 与告警阈值尚未封板。 | 建立 `debate_message_pin_*` 专项看板与告警阈值，完成一次值班演练与复盘记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |
| debate-message-pin-kafka-only-final-cutover | 当前为“kafka-only 时 trigger 静默”的治理阶段，尚未进入“彻底移除 trigger”终态。 | 在全局 kafka-only 稳定后完成最终收口决策（保留静默策略或物理移除 trigger），并形成可回滚方案。 | 执行切换演练并归档 `/ops/kafka/readiness` 快照、事件链路回归结果与回滚记录。 |

## AD. debate-judge-job-request-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-judge-job-request-degraded-fault-injection-evidence | 已实现 `degraded_enqueue_final_failed` 语义与日志，但缺少故障注入实证回归。 | 形成可复核报告：final enqueue 故障注入时，`status=degraded/reason=degraded_enqueue_final_failed`、日志告警、幂等回放语义均符合预期。 | 在本地执行故障注入脚本或手工注入，归档命令、时间戳、响应快照与日志到 `docs/consistency_reports/`。 |
| debate-judge-job-request-rate-limit-tuning-baseline | user/session + ip/session 双限频已落地，但阈值仍为工程初值，缺真实样本回标。 | 输出限频基线报告：命中率、误杀率、`p95/p99`、建议阈值区间与客户端退避策略。 | 执行接口专项压测并归档命令、时间戳与报告到 `docs/loadtest/evidence/`。 |
| debate-judge-job-request-lock-contention-baseline | 已缩短事务临界区，但缺热点并发场景的锁等待量化证据。 | 形成可复核热点并发报告：锁等待/冲突占比、成功率、延迟分位与容量建议。 | 使用同一 session 高并发压测并归档报告到 `docs/consistency_reports/`。 |

## AE. debate-ops-topics-ops-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-ops-topics-conflict-code-standardization | `POST /api/debate/ops/topics` 已能正确返回 `409`，但机读码语义仍部分依赖展示文案。 | 统一冲突错误为稳定 machine code（权限/幂等/业务冲突可直接分支），并保持 message 可读。 | 回归创建冲突场景，验证客户端仅凭 code 即可完成分支；归档响应样例。 |
| debate-ops-topics-db-unique-constraint-rollout | 当前重复防护以应用层锁+查重为主，尚未引入 DB 强唯一约束。 | 完成存量去重评估与迁移预案，并分阶段上线 `(title_norm, category)` 唯一约束（或等效表达式唯一索引）。 | 迁移预演（含回滚）+ 并发压测，归档 before/after 冲突行为对比报告。 |
| debate-ops-topics-category-dictionary-config | `category` 白名单已可用，但仍硬编码在服务端代码中。 | 支持配置中心或字典表驱动，新增分类无需发版；保留默认兜底。 | 新增分类热更新/配置变更联调记录，回归非法分类仍返回稳定 `400`。 |
| debate-ops-topics-update-rate-limit-idempotency-hardening | `PUT /api/debate/ops/topics/{id}` 本轮已完成正确性治理，但尚未接入更新侧限流与幂等保护。 | 更新接口接入 request_guard（user/ip 限流 + 幂等键策略），与创建接口治理水位对齐。 | Redis 开启环境下完成联调：限流命中、重试回放一致、冲突分支可观测；归档证据到 `docs/consistency_reports/`。 |
| debate-ops-topics-update-route-matrix | 更新接口已补模型层关键回归，但路由层 `200/400/401/403/404/409/422/500` 全矩阵仍未封板。 | 新增 update route 专项测试矩阵，覆盖鉴权、门禁、提取器失败、业务冲突和成功路径。 | 执行路由回归并归档测试结果，确保后续中间件/注解调整可被门禁拦截。 |
| debate-ops-topics-length-semantics-decision | 当前长度口径为字节数，中文字符场景可能与产品“字符数”预期有偏差。 | 明确并冻结长度语义（字节或字符），若切换需补迁移说明与回归矩阵。 | 评审结论文档 + 边界回归测试（中英文/emoji）通过并归档。 |
| debate-ops-topics-owner-configurability | Owner 历史语义仍存在硬编码实现痕迹，平台化弹性不足。 | 迁移为角色/配置驱动，不依赖固定 user_id。 | 回归 owner/ops_admin/ops_reviewer 权限矩阵并归档结果。 |

## AF. debate-ops-sessions-create-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-ops-sessions-error-model-standardization | `POST /api/debate/ops/sessions` 关键路径已稳定，但 400 类错误仍部分依赖文案串，机读语义不够硬。 | 收敛为稳定结构化错误模型（`code/message/details?`），客户端仅依赖 `code` 分支。 | 回归参数错误/冲突错误场景，验证客户端仅凭 `code` 可完成提示与动作分支；归档响应样例。 |
| debate-ops-sessions-joinable-semantics-unification | create 与 list 的 `joinable` 计算口径未完全统一（容量条件存在漂移风险）。 | 抽取统一 `joinable` 公式（公共 SQL 片段/视图），并在 create/list/update 共用。 | 创建后立即列表读取的对照回归通过，边界容量场景无语义漂移。 |
| debate-ops-sessions-route-matrix-expansion | 本轮已补关键 route 回归，但 `201/400/401/403/422/404/409/429/500` 全矩阵仍未完全封板。 | 新增 create-session route 专项全矩阵测试，覆盖鉴权、门禁、提取器、幂等、限流与冲突路径。 | 执行 route 测试集并归档结果，确保中间件/注解变更可被门禁拦截。 |
| debate-ops-sessions-topic-active-policy | 是否只允许 `is_active=true` topic 创建新场次尚未冻结，产品策略待确认。 | 明确 active 策略并固化到接口校验与错误码（允许历史题复开或 strict active-only）。 | 产品评审记录 + 接口回归（active/inactive topic）通过并归档。 |
| debate-ops-sessions-duplicate-schedule-governance | 当前缺“同 topic + 时间窗口”重复创建治理，重试/并发下仍可能产生重复排期。 | 完成业务去重规则（应用层查重 + DB 约束预案），并给出存量数据处理策略。 | 迁移预演（含回滚）+ 并发压测，归档重复创建前后行为对比报告。 |

## AG. debate-ops-sessions-update-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-ops-sessions-update-state-transition-policy | `PUT /api/debate/ops/sessions/{id}` 已完成治理增强，但状态机方向约束仍未冻结，运营可任意跳转。 | 明确并落地状态转移矩阵（必要时提供受控 override 入口），避免非法逆向流转。 | 状态机边界回归（含逆向流转）通过，产出策略评审与测试证据。 |
| debate-ops-sessions-update-actual-start-at-governance | 手工更新到 `open/running` 时 `actual_start_at` 语义治理尚未完成。 | 冻结 `actual_start_at` 规则（自动回填/保留策略）并补齐回归。 | 更新状态后字段一致性回归通过，报表口径校验记录归档。 |
| debate-ops-sessions-update-scheduled-future-policy | `scheduled` 的未来时态策略尚未统一，当前仅 `open/running` 强制 `endAt > now`。 | 明确并落地 create/update 一致的时间语义策略，避免过期计划态残留。 | 时间边界回归通过，策略文档与接口行为一致。 |
| debate-ops-sessions-update-route-matrix-expansion | 本轮已补关键 route 用例，但 `401/403/422/500` 等边界矩阵仍可继续扩展。 | 完成 update 路由全矩阵测试封板，覆盖中间件、提取器与异常路径。 | 执行 route 专项测试并归档结果，确保后续中间件改动可被门禁拦截。 |
| debate-ops-sessions-update-error-model-standardization | 当前 400/409 仍部分依赖文案串，机读稳定性不够强。 | 推进结构化错误模型（`code/message/details?`），客户端仅依赖 `code` 分支。 | 回归错误场景并验证客户端仅靠 `code` 完成分支，归档响应样例。 |
| debate-ops-sessions-update-schedule-change-realtime-event | 非状态字段（时间/人数）变更暂无实时事件，客户端可能读取旧计划。 | 为计划字段变更补齐实时事件（或等效 outbox 通知）并完成消费侧联调。 | 计划更新联调通过，前后端可观测字段与事件快照归档。 |

## AH. debate-ops-rbac-me-hardening 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-ops-rbac-me-error-model-standardization | `GET /api/debate/ops/rbac/me` 已完成 owner 真源与测试治理，但错误语义仍偏字符串。 | 收敛为结构化错误模型（`code/message/details?`），客户端仅依赖 `code` 分支。 | 回归 `401/403/500` 场景并验证客户端只依赖 `code` 即可稳定分支；归档响应样例。 |
| debate-ops-rbac-me-observability-dashboard-baseline | 控制平面读接口已稳定，但缺少 RBAC 专项看板与告警阈值。 | 建立 `ops_rbac_me_*` 指标看板与告警阈值，完成一次值班演练与复盘记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |
| debate-ops-rbac-me-revision-cache-strategy | 当前权限快照无 `rbacRevision/policyVersion`，客户端缓存失效策略不显式。 | 增加快照版本字段并与客户端缓存策略联动，避免短时权限漂移。 | 角色变更后快照一致性联调通过，归档“变更前后版本号与 UI 行为”证据。 |
| debate-ops-rbac-policy-unification | 同一 RBAC 快照被多模块消费，策略定义仍分散。 | 抽象统一 policy 层，沉淀可复用权限判定契约，降低多入口语义漂移。 | 选取 topics/iap/report 三条链路回归，验证策略统一后行为一致并归档。 |
| debate-ops-rbac-me-phone-gate-policy-decision | `rbac/me` 仍受 `require_phone_bound` 门禁，运维应急场景策略待产品冻结。 | 明确并固化“是否保留手机门禁”的产品决策，接口行为、错误码与文档三者一致。 | 产出策略评审记录 + 对应路由回归（保留/放开）并归档。 |

## AI. api058-rbac-roles-governance 后续待办（来源：当前开发计划）

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-ops-rbac-roles-observability-dashboard-baseline | `ops.rbac.*` 指标与字典已落地，但 dashboard/告警阈值仍未接入。 | 建立 `ops.rbac.roles_list.*`、`ops.rbac.me.*`、`ops.rbac.roles_write.*` 看板与告警阈值，完成一次值班演练与复盘。 | 运维看板配置导出 + 告警演练记录 + 复盘文档归档。 |
| debate-ops-rbac-roles-rate-limit-tuning-baseline | RBAC 三接口限流已接入，但阈值仍是工程初值，缺真实样本回标。 | 形成阈值调优基线报告：命中率、误杀率、`p95/p99`、建议参数区间。 | 执行 RBAC 管理面接口专项压测并归档命令、时间戳、结果报告到 `docs/loadtest/evidence/`。 |
| debate-ops-rbac-audit-query-surface-and-retention-policy | 审计落库与脚本级查询/留存已落地，但“脚本级 vs 受控 API”与归档层策略尚未评审冻结。 | 完成 RBAC 审计查询面形态决策（脚本或 API）与留存/归档策略定稿，形成正式结论与回滚路径。 | 评审纪要 + 结论文档归档，并补充受控查询演练与留存执行验收清单。 |
| debate-ops-rbac-roles-pagination-pii-policy | `rbacRevision` 已落地，但分页触发阈值与 PII 最小化策略仍未定稿。 | 冻结分页触发阈值与 PII 最小化边界，并更新 OpenAPI/前端消费契约。 | 回归分页边界与 PII 策略场景，并归档“revision + UI 刷新行为 + 策略评审记录”。 |
