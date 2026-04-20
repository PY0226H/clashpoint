# todo.md

## A. 文档说明
- 本文件只记录“明确延后”的技术债/收口债，不承担开发过程记录。
- 只有在阶段收口时，才把活动计划中的延后项写入本文件。
- 每条技术债都应写清：为什么这轮不做、何时再做、做到什么算完成。
- 不要把新需求脑暴、产品 wishlist 或尚未开工的泛化设想直接写进本文件。

## B. 技术债总则
- `来源模块`：该债务来自哪个已完成或阶段性完成的模块。
- `债务类型`：建议使用 `发布前收口 / 性能压测 / 可靠性 / 可观测性 / 多端契约 / 环境依赖 / 工程债`。
- `当前不做原因`：解释为什么这轮先不做，例如“距离上线较远”“当前无压测环境”“当前缺少真实联调对象”。
- `触发时机`：写清未来何时该重新捡起，例如“上线前收口”“获得压测环境后”“多端联调窗口开启后”。

## C. 当前写入区（新结构）

### C1. 发布前收口债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| v2-m4-iap-storekit-production-and-wallet-closure | `pay-iap-verify-hardening`、`pay-wallet-hardening` | 发布前收口 | 产品尚未进入提审/上线窗口，当前没有真机与生产配置封板需求。 | 上线前收口 | 形成“购买 -> 验单 -> 到账 -> 置顶消费”四证合一归档，并固定生产配置样本。 | `bash scripts/release/appstore_preflight_check.sh --runtime-env production --chat-config <prod-chat.yml> --tauri-app-config <prod-app.yml> --ai-judge-env <prod-ai.env>`；归档证据索引。 |
| v2-m10-release-readiness-and-appstore-runbook | 发布门禁工具链 | 发布前收口 | 当前距离上线还有距离，不需要现在就封板提审材料与演练证据。 | 上线前收口 | 提审材料齐套；上线与回滚演练均有时间戳、操作日志与结果证据。 | 运行 preflight 并完成发布 checklist 证据审计。 |

### C2. 性能 / 压测债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| auth-sessions-list-load-baseline-and-rate-limit-tuning | `auth-sessions-list-hardening` | 性能压测 | 当前没有稳定压测环境，不值得在本地伪造长期基线。 | 有压测环境后 | 形成可复核压测报告：不同会话规模下的 `p95/p99`、返回条目分布、限频命中率与阈值建议。 | 执行列表接口专项压测并归档到 `docs/loadtest/evidence/`。 |
| pay-iap-verify-rate-limit-and-retry-baseline | `pay-iap-verify-hardening` | 性能压测 | 当前缺真实交易样本与稳定压测环境，无法给出可信阈值。 | 有压测环境或上线前收口 | 形成可复核报告：`p95/p99`、限频命中率、冲突复用命中率、`retryAfterMs` 调参建议。 | 执行 verify 接口专项压测并归档到 `docs/loadtest/evidence/`。 |

### C3. 可靠性 / 故障注入债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| auth-session-revoke-redis-fault-injection-evidence | `auth-session-revoke-hardening` | 可靠性 | 代码与测试已覆盖补偿路径，但当前没有必要为了本地阶段立即补全真实故障注入证据。 | 上线前收口或专项可靠性回合 | 形成可复核故障注入报告：故障窗口、outbox 堆积/清空曲线、最终一致性对账结论。 | 本地执行 revoke + Redis 故障注入，归档命令、时间戳、指标截图与报告到 `docs/consistency_reports/`。 |
| auth-sms-send-callback-anti-replay | `auth-sms-send-hardening` | 可靠性 | 主链路已可用，防重放增强不阻塞当前本地开发闭环。 | 安全/上线前专项回合 | 落地签名 + 时间窗 + nonce 校验，并补齐成功/失败/重放攻击回归测试。 | `cd chat && cargo test -p chat-server handlers::auth::tests:: -- --nocapture` + callback 防重放专项用例。 |

### C4. 可观测性 / 告警 / Dashboard 债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| auth-sessions-list-observability-dashboard-baseline | `auth-sessions-list-hardening` | 可观测性 | 当前产品仍处于本地开发阶段，不需要立即固化运维看板和告警阈值。 | 进入值班/上线前收口 | 建立 `auth_sessions_list_*` 与 retention worker 指标看板，完成告警阈值与值班演练记录。 | 运维看板配置导出 + 告警演练记录 + 值班复盘归档。 |
| pay-iap-verify-observability-dashboard-baseline | `pay-iap-verify-hardening` | 可观测性 | 当前没有线上观测场景，提前固化看板收益有限。 | 上线前收口 | 建立 `iap_verify_*` 看板与告警阈值，完成一次值班演练与复盘记录。 | 运维看板配置导出 + 告警演练记录 + 一次值班复盘归档。 |

### C5. 多端契约联调债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| auth-session-revoke-multi-client-contract-alignment | `auth-session-revoke-hardening` | 多端契约 | 当前本轮目标是完成后端主体治理，不需要同步把所有客户端联调封板。 | 多端联调窗口开启后 | 完成多客户端对 `revoked/affectedCount/result` 的提示文案、重试/刷新策略联调，并沉淀映射表。 | 客户端联调脚本 + 手工回归，归档“字段 -> 动作映射”与结果快照。 |
| pay-iap-products-multi-client-contract-alignment | `pay-iap-products-list-hardening` | 多端契约 | 当前无统一多端联调窗口，先不占用本轮开发节奏。 | 多端联调窗口开启后 | Web/Mac/移动端统一 `items/revision/emptyReason` 与错误码映射策略，形成联调记录。 | 客户端联调脚本 + 手工回归，归档契约映射与结果快照。 |

### C6. 环境依赖阻塞项
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| v2-m2-lobby-search-and-join-flow-environment-e2e | `v2-m2-lobby-search-and-join-flow` | 环境依赖 | 当前缺联网环境 Playwright 实跑条件。 | 获得可联网环境后 | 完成 lobby E2E 实跑并沉淀 `playwright-report`、`test-results`、trace。 | `cd e2e && npm ci && npx playwright install --with-deps && npm run test:lobby`；报告链接写入 evidence 索引。 |
| b3-redis-collision-stress-high-scale-non-sandbox | `b3-outbox-switch-implementation-plan` | 环境依赖 | 当前会话受沙箱/环境限制，尚未形成高并发放大量化样本。 | 获得非受限环境后 | 在非受限环境产出 redis 多 worker 并发冲突压测报告。 | `cd ai_judge_service && ../scripts/py scripts/b3_report_collision_stress.py --workers 32 --mode redis` |

### C7. 低优先级工程债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| debate-pg-listener-channel-migration-plan | `debate-ws-reliability-refactor` | 工程债 | 当前不阻塞主链路，且优先级低于真实业务收口与环境验证。 | 有余量的基础设施治理回合 | 补齐 PG listener 剩余通道迁移清单、优先级与执行顺序。 | 输出迁移清单文档并完成评审。 |

### C8. API065 后置技术债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| api065-replay-execute-idempotency-key-rollout-decision | `api065-judge-replay-execute-governance-phase-closure` | 可靠性 | 当前已通过状态机与事务锁收敛重复执行风险，但缺真实重复提交样本，不适合立即引入额外幂等存储协议。 | execute 冲突率持续上升或出现重复触发投诉 | 形成 Go/No-Go 评审结论；若 Go，落地 `Idempotency-Key` 协议、冲突语义与回归测试。 | 统计 execute 冲突分布 + 评审记录；若落地则执行 `cargo test -p chat-server judge_replay` 并归档。 |
| api065-replay-execute-rate-limit-rollout-decision | `api065-judge-replay-execute-governance-phase-closure` | 性能压测 | 当前无稳定线上流量样本，先观察结构化日志与锁等待，不在本轮提前上限频以避免误伤 Ops 应急操作。 | execute QPS/锁等待异常或压测窗口开启 | 形成 user/ip 限流阈值建议并完成 Go/No-Go；若 Go，落地限频与告警阈值。 | 执行 execute 压测 + 锁等待观测，归档报告到 `docs/loadtest/evidence/`。 |
| api065-replay-execute-permission-status-semantics-review | `api065-judge-replay-execute-governance-phase-closure` | 多端契约 | 当前接口沿用历史 `409` 权限拒绝语义，短期不改避免跨端回归面扩大。 | 多端联调窗口开启或持续出现权限语义歧义反馈 | 形成 409/403 统一语义评审结论；若切换，完成前后端错误码映射与回归封板。 | 联调脚本 + 错误码映射表 + route 回归结果归档。 |

### C9. API066 后置技术债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| api066-replay-actions-cursor-pagination-evaluation | `api066-judge-replay-actions-governance-phase-closure` | 工程债 | 当前 `offset + count/list` 方案已可满足本地阶段，提前切 cursor 会扩大前后端联动改造面。 | 列表深分页成本上升或进入多端统一分页改造窗口 | 形成 cursor/keyset 设计评审结论并落地 `(created_at,id)` 游标协议与回归测试。 | 方案评审记录 + `cargo test -p chat-server list_judge_replay_actions_by_owner_should -- --nocapture` + 前端联调记录。 |
| api066-replay-actions-read-rate-limit-rollout-decision | `api066-judge-replay-actions-governance-phase-closure` | 性能压测 | 当前缺少真实 Ops 检索流量样本，先观察结构化日志，不在本轮提前启用读限流避免误伤排障。 | 查询 QPS/慢查询占比异常或压测窗口开启 | 形成 user/ip 限流阈值 Go/No-Go 结论；若 Go，落地限流与告警阈值并补测试。 | 压测报告 + 错误预算评审记录 + route 回归结果归档。 |
| api066-replay-actions-query-rejection-unification | `api066-judge-replay-actions-governance-phase-closure` | 多端契约 | 当前接口沿用 `Query<T>` 默认提取错误语义，单点改造收益低于家族统一改造。 | API 家族统一错误语义治理启动 | 完成 QueryRejection 统一包装并给出稳定错误码映射表。 | 接口家族联调脚本 + 错误码映射表 + route 回归结果归档。 |
| api066-replay-actions-pgtrgm-real-benchmark-baseline | `api066-judge-replay-actions-governance-phase-closure` | 性能压测 | 本轮仅完成 dry-run 基线，缺真实库（含/不含 `pg_trgm`）的可对比样本。 | 拿到可压测数据库或上线前容量收口 | 形成真实 before/after 基线报告，明确 `ILIKE` 场景性能下限与告警阈值建议。 | `bash chat/scripts/ai_judge_replay_actions_perf_regression_suite.sh ...` + `..._gate.sh ...`，报告归档到 `docs/consistency_reports/`。 |

### C10. API067 后置技术债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| api067-rejudge-run-versioning-migration-baseline-verify | `api067-judge-rejudge-run-versioning-phase-closure` | 环境依赖 | 本地库存在迁移基线漂移（`sqlx migrate run` 报 `relation \"users\" already exists`），当前执行结果不具备标准验收可信度。 | 获得标准迁移基线库后 | 在标准基线库完成 run/version 迁移验收并归档证据（执行记录、结果摘要、SQL 校验输出）。 | `cd chat && DATABASE_URL=<baseline_db> ./scripts/ai_judge_rejudge_run_versioning_verify.sh`。 |
| api067-rejudge-rate-limit-rollout-decision | `api067-judge-rejudge-run-versioning-phase-closure` | 性能压测 | 当前缺真实 Ops 重判流量样本，提前固化阈值容易误伤应急操作。 | rejudge QPS 异常或压测窗口开启 | 形成 user/session 与 ip/session 限流阈值 Go/No-Go 结论；若 Go，完成限流落地与告警阈值封板。 | 执行 rejudge 压测并归档报告 + route 回归结果。 |
| api067-rejudge-idempotency-strategy-rollout-decision | `api067-judge-rejudge-run-versioning-phase-closure` | 可靠性 | 当前 run/version 已支持“每次新 run”语义，尚缺真实重复触发样本，不宜提前引入额外幂等存储协议。 | 出现重复触发投诉或锁冲突指标上升 | 形成幂等策略 Go/No-Go 结论；若 Go，落地 `Idempotency-Key` 协议、冲突语义与回归测试。 | 冲突分布统计 + 评审记录；若落地则执行 `cargo test -p chat-server rejudge -- --nocapture` 并归档。 |
| api067-rejudge-observability-and-fault-drill-closure | `api067-judge-rejudge-run-versioning-phase-closure` | 可观测性 | 当前已补接口结构化日志，但发布前告警看板与故障演练证据尚未封板。 | 上线前收口 | 建立 rejudge 频率/成功率/degraded 比例/耗时看板，并完成一次故障注入演练与复盘。 | 告警配置导出 + 演练记录 + 复盘文档归档。 |
| api067-rejudge-dedicated-audit-surface-evaluation | `api067-judge-rejudge-run-versioning-phase-closure` | 工程债 | 当前已具备 replay actions 审计与结构化日志，独立 rejudge 主事件审计表属于增强项，不阻塞本阶段交付。 | 合规审计检索需求提升或值班复盘频繁受阻 | 完成独立 rejudge 审计建模评审；若 Go，落地审计表与查询面并补回归测试。 | 评审记录 + 迁移脚本 + `cargo test -p chat-server rejudge -- --nocapture`。 |

### C11. API068 后置技术债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| api068-observability-config-read-cache-rollout-decision | `api068-observability-config-governance-phase-closure` | 性能压测 | 当前本地阶段接口规模较小，先完成契约/权限收敛；提前引入缓存会放大行为面与排障复杂度。 | Ops 高频刷新导致 DB 读压上升，或进入上线前容量收口 | 形成缓存 Go/No-Go 评审；若 Go，落地 `3~5s` 短 TTL + 写后失效，并补齐一致性与回归测试。 | 压测报告 + 评审结论；若落地则执行 `cargo test -p chat-server get_ops_observability_config -- --nocapture` 与写后读一致性专项用例。 |
| api068-observability-config-read-rate-limit-rollout-decision | `api068-observability-config-governance-phase-closure` | 性能压测 | 真实 Ops 流量样本不足，当前不宜提前固化阈值，以免误伤值班排障操作。 | 读取 QPS 异常、出现滥刷迹象，或压测窗口开启 | 形成 user/ip 限流阈值 Go/No-Go 结论；若 Go，落地限流、告警阈值与错误语义回归。 | 压测与日志分布分析归档；若落地则执行 route 回归并补 `429` 断言。 |
| api068-observability-anomaly-state-lifecycle-governance | `api068-observability-config-governance-phase-closure` | 工程债 | 当前仅在读路径惰性清理，功能可用但持久层压缩策略尚未设计定稿。 | anomaly_state 冗余规模上升、排障可读性下降，或进入发布前治理回合 | 明确“定时压缩”或“写时压缩”方案并落地，保证历史冗余键可控且行为可审计。 | 方案评审记录 + 数据体量对比报告 + 相关 model 测试通过。 |

### C12. API069 后置技术债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| api069-metrics-dictionary-source-of-truth-governance | `api069-observability-metrics-dictionary-governance-phase-closure` | 工程债 | 当前已补齐 revision/缓存与质量门禁，优先保证现网可维护；“字典与埋点同源治理”改造面较大，不适合在本轮并入。 | 指标定义漂移频发、跨服务字典协同需求提升，或进入发布前治理回合 | 完成 C1（代码 registry 同源）或 C2（manifest + 代码生成）方案评审并落地，确保“新增/下线埋点”与字典变更一致。 | 方案评审记录 + 回归测试 + 变更前后对照报告归档。 |
| api069-metrics-dictionary-category-filter-evaluation | `api069-observability-metrics-dictionary-governance-phase-closure` | 性能压测 | 当前字典规模（33项）全量返回成本可接受，提前扩展筛选参数收益有限且会放大契约面。 | 指标规模持续增长、客户端拉取频率上升，或出现明显传输/解析成本压力 | 形成 `category` 过滤 Go/No-Go 结论；若 Go，落地可选查询参数且保持默认全量兼容。 | 压测与链路观测报告 + route/model 回归测试归档。 |
| api069-metrics-dictionary-permission-semantics-review | `api069-observability-metrics-dictionary-governance-phase-closure` | 多端契约 | 当前沿用最小权限策略（`platform_role_admin` 默认无 `ObservabilityRead`），短期不改可避免跨角色行为震荡。 | 产品/安全评审窗口开启，或出现角色语义争议反馈 | 明确并冻结权限语义（是否放开 `platform_role_admin` 读取），同步更新权限矩阵、学习文档与回归测试。 | 评审结论归档 + route 回归 + 权限矩阵文档同步。 |

### C13. API070 后置技术债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| api070-slo-snapshot-window-anchor-unification | `api070-observability-slo-snapshot-governance-phase-closure` | 工程债 | 当前先完成契约/权限/语义收敛，时间口径统一会牵涉信号层统计定义与多接口一致性，不适合与本轮并行硬切。 | 出现“成功率与时延观感不一致”反馈，或进入 API070 第二轮治理窗口 | 统一 `load_recent_judge_signal` 的时间锚点口径并文档化（单一采用 `updated_at` 或 `created_at`），补齐回归测试。 | `cargo test -p chat-server get_ops_observability_slo_snapshot -- --nocapture` + 指标口径对照报告归档。 |
| api070-slo-snapshot-threshold-domain-rename-cutover | `api070-observability-slo-snapshot-governance-phase-closure` | 工程债 | 当前阈值字段兼容历史命名，直接硬切会联动配置写接口、前端阈值面板与存量配置迁移，改造面较大。 | 发生调参误配事故，或进入 observability 阈值统一治理回合 | 完成字段域拆分并硬切：`high_coalesced_threshold -> dlq_pending_threshold`、`min_request_for_cache_hit_check -> min_completed_for_slo_eval`，同步迁移与前后端契约。 | 迁移脚本 + route/model 回归 + 前端 typecheck 与联调记录归档。 |
| api070-slo-snapshot-read-protection-rollout-decision | `api070-observability-slo-snapshot-governance-phase-closure` | 性能压测 | 当前已先完成 N+1 消除与日志补位，真实 QPS 样本不足，暂不提前固化缓存/限流阈值以免误伤值班操作。 | Ops 面板高频刷新导致 DB 压力上升，或压测窗口开启 | 完成读保护 Go/No-Go 评审；若 Go，落地“2~5s 短 TTL 缓存”或“user/ip 读限流”并补齐告警阈值。 | 压测报告 + 慢查询观测 + route 回归结果归档。 |
| api070-slo-snapshot-last-emitted-freshness-indicator | `api070-observability-slo-snapshot-governance-phase-closure` | 可观测性 | 当前返回 `lastEmittedStatus` 但缺“最近评估时间/新鲜度”提示，不阻塞本轮主链收口。 | 值班复盘中频繁出现“状态是否过期”判读困难 | 在规则快照中补充状态新鲜度字段（如 `lastEvaluatedAtMs`），并同步前端提示策略。 | route/model 回归 + 前端展示联调记录 + 值班演练记录归档。 |

### C14. API071 后置技术债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| api071-split-readiness-cache-ttl-automation-coverage | `api071-observability-split-readiness-governance-phase-closure` | 工程债 | 当前测试环境中 handler 缓存逻辑默认禁用，本轮优先完成主链路治理与契约收口。 | 进入 API071 第二轮治理或发布前稳定性回合 | 增加可控时钟或集成测试，覆盖“TTL 内命中、TTL 外刷新、review 写后失效”三类行为。 | 新增缓存专项测试并归档：`cargo test -p chat-server split_readiness_cache -- --nocapture`（按最终命名）。 |
| api071-split-readiness-evidence-schema-typing | `api071-observability-split-readiness-governance-phase-closure` | 工程债 | 当前 `thresholds[].evidence` 使用自由 JSON 可快速演进，但不利于编译期契约保护；本轮不扩大重构面。 | 字段漂移导致前端运行时兼容问题，或 API071+ 家族统一契约治理启动 | 按规则类型引入强类型 schema（至少覆盖 `judge_dispatch_pressure` 与 `payment_compliance_isolation`），并完成前后端同步。 | 后端类型与 OpenAPI 同步回归 + 前端 typecheck + 契约映射文档归档。 |
| api071-split-readiness-threshold-config-center | `api071-observability-split-readiness-governance-phase-closure` | 可运维性 | 当前阈值常量硬编码可满足本地阶段，提前平台化会显著扩大改造范围。 | 调参频率上升、需要审计阈值变更，或进入 observability 平台化阶段 | 阈值配置接入版本化配置源，具备“版本号、生效时间、回滚策略、变更审计”。 | 配置变更演练 + 回滚演练 + 回归测试与审计日志归档。 |
| api071-split-readiness-multi-instance-cache-consistency | `api071-observability-split-readiness-governance-phase-closure` | 可靠性 | 当前采用进程内 3 秒缓存，适配本地/单实例阶段；多实例一致性优化不阻塞本轮交付。 | 进入多实例部署或出现节点间快照不一致排障案例 | 形成共享缓存或统一限流方案并落地，保证多节点读一致性与可观测性。 | 多实例对照压测 + 一致性检查脚本 + 结果归档到 `docs/consistency_reports/`。 |

### C15. API072 后置技术债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| api072-split-review-audits-cursor-pagination-evaluation | `api072-observability-split-readiness-reviews-governance-phase-closure` | 性能压测 | 当前已完成契约、回归、过滤与限流收口；直接切 cursor 会扩大前后端联动改造面，本轮先保留 offset。 | 深分页响应时延上升，或进入 observability 查询模型统一治理窗口 | 形成 cursor/keyset Go/No-Go 结论；若 Go，落地基于 `(created_at,id)` 的游标协议并补齐回归测试。 | 压测报告 + 评审记录 + `cargo test -p chat-server list_ops_service_split_review_audits -- --nocapture`（按最终命名） + 前端联调归档。 |
| api072-split-review-audits-revision-etag-evaluation | `api072-observability-split-readiness-reviews-governance-phase-closure` | 工程债 | 当前控制台读压主要通过 user 限流兜底，`revision/etag` 协商缓存改造收益需结合真实刷新频率评估。 | 控制台轮询频率提升或出现重复拉取成本明显上升 | 形成 `revision/ETag + If-None-Match` 方案评审并落地（若 Go），支持 `304` 协商返回。 | 评审结论 + route/model 回归 + 端到端缓存命中验证归档。 |
| api072-split-review-audits-retention-governance | `api072-observability-split-readiness-reviews-governance-phase-closure` | 可运维性 | 当前数据规模可控，本轮优先完成接口治理闭环；审计归档策略需要跨模块一致性评审。 | 审计表增长显著、查询成本上升，或进入发布前数据治理回合 | 明确保留周期、归档与清理策略（含审计可追溯要求），并形成执行与回滚 SOP。 | retention 方案评审记录 + 演练日志 + 查询基线对比报告归档。 |

### C16. API052 后置技术债
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| api052-dispatch-metrics-process-startup-freshness-indicator | `api052-judge-dispatch-metrics-governance-phase-closure` | 可观测性 | 本轮优先完成口径正确性与维度化，未扩展进程级可解释字段。 | 多实例部署或值班复盘出现“归零无法解释”时 | 在指标输出补齐 `processStartAtMs/instanceId` 或等效可解释字段，并更新文档与看板聚合策略。 | `cargo test -p chat-server judge_dispatch -- --nocapture` + 看板聚合规则回归记录归档。 |
| api052-dispatch-metrics-internal-auth-signature-rollout | `api052-judge-dispatch-metrics-governance-phase-closure` | 发布前收口 | 当前仍处本地开发阶段，先不扩大到全内部 API 鉴权体系改造。 | 上线前安全收口窗口 | 将内部鉴权从静态 key 升级为 `key-id + HMAC(signature,timestamp,nonce)`，并支持时间窗、重放防护、密钥轮换。 | 安全回归脚本 + 401/签名错误/重放攻击用例通过并归档。 |
| api052-dispatch-metrics-fault-injection-and-backlog-anomaly-drill | `api052-judge-dispatch-metrics-governance-phase-closure` | 可靠性 | 目前单测已覆盖口径，但真实超时与 backlog 异常注入演练尚未完成。 | 压测窗口开启或上线前可靠性演练 | 形成超时故障注入与 backlog 刷新异常演练报告，验证指标分桶与告警阈值可用。 | 压测/故障注入脚本执行记录 + 指标快照 + 复盘报告归档到 `docs/consistency_reports/`。 |
| api052-dispatch-metrics-relaxed-snapshot-consistency-governance | `api052-judge-dispatch-metrics-governance-phase-closure` | 工程债 | 当前 `Relaxed` 快照满足性能目标，短期不做强一致快照重构。 | 出现守恒误报或看板依赖严格瞬时一致时 | 形成一致性策略评审（窗口平滑/采样聚合/强一致快照方案）并固化调用约束。 | 评审结论 + 指标守恒误报对比报告归档。 |

## Z. 历史待迁移技术债（只读归档）
- 下方内容保留旧结构，仅用于查询和后续分批迁移。
- 新增技术债不要继续写入下方旧结构。

## A. P0 发布阻塞

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
| debate-ops-rbac-me-revision-cache-strategy | `rbacRevision` 已落地，但跨模块 `policyVersion`/缓存失效策略仍未统一。 | 冻结 RBAC 快照版本策略（`rbacRevision` 与可选 `policyVersion` 的职责边界）并统一客户端缓存失效规则。 | 角色变更后快照一致性联调通过，归档“变更前后版本号与 UI 行为”证据。 |
| debate-ops-rbac-policy-unification | 同一 RBAC 快照被多模块消费，策略定义仍分散。 | 抽象统一 policy 层，沉淀可复用权限判定契约，降低多入口语义漂移。 | 选取 topics/iap/report 三条链路回归，验证策略统一后行为一致并归档。 |
| debate-ops-rbac-me-phone-gate-policy-decision | `rbac/me` 仍受 `require_phone_bound` 门禁，运维应急场景策略待产品冻结。 | 明确并固化“是否保留手机门禁”的产品决策，接口行为、错误码与文档三者一致。 | 产出策略评审记录 + 对应路由回归（保留/放开）并归档。 |

## AI. api058-rbac-roles-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-08）：
- `docs/dev_plan/当前开发计划.md` 中 API058 未完成项已并入本分组持续跟踪。
- API058 已完成项已并入 `docs/dev_plan/completed.md`（条目：`api058-rbac-roles-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| debate-ops-rbac-roles-observability-dashboard-baseline | `ops.rbac.*` 指标与字典已落地，但 dashboard/告警阈值仍未接入。 | 建立 `ops.rbac.roles_list.*`、`ops.rbac.me.*`、`ops.rbac.roles_write.*` 看板与告警阈值，完成一次值班演练与复盘。 | 运维看板配置导出 + 告警演练记录 + 复盘文档归档。 |
| debate-ops-rbac-roles-rate-limit-tuning-baseline | RBAC 三接口限流已接入，但阈值仍是工程初值，缺真实样本回标。 | 形成阈值调优基线报告：命中率、误杀率、`p95/p99`、建议参数区间。 | 执行 RBAC 管理面接口专项压测并归档命令、时间戳、结果报告到 `docs/loadtest/evidence/`。 |
| debate-ops-rbac-audit-query-surface-and-retention-policy | 审计落库与脚本级查询/留存已落地，但“脚本级 vs 受控 API”与归档层策略尚未评审冻结。 | 完成 RBAC 审计查询面形态决策（脚本或 API）与留存/归档策略定稿，形成正式结论与回滚路径。 | 评审纪要 + 结论文档归档，并补充受控查询演练与留存执行验收清单。 |
| debate-ops-rbac-roles-pagination-pii-policy | `rbacRevision` 已落地，PII 已收口为“默认 minimal + 显式 full”；分页触发阈值与扩展分页契约仍未定稿。 | 冻结分页触发阈值与分页预案（cursor/limit 或等效），并固化 full PII 触发条件与审计要求。 | 回归分页边界与 PII 策略场景，并归档“revision + UI 刷新行为 + 策略评审记录”。 |

## AJ. api059-rbac-roles-write-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-09）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API059 未解决项已并入本分组持续跟踪。
- API059 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api059-rbac-roles-write-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api059-rbac-write-trusted-proxy-production-rollout | `server.forwarded_header_trust` 机制已落地，但生产代理链路白名单（`trusted_proxy_ids/cidrs`）与误配排查 Runbook 尚未完成运维收口。 | 形成并上线生产白名单配置，完成一次误配/缺配演练并沉淀排查手册。 | 生产前在预发执行“trusted/untrusted 透传头”对照回归，归档配置快照、演练命令与结果记录到 `docs/consistency_reports/`。 |
| api059-rbac-write-forwarded-header-governance-rollout | API059 已完成“仅可信代理采信转发头”，但 auth/payment/ticket 等控制面写接口尚未统一复用同策略。 | 完成跨接口治理清单与改造收口，确保“转发头采信边界”在控制面写路径一致。 | 输出治理评审清单并执行接口级回归（至少覆盖 auth/payment/ticket 各 1 条核心写路径），归档结果到 `docs/consistency_reports/`。 |
| api059-rbac-write-observability-and-load-baseline | API059 功能闭环已完成，但 RBAC 写链路尚未形成正式 dashboard/告警阈值与并发冲突/限流压测基线。 | 建立 `ops.rbac.roles_write.*` 观测看板与告警阈值，并形成 `ops_rbac_revision_conflict`、限流命中率、`p95/p99` 压测基线报告。 | 执行 RBAC 写接口专项压测，导出看板配置与告警演练记录，统一归档到 `docs/loadtest/evidence/` 与 `docs/consistency_reports/`。 |

## AK. api060-rbac-roles-delete-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-09）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API060 未完成项已并入本分组持续跟踪。
- API060 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api060-rbac-roles-delete-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api060-rbac-delete-trusted-proxy-production-rollout | trusted proxy 门控机制已落地，但预发/生产 `trusted_proxy_ids/cidrs` 白名单与误配演练尚未运维收口。 | 完成白名单配置上线、误配/缺配演练与 runbook 定版，确保来源信任边界可运维。 | 在预发执行 trusted/untrusted 转发头对照回归，归档配置快照、演练命令、响应与日志证据到 `docs/consistency_reports/`。 |
| api060-rbac-delete-forwarded-header-governance-rollout | API060 已收敛来源信任边界，但 auth/payment/ticket 控制面写接口尚未统一复用。 | 完成跨接口治理清单与分批改造收口，统一“仅可信代理采信转发头”的策略。 | 按接口清单执行回归（至少 auth/payment/ticket 各 1 条核心写路径），归档报告到 `docs/consistency_reports/`。 |
| api060-rbac-delete-observability-and-load-baseline | DELETE 已补充 revoke 观测信号，但未形成 dashboard、告警阈值与压测基线封板。 | 建立 `ops.rbac.roles_write.*` 看板，冻结冲突率/限流率/outbox 健康度阈值，并形成压测基线报告。 | 执行 RBAC 写链路专项压测，导出看板和告警演练证据，归档到 `docs/loadtest/evidence/` 与 `docs/consistency_reports/`。 |
| api060-rbac-delete-semantic-strategy-observation | DELETE 去噪与 strict 语义当前为“观察期决策”（No-Go + 观测侧聚合），缺真实运行样本支撑下一步。 | 基于 2~4 周样本输出评审结论：保持现状或升级为协议变更（`idempotency-key`/strict mode）。 | 归档样本统计与评审纪要，明确 Go/No-Go 与回滚条件，并同步学习文档与 API 契约。 |

## AL. api061-judge-reviews-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-09）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API061 未完成项已并入本分组持续跟踪。
- API061 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api061-judge-reviews-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api061-judge-reviews-pagination-upgrade-evaluation | 当前仅 `limit`，缺少 cursor 翻页；深历史审核需要重复扫描新窗口。 | 形成 `time+id` cursor 方案与迁移评审（含响应契约、兼容策略、回滚路径）。 | 输出接口方案文档并完成至少 1 轮前后端联调评审纪要。 |
| api061-judge-reviews-threshold-configurability | `narrow_score_gap` 等异常阈值硬编码在服务端，策略调参需发版。 | 将核心异常阈值配置化（配置表或配置中心），并支持灰度回滚。 | 通过配置变更回归验证阈值生效与回滚，归档配置快照和测试报告。 |
| api061-judge-reviews-query-performance-baseline | `($N IS NULL OR ...)` 与 JSONB 长度判断在大数据量下性能边界不明确。 | 产出 explain+压测封板报告，明确是否需要索引/SQL 改写。 | 归档查询计划、`p95/p99`、吞吐与 CPU 指标到 `docs/loadtest/evidence/`。 |
| api061-judge-reviews-permission-status-semantics-review | 权限拒绝仍是 `409 ops_permission_denied:*`，与常见 `403` 语义存在认知偏差。 | 完成错误语义评审结论（维持 409 或迁移 403）并给出客户端迁移方案。 | 产出评审纪要与契约更新记录，补充相应回归测试。 |
| api061-judge-reviews-read-rate-limit-rollout-decision | 本轮对读限流结论为 No-Go（后置），缺线上样本支撑下一步阈值设计。 | 基于 2~4 周观测数据完成 Go/No-Go 复评，若 Go 先落 user 维度限流再评估 ip 维度。 | 归档 scanned/returned/anomaly_hit 统计与压测结果，形成正式决策文档。 |

## AM. api062-judge-final-dispatch-failure-stats-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-09）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API062 未完成项已并入本分组持续跟踪。
- API062 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api062-judge-final-dispatch-failure-stats-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api062-failure-stats-alert-threshold-baseline | 接口已输出 `unknown_rate/truncated_rate/scan_coverage/latency_ms`，但告警阈值尚未在监控平台固化。 | 固化阈值（初版建议：`unknown_rate>0.20`、`truncated_rate>0.80`、`p95>300ms`）并完成一次告警演练。 | 导出看板/告警配置与演练复盘，归档到 `docs/consistency_reports/`。 |
| api062-failure-stats-read-rate-limit-rollout-decision | 当前读接口未接限流，是否接入缺真实流量样本支撑。 | 基于 2~4 周观测数据完成 Go/No-Go 复评，若 Go 先落 user 维度后评估 ip 维度。 | 归档请求量、`scan_limit` 分布、`p95/p99` 与 DB 压力指标，形成正式决策文档。 |
| api062-failure-stats-permission-status-semantics-review | 权限拒绝语义仍是 `409 ops_permission_denied:*`，与常见 `403` 语义存在跨端认知偏差。 | 完成语义评审结论（维持 409 或迁移 403）并给出客户端迁移策略。 | 产出评审纪要 + 契约更新记录 + 对应回归测试清单。 |
| api062-failure-stats-failure-type-filter-evaluation | 当前仅支持窗口+limit，不支持 `failureType` 定向过滤。 | 形成 `failureType` 过滤增强方案（契约、索引、回滚路径）并完成评审。 | 输出方案文档并完成至少 1 轮前后端联调评审纪要。 |
| api062-failure-stats-query-performance-baseline | COUNT + 采样双查询在大数据量下性能边界尚无封板报告。 | 产出 explain+压测基线，明确是否需要默认窗口收紧或索引/SQL 改写。 | 归档查询计划、`p95/p99`、吞吐与 CPU 指标到 `docs/loadtest/evidence/`。 |

## AN. api063-judge-trace-replay-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-09）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API063 未完成项已并入本分组持续跟踪。
- API063 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api063-judge-trace-replay-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api063-trace-replay-pagination-upgrade-evaluation | 当前仅 `limit`，无 cursor 翻页；深历史追踪需要重复扫窗口。 | 形成 `created_at + job_id + scope` cursor 方案（含响应契约、兼容策略、回滚路径）并完成评审。 | 输出接口方案文档并完成至少 1 轮前后端联调评审纪要。 |
| api063-trace-replay-query-performance-baseline | `UNION ALL + 相关子查询` 在大数据量与高 limit 场景下性能边界尚无封板报告。 | 产出 explain+压测基线，明确是否需要 SQL 改写（LATERAL/预聚合）或索引增强。 | 归档查询计划、`p95/p99`、吞吐与 CPU 指标到 `docs/loadtest/evidence/`。 |
| api063-trace-replay-read-rate-limit-rollout-decision | 接口已补观测日志，但读限流是否接入缺真实流量样本支撑。 | 基于 2~4 周观测数据完成 Go/No-Go 复评，若 Go 先落 user 维度后评估 ip 维度。 | 归档请求量、`limit` 分布、`p95/p99` 与 DB 压力指标，形成正式决策文档。 |
| api063-trace-replay-permission-status-semantics-review | 权限拒绝仍是 `409 ops_permission_denied:*`，与常见 `403` 语义存在跨端认知偏差。 | 完成语义评审结论（维持 409 或迁移 403）并给出客户端迁移策略。 | 产出评审纪要 + 契约更新记录 + 对应回归测试清单。 |

## AO. api064-judge-replay-preview-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-09）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API064 未完成项已并入本分组持续跟踪。
- API064 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api064-judge-replay-preview-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api064-replay-preview-read-rate-limit-rollout-decision | preview 接口已补观测日志，但读限流是否启用缺真实流量样本支撑。 | 基于 2~4 周观测数据完成 Go/No-Go 复评；若 Go，先落 user 维度限流，再评估 ip 维度。 | 归档请求量、`message_count/snapshot_bytes` 分布、`p95/p99` 与 DB 读压力指标，形成正式决策文档。 |
| api064-replay-preview-payload-governance-evaluation | phase 预览返回完整消息体，容量与响应体治理策略尚未冻结。 | 形成 payload 治理方案（保留现状 / 分层返回 / 裁剪策略）并明确兼容与回滚路径。 | 输出方案文档并完成至少 1 轮前后端联调评审纪要，补充容量对比基线。 |
| api064-replay-preview-query-consistency-snapshot-evaluation | phase 分支采用 job + messages 双查询，是否需要读事务快照仍无样本结论。 | 完成一致性风险评估，明确是否引入事务快照或保持现状并附触发阈值。 | 归档异常样本统计（`message_count mismatch`）与评审纪要，补充对应回归/压测证据。 |
| api064-replay-preview-permission-status-semantics-review | 权限拒绝仍沿用 `409 ops_permission_denied:*`，与常见 `403` 语义存在跨端认知偏差。 | 完成语义评审结论（维持 409 或迁移 403）并给出客户端迁移策略。 | 产出评审纪要 + 契约更新记录 + 对应回归测试清单。 |

## AP. api049-phase-report-hardening 后续待办（来源：当前开发计划）

整合说明（2026-04-10）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API049 未完成项已并入本分组持续跟踪。
- API049 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api049-phase-report-hardening-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api049-phase-report-idempotent-echo-truth | 幂等短路分支仍回显输入 `sessionId/phaseNo`，非 job 真值，可能掩盖上游 payload 漂移。 | 幂等分支返回 job 真值（或在幂等返回前做一致性校验），并冻结契约行为。 | 新增模型回归：重复回调 + 错配入参场景，验证返回值与 job 真值一致；归档测试记录。 |
| api049-phase-report-message-ids-window-validation | `messageIds` 仅校验非空/非零，未校验是否落在 job 消息窗口。 | 增加 `messageIds` 窗口校验与去重约束，拒绝越界引用。 | 新增模型回归：越界/重复 `messageIds` 场景返回 `400`，并归档回归结果。 |
| api049-phase-report-rejection-observability-baseline | 回调拒绝原因（状态冲突/权重非法等）缺专项指标与告警阈值。 | 建立拒绝原因分桶指标与结构化日志字段，完成 dashboard 与告警阈值封板。 | 导出看板配置 + 告警演练记录 + 一次值班复盘归档。 |
| api049-phase-report-dispatching-state-evolution | 当前为最小止血策略，尚未引入 `dispatching` 稳态模型统一 worker/回调时序语义。 | 完成 `dispatching` 演进设计与落地（含迁移、回滚、测试），统一状态机语义。 | 评审纪要 + 迁移脚本演练 + worker/callback 闭环集成回归通过并归档。 |

## AQ. api050-final-report-hardening 后续待办（来源：当前开发计划）

整合说明（2026-04-10）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API050 未完成项已并入本分组持续跟踪。
- API050 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api050-final-report-hardening-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api050-final-report-winner-draw-vote-consistency-governance | 当前仅做 winner 枚举合法性校验，未强约束 `winner=draw` 与 `needsDrawVote=true` 及 `winnerFirst/winnerSecond` 的一致性。 | 增加 final 语义一致性校验与稳定错误码，避免写入冲突组合。 | 新增模型回归：draw 场景/冲突组合场景，验证拒绝语义与错误码；归档测试记录。 |
| api050-final-report-rejection-observability-baseline | 回调拒绝原因（状态冲突、session mismatch、字段非法）缺统一分桶指标与告警阈值。 | 建立拒绝原因分桶指标与结构化日志字段，完成 dashboard 与告警阈值封板。 | 导出看板配置 + 告警演练记录 + 一次值班复盘归档。 |
| api050-final-report-dispatching-state-evolution | 当前采用“准入放宽”止血，尚未引入 `dispatching` 中间态统一 worker/回调语义。 | 完成 `dispatching` 状态机方案评审与落地（含迁移、回滚、测试）。 | 评审纪要 + 迁移演练 + worker/callback 闭环集成回归通过并归档。 |
| api050-final-report-callback-signature-anti-replay | 当前仅 `x-ai-internal-key` 校验，缺签名时间窗与 nonce 防重放。 | 上线前落地 HMAC 签名（body hash + timestamp + nonce）与短窗去重校验。 | 回调签名联调脚本 + 重放攻击回归测试 + 安全审计记录归档。 |

## AR. api051-redis-health-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-10）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API051 后置事项已并入本分组持续跟踪。
- API051 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api051-redis-health-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api051-redis-health-callback-signature-anti-replay | 内部探针接口仍使用静态 `x-ai-internal-key`，缺签名时间窗与 nonce 防重放。 | 上线前落地 HMAC 签名（method/path/body hash + timestamp + nonce）与短窗去重校验，形成密钥轮转方案。 | 签名联调脚本 + 重放攻击回归测试 + 轮转演练记录归档。 |
| api051-redis-health-source-guard-and-rate-limit-rollout | 当前未对来源网段/可信代理做约束，接口级限频也未封板。 | 完成来源信任边界（trusted proxy 或 mTLS）与探针级限频策略，并固化误配排障 runbook。 | 预发执行 trusted/untrusted 来源对照回归 + 限频压测，归档配置快照与结果。 |
| api051-redis-ready-204-positive-path-test-coverage | 当前单测环境默认 redis disabled，仅覆盖 `/ready` 的 `401/503`，缺 `204` 正路径自动化回归。 | 增加可控的 `Enabled+ready=true` 测试桩或集成测试，补齐 `204` 正路径自动化断言。 | `cargo test -p chat-server ai_internal -- --nocapture` 中新增 `ready=204` 用例通过并归档。 |
| api051-redis-health-multi-instance-cache-consistency-evaluation | 当前缓存为进程内 2 秒快照，多实例部署下一致性策略未冻结。 | 形成多实例一致性方案评审（共享缓存、统一探针入口或保持本地缓存并文档化约束）并冻结结论。 | 多实例对照测试 + 评审纪要归档到 `docs/consistency_reports/`。 |
| api051-redis-health-observability-dashboard-baseline | 接口已补结构化日志与内存计数，但 dashboard 与告警阈值未封板。 | 建立 `redis_probe_*` 指标看板与阈值（超时率、degraded 比例、探测时延），完成一次值班演练与复盘。 | 看板配置导出 + 告警演练记录 + 值班复盘归档。 |

## AS. api073-observability-split-readiness-review-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-10）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API073 未完成项已并入本分组持续跟踪。
- API073 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api073-observability-split-readiness-review-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api073-split-review-revision-if-match-governance | 当前为单例 `UPSERT`，并发写入是“最后写覆盖”，缺少冲突提示与协同写保护。 | 落地 `revision + If-Match` 条件写（或等效版本控制），冲突返回稳定 `409` 语义，并完成前后端交互文案统一。 | route/model 回归补齐冲突场景 + 前端联调记录（刷新重试链路）归档。 |
| api073-split-review-idempotency-key-rollout-decision | 当前写接口未启用 `Idempotency-Key`，网络重试会增加审计噪声。 | 形成幂等策略 Go/No-Go 结论；若 Go，落地 key 作用域、TTL 与冲突语义并补测试。 | 压测/回放样本统计 + 评审记录；若落地则执行 `cargo test -p chat-server upsert_ops_service_split_review_should -- --nocapture` 并归档。 |
| api073-split-review-alert-outbox-async-rollout | 当前已改为 best-effort，但告警仍在同步请求路径内执行，尚未彻底 outbox 异步化。 | 完成 outbox 事件建模与 worker 派发重试落地，主写入与通知链路彻底解耦。 | 迁移脚本演练 + 故障注入回归（通知失败可补偿）+ 指标看板归档。 |
| api073-split-review-cache-consistency-evaluation | 当前 `GET` 3 秒短缓存 + `PUT` 失效在并发下仍存在短时竞态窗口。 | 形成缓存一致性 Go/No-Go 结论；若 Go，落地版本化缓存或写后回填策略并补齐回归。 | 并发读写压测与一致性对照报告归档到 `docs/consistency_reports/`。 |
| api073-split-review-audit-schema-structuring | 审计表当前缺 `action_type/request_id/source` 等结构字段，行为归因成本高。 | 完成审计 schema 增强评审并落地（如 `action_type/request_id/source`），支持后续报表与归责分析。 | 迁移脚本 + 查询回归 + 审计报表示例归档。 |

## AT. api074-observability-thresholds-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-10）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API074 延后事项已并入本分组持续跟踪。
- API074 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api074-observability-thresholds-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api074-thresholds-low-cache-hit-wire-or-remove | `lowCacheHitRateThreshold` 当前仅存储与回显，未接入告警评估，形成“可配但不生效”认知偏差。 | 完成 Go/No-Go 结论：要么接入评估链路并补齐告警规则，要么从契约中移除并完成迁移说明。 | 规则评审记录 + `cargo test -p chat-server evaluate_alert_for_rule -- --nocapture`（按最终命名）+ 学习文档同步归档。 |
| api074-thresholds-coalesced-domain-rename-cutover | `highCoalescedThreshold` 实际用于 `dlq_pending` 判定，字段语义与命名长期偏离。 | 完成字段域重命名方案（含迁移脚本、前后端契约切换、回滚策略），并冻结统一语义。 | 迁移演练 + route/model 回归 + `pnpm --dir frontend typecheck` 通过并归档。 |
| api074-thresholds-update-immediate-evaluation-decision | 当前阈值更新只落库，不会立即触发一次评估，调参反馈链路存在时延。 | 形成“写后异步触发评估”或“继续手动触发”Go/No-Go 结论；若 Go，落地异步触发与幂等保护。 | 故障注入/并发压测报告 + 评审纪要 + 回归测试归档。 |
| api074-thresholds-patch-or-config-center-evaluation | 当前仍为全量 PUT；未来阈值项扩展后，调用心智与维护成本可能上升。 | 完成 PATCH 语义或配置中心化的阶段评审结论（保持 PUT / 升级 PATCH / 配置中心），并给出迁移路径。 | 方案评审文档 + PoC 或成本评估报告归档到 `docs/consistency_reports/`。 |
| api074-thresholds-422-business-error-unification | 当前 `422` 仍依赖框架默认 Json 提取器错误，业务错误码与提示口径未统一。 | 完成提取器错误统一包装（Json/Query）与稳定业务错误码映射，并同步前端文案。 | route 回归补齐 `422` 业务码断言 + 前端错误提示联调记录归档。 |

## AU. api075-observability-anomaly-state-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-10）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API075 延后事项已并入本分组持续跟踪。
- API075 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api075-observability-anomaly-state-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api075-anomaly-state-normalization-feedback-surface | 当前归一化丢弃信息仅在日志/审计可见，响应体无 dropped 详情，调用方不易自校验。 | 形成回执增强 Go/No-Go 结论；若 Go，落地 `droppedCount/retainedCount`（或等效）并补齐前后端契约。 | route 回归补齐回执断言 + 前端联调记录 + 学习文档同步归档。 |
| api075-anomaly-state-full-put-vs-actions-boundary-decision | 全量 PUT 与单 key actions 并存，调用边界尚未冻结，存在高频误用全量接口风险。 | 完成接口职责边界评审并冻结策略（导入专用/API 权限分层/调用约束文档）。 | 评审纪要 + 权限/调用文档 + 关键场景回归记录归档。 |
| api075-anomaly-state-write-rate-limit-evaluation | API075 当前无写限频封板，热点脚本可能频繁重写单例配置行。 | 基于真实流量与压测形成写限频 Go/No-Go 结论；若 Go，落地 user/ip 写保护阈值与告警。 | 压测报告 + 阈值评审记录 + route 回归（含 `429`）归档。 |
| api075-anomaly-state-event-sourcing-evaluation | 当前为快照覆写模型，长期回放与合规审计能力上限受限。 | 完成事件源化/operation-log 方案可行性评审，明确是否进入下一阶段实施。 | 方案评审文档 + 成本评估 + PoC 结论归档到 `docs/consistency_reports/`。 |

## AV. api076-observability-anomaly-state-actions-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-10）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API076 延后事项已并入本分组持续跟踪。
- API076 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api076-observability-anomaly-state-actions-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api076-anomaly-actions-idempotency-key-rollout-decision | 当前未引入 `Idempotency-Key`，网络重试与用户连点会放大重复写与审计噪声。 | 基于真实流量与冲突样本形成 Go/No-Go 结论；若 Go，落地 key 作用域、TTL、冲突语义与回归测试。 | 压测/日志样本统计 + 评审记录；若落地则执行 `cargo test -p chat-server apply_ops_observability_anomaly_action -- --nocapture` 并归档。 |
| api076-anomaly-actions-alert-key-governance | 当前 `alertKey` 仅做非空与长度校验，缺命名规范与统一治理，存在状态碎片化风险。 | 形成告警 key 规范（命名规则/来源映射/兼容策略）并完成后端校验与文档冻结。 | 指标字典映射评审 + route/model 回归 + 学习文档同步归档。 |
| api076-anomaly-actions-event-sourcing-evaluation | 当前仍是“快照 + 审计”模型，长期回放与跨系统审计对账能力上限受限。 | 完成事件源化或 operation-log 方案可行性评审，明确是否进入下一阶段实施。 | 方案评审文档 + 成本评估 + PoC 结论归档到 `docs/consistency_reports/`。 |

## AW. api077-observability-evaluate-once-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-11）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API077 阶段剩余事项已并入本分组持续跟踪。
- API077 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api077-observability-evaluate-once-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api077-evaluate-once-recipient-policy-configurability | 当前接收人已收敛为 `owner + ops_admin + ops_reviewer`，但尚未支持按环境/班次动态配置。 | 完成接收人策略配置化方案（含默认值、越权防护、回滚策略）并落地最小可用配置入口。 | 产出方案评审纪要 + route/model 回归 + 一次值班联调记录并归档。 |
| api077-evaluate-once-rate-limit-threshold-production-tuning | preview/execute + user/ip 双维限流已落地，但阈值仍是工程初值，缺真实流量回标。 | 基于 2~4 周运行数据完成阈值复核，形成 Go/No-Go 与参数调整结论。 | 归档限流命中率、误杀率、`p95/p99` 与执行成功率报告到 `docs/loadtest/evidence/` 或 `docs/consistency_reports/`。 |

## AX. api078-observability-alerts-list-governance 后续待办（来源：当前开发计划）

整合说明（2026-04-11）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API078 未完成事项已并入本分组持续跟踪。
- API078 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api078-observability-alerts-list-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api078-alerts-list-offset-pagination-upgrade | 当前仍采用 `LIMIT/OFFSET`，深分页在数据增长后存在扫描成本放大风险。 | 完成 cursor 分页方案（`created_at + id`）评审与落地计划，形成兼容迁移与回滚路径。 | 输出方案文档 + 翻页一致性回归（无重复/漏项）+ 联调纪要归档。 |
| api078-alerts-list-sql-plan-stability-evaluation | 查询仍使用 `($N IS NULL OR ...)` 可选过滤写法，复杂过滤组合下计划稳定性与索引利用率待验证。 | 完成 SQL 计划评估结论（保持现状或动态 SQL/索引优化）并固化实现策略。 | 归档 explain 对比、典型过滤场景延迟与 CPU 指标到 `docs/consistency_reports/`。 |
| api078-alerts-list-performance-baseline-and-index-review | 尚未形成 API078 查询性能封板报告，索引优化策略未冻结。 | 完成压测基线与索引评审（是否新增复合索引）并给出 Go/No-Go 结论。 | 归档压测报告（`p95/p99`、吞吐、资源占用）与索引评审纪要到 `docs/loadtest/evidence/`。 |

## AY. api079-kafka-dlq-governance 后续待办（来源：当前开发文档）

整合说明（2026-04-12）：
- `docs/dev_plan/当前开发计划.md` 与 `docs/dev_plan/当前开发文档.md` 中 API079 阶段剩余事项已并入本分组持续跟踪。
- API079 已完成主体已并入 `docs/dev_plan/completed.md`（条目：`api079-kafka-dlq-governance-phase-closure`）。

| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|
| api079-dlq-list-real-load-baseline-and-plan-report | 当前仅本地开发环境，缺少真实流量与压测环境；现有 EXPLAIN 基线不足以替代 `p95/p99` 压测结论。 | 形成至少 3 轮真实样本压测与计划对比报告，覆盖 `COUNT/OFFSET/CURSOR` 三路径并给出索引稳定性结论。 | 归档压测报告（`p95/p99`、吞吐、资源占用）+ `EXPLAIN ANALYZE` 对比到 `docs/loadtest/evidence/` 与 `docs/consistency_reports/`。 |
| api079-dlq-retention-parameter-production-tuning | retention 默认值（`14d/500`）来自工程经验，缺线上数据支撑最优参数。 | 基于真实数据规模与清理窗口完成 `retention_days/cleanup_batch_size/interval` 调参结论，并给出回滚策略。 | 运行多轮 retention 观测，归档删除吞吐、锁等待、慢查询、表膨胀趋势与调参结论。 |
| api079-dlq-replay-discard-fault-drill-and-dashboard-baseline | 功能链路已可用，但缺值班视角故障注入与告警看板封板证据。 | 完成 replay/discard 故障注入演练，建立 `dlq_list/replay/discard/retention` 指标看板与告警阈值。 | 演练脚本与日志、告警触发记录、复盘报告归档到 `docs/consistency_reports/`。 |
| api079-kafka-readiness-replay-rate-threshold-calibration | replay-rate 门禁阈值缺稳定真实样本，当前结论偏本地实验值。 | 在真实 replay 样本基础上完成 `actions/min` 阈值校准与 Go/No-Go 冻结。 | 归档 readiness 快照对比、样本窗口统计与阈值评审纪要。 |

### C17. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| ai-judge-stage-closure-deferred-01 | ai-judge-stage-closure-execute | 环境依赖 | 真实线上压测数据驱动的容量规划 | 获得真实环境或上线前收口 | 将该延后项转为可执行模块并产出证据 | 对应脚本或报告工件归档 |
| ai-judge-stage-closure-deferred-02 | ai-judge-stage-closure-execute | 环境依赖 | 真实请求延迟分布驱动的 SLA 阈值冻结 | 获得真实环境或上线前收口 | 将该延后项转为可执行模块并产出证据 | 对应脚本或报告工件归档 |
| ai-judge-stage-closure-deferred-03 | ai-judge-stage-closure-execute | 环境依赖 | 真实用户语料驱动的公平 benchmark 冻结 | 获得真实环境或上线前收口 | 将该延后项转为可执行模块并产出证据 | 对应脚本或报告工件归档 |
| ai-judge-stage-closure-deferred-04 | ai-judge-stage-closure-execute | 环境依赖 | 基于真实成本账单的缓存/模型路由优化 | 获得真实环境或上线前收口 | 将该延后项转为可执行模块并产出证据 | 对应脚本或报告工件归档 |
| ai-judge-stage-closure-deferred-05 | ai-judge-stage-closure-execute | 环境依赖 | `Temporal` 是否优于自建 orchestrator 的真实运维评估 | 获得真实环境或上线前收口 | 将该延后项转为可执行模块并产出证据 | 对应脚本或报告工件归档 |
| ai-judge-stage-closure-deferred-06 | ai-judge-stage-closure-execute | 环境依赖 | `Milvus` 与其他向量后端的真实规模对比评估 | 获得真实环境或上线前收口 | 将该延后项转为可执行模块并产出证据 | 对应脚本或报告工件归档 |
| ai-judge-p5-real-calibration-on-env | ai-judge-p5-real-calibration-on-env | 环境依赖 | 当前执行结果为 env_blocked，真实环境未就绪 | REAL_CALIBRATION_ENV_READY=true 且可访问真实样本环境后 | 五类轨道均达到 pass，产出真实校准摘要并更新阈值结论 | bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh --root /Users/panyihang/Documents/EchoIsle |

### C18. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| `ai-judge-real-env-window-closure`（真实环境窗口补齐时复跑并更新最终结论） | ai-judge-stage-closure-execute | 环境依赖 | 当前计划建议包含真实环境模块，需在环境窗口就绪后执行收口 | REAL_CALIBRATION_ENV_READY=true 且具备可用真实样本后 | 完成该模块并产出 real-env 证据工件，状态达到 pass | 执行对应模块脚本并归档 artifacts/harness 与 docs/loadtest/evidence |

### C19. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| （无新增） | 当前延后项已写入技术债池 | （无） | （无） | （无） | （无） | （无） |

### C20. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| `ai-judge-p13-real-env-pass-window-execute-on-env` | ai-judge-stage-closure-execute | 环境依赖 | 当前计划建议包含真实环境模块，需在环境窗口就绪后执行收口 | REAL_CALIBRATION_ENV_READY=true 且具备可用真实样本后 | 完成该模块并产出 real-env 证据工件，状态达到 pass | 执行对应模块脚本并归档 artifacts/harness 与 docs/loadtest/evidence |

### C21. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| `ai-judge-p14-real-env-pass-window-execute-on-env` | ai-judge-stage-closure-execute | 环境依赖 | 当前计划建议包含真实环境模块，需在环境窗口就绪后执行收口 | REAL_CALIBRATION_ENV_READY=true 且具备可用真实样本后 | 完成该模块并产出 real-env 证据工件，状态达到 pass | 执行对应模块脚本并归档 artifacts/harness 与 docs/loadtest/evidence |

### C22. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| （无新增） | 当前延后项已写入技术债池 | （无） | （无） | （无） | （无） | （无） |

### C23. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| （无新增） | 当前延后项已写入技术债池 | （无） | （无） | （无） | （无） | （无） |

### C24. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| （无新增） | 当前延后项已写入技术债池 | （无） | （无） | （无） | （无） | （无） |

### C25. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| （无新增） | 当前延后项已写入技术债池 | （无） | （无） | （无） | （无） | （无） |

### C26. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| （无新增） | 当前延后项已写入技术债池 | （无） | （无） | （无） | （无） | （无） |

### C27. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| （无新增） | 当前延后项已写入技术债池 | （无） | （无） | （无） | （无） | （无） |

### C28. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| （无新增） | 当前延后项已写入技术债池 | （无） | （无） | （无） | （无） | （无） |

### C29. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| （无新增） | 当前延后项已写入技术债池 | （无） | （无） | （无） | （无） | （无） |

### C30. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| `ai-judge-p22-real-env-pass-window-execute-on-env`（环境阻塞） | ai-judge-stage-closure-execute | 环境依赖 | 当前计划建议包含真实环境模块，需在环境窗口就绪后执行收口 | REAL_CALIBRATION_ENV_READY=true 且具备可用真实样本后 | 完成该模块并产出 real-env 证据工件，状态达到 pass | 执行对应模块脚本并归档 artifacts/harness 与 docs/loadtest/evidence |

### C31. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| `ai-judge-p23-real-env-pass-window-execute-on-env`（真实环境窗口可用时执行） | ai-judge-stage-closure-execute | 环境依赖 | 当前计划建议包含真实环境模块，需在环境窗口就绪后执行收口 | REAL_CALIBRATION_ENV_READY=true 且具备可用真实样本后 | 完成该模块并产出 real-env 证据工件，状态达到 pass | 执行对应模块脚本并归档 artifacts/harness 与 docs/loadtest/evidence |

### C32. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| 真实环境窗口可用后再执行 `ai-judge-p24-real-env-pass-window-execute-on-env` | ai-judge-stage-closure-execute | 环境依赖 | 当前计划建议包含真实环境模块，需在环境窗口就绪后执行收口 | REAL_CALIBRATION_ENV_READY=true 且具备可用真实样本后 | 完成该模块并产出 real-env 证据工件，状态达到 pass | 执行对应模块脚本并归档 artifacts/harness 与 docs/loadtest/evidence |

### C33. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| `ai-judge-p25-real-env-pass-window-execute-on-env` | ai-judge-stage-closure-execute | 环境依赖 | 当前计划建议包含真实环境模块，需在环境窗口就绪后执行收口 | REAL_CALIBRATION_ENV_READY=true 且具备可用真实样本后 | 完成该模块并产出 real-env 证据工件，状态达到 pass | 执行对应模块脚本并归档 artifacts/harness 与 docs/loadtest/evidence |

### C34. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| `ai-judge-p26-real-env-pass-window-execute-on-env` | ai-judge-stage-closure-execute | 环境依赖 | 当前计划建议包含真实环境模块，需在环境窗口就绪后执行收口 | REAL_CALIBRATION_ENV_READY=true 且具备可用真实样本后 | 完成该模块并产出 real-env 证据工件，状态达到 pass | 执行对应模块脚本并归档 artifacts/harness 与 docs/loadtest/evidence |

### C35. AI Judge 平台化重构阶段收口（来源：当前开发计划）
| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |
|---|---|---|---|---|---|---|
| `ai-judge-p27-real-env-pass-window-execute-on-env`（仅真实环境窗口） | ai-judge-stage-closure-execute | 环境依赖 | 当前计划建议包含真实环境模块，需在环境窗口就绪后执行收口 | REAL_CALIBRATION_ENV_READY=true 且具备可用真实样本后 | 完成该模块并产出 real-env 证据工件，状态达到 pass | 执行对应模块脚本并归档 artifacts/harness 与 docs/loadtest/evidence |
