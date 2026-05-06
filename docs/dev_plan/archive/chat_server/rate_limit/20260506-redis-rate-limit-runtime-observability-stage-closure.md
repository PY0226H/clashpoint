# 当前开发计划：Redis 限流运行态可观测性

关联 slot：`default`
更新时间：2026-05-06
任务类型：refactor / observability
当前状态：已完成

---

### 已完成/未完成矩阵

| 模块 | 阶段 | 状态 | 说明 |
| --- | --- | --- | --- |
| chat-server-rate-limit-metrics-prd-guard | S0 | 已完成 | 已运行 PRD/product-goals 对齐，确认运行态可观测性不偏离上线安全边界 |
| chat-server-rate-limit-runtime-metrics-model | S1 | 已完成 | 已新增全局与 scope 级限流指标模型，不记录 raw key / user / IP |
| chat-server-rate-limit-request-guard-observe | S2 | 已完成 | 已在通用限流入口统一记录 Redis / fallback / disabled fallback outcome |
| chat-server-rate-limit-internal-metrics-endpoint | S3 | 已完成 | 已新增 internal key 保护的 `/api/internal/ai/infra/rate-limit/metrics` |
| chat-server-rate-limit-metrics-tests | S4 | 已完成 | 已补指标模型、request_guard 与 ai_internal handler 回归 |
| chat-server-rate-limit-metrics-stage-closure | S5 | 已完成 | 已运行测试门禁、同步计划与架构地图更新判断 |

---

## 1. 计划目标

在已落地的 Redis Lua GCRA 与 explicit burst 策略之上，补齐 `chat_server` 通用限流的运行态可观测性闭环。

本阶段目标是让上线前调参有事实依据：能回答“哪个 scope 被限流最多”“Redis 主路径和本地 fallback 各自表现如何”“哪些 scope 已接近限流边界”。本阶段不调整任何现有 `limit/window/burst` 参数，也不做热更新或动态配置。

---

## 2. 上游设计文档

开发前优先阅读：

1. [Redis限流优化_意图与边界说明.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/chat_server/rate_limit/Redis限流优化_意图与边界说明.md)
2. [Redis限流优化_ADR_GCRA方案决策.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/chat_server/rate_limit/Redis限流优化_ADR_GCRA方案决策.md)
3. [Redis限流优化_参数策略梳理.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/chat_server/rate_limit/Redis限流优化_参数策略梳理.md)
4. [Redis限流优化_Burst策略开发计划.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/chat_server/rate_limit/Redis限流优化_Burst策略开发计划.md)
5. [Redis限流优化_可观测性与运行期调参设计.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/chat_server/rate_limit/Redis限流优化_可观测性与运行期调参设计.md)

---

## 3. 当前代码入口

优先检查以下代码事实：

1. `chat/chat_server/src/application/request_guard.rs`
   - `enforce_rate_limit`
   - `enforce_rate_limit_with_disabled_fallback`
   - `local_rate_limit_fallback_decision`
   - `build_rate_limit_headers`
   - `rate_limit_exceeded_response`

2. `chat/chat_server/src/redis_store.rs`
   - `RedisStore::check_rate_limit`
   - `RateLimitDecision`
   - `rate_limit_burst_limit_for_scope`

3. `chat/chat_server/src/lib.rs`
   - `AppStateInner`
   - `AppState::try_new_with_bootstrap`
   - `AppState::new_for_unit_test`

4. `chat/chat_server/src/handlers/ai_internal.rs`
   - Redis health internal endpoint
   - AI dispatch metrics internal endpoint
   - auth consistency metrics internal endpoint

5. `chat/chat_server/src/openapi.rs`
   - internal endpoint 注册
   - schema 注册

---

## 4. 开发边界

### 4.1 本阶段要做

1. 新增通用 `RateLimitRuntimeMetrics`，聚合全局与 scope 级限流指标。
2. 在通用限流入口统一 observe，不要求每个 handler 单独埋点。
3. 指标区分 Redis 主路径、Redis error 后 fallback、Redis disabled fallback。
4. 指标只按 `scope` 聚合，不记录 raw key、手机号、邮箱、交易号、IP 或 user id。
5. 新增内部接口：

```text
GET /api/internal/ai/infra/rate-limit/metrics
```

6. 复用 internal key 认证边界。
7. 补 OpenAPI schema 与 handler 注册。
8. 补指标单元测试与 internal endpoint 权限/响应测试。

### 4.2 本阶段不做

1. 不调整任何 `limit/window/burst` 参数。
2. 不把限流策略配置化。
3. 不做热更新、shadow mode、双轨限流或灰度策略。
4. 不引入 Prometheus exporter。
5. 不把指标落库。
6. 不扫描 Redis key。
7. 不改变现有 429 响应体、错误码或 rate-limit headers。
8. 不把 internal metrics endpoint 暴露给普通用户或 Ops UI。

---

## 5. 开发切片

### S0：开发前核验

目标：确认指标边界和测试入口。

任务：

1. 运行 `pre-module-prd-goal-guard`，确认本阶段可观测性优化不偏离产品目标与安全边界。
2. 复核 `request_guard.rs` 当前 GCRA fallback 与 Redis 主路径 outcome。
3. 复核 `ai_internal.rs` 现有 internal endpoint 测试风格。
4. 确认输出 DTO 不包含 raw key / user id / IP。

验收：

1. 明确指标模块位置。
2. 明确 endpoint 路由和 OpenAPI 注册点。
3. 明确测试命名与最小覆盖面。

### S1：指标模型

目标：建立可快照的限流运行态指标。

任务：

1. 新增全局指标字段：
   - `request_total`
   - `allowed_total`
   - `rejected_total`
   - `redis_allowed_total`
   - `redis_rejected_total`
   - `fallback_allowed_total`
   - `fallback_rejected_total`
   - `redis_error_total`
   - `redis_disabled_fallback_total`
   - `near_limit_total`

2. 新增 scope 级指标字段：
   - `scope`
   - `limit`
   - `window_secs`
   - `burst_limit`
   - `request_total`
   - `allowed_total`
   - `rejected_total`
   - `fallback_total`
   - `redis_error_total`
   - `near_limit_total`
   - `last_rejected_at_ms`
   - `last_redis_error_at_ms`

3. 输出 DTO 使用 `camelCase`。
4. scope 为空时归一为 `unknown`。

验收：

1. 指标 snapshot 稳定、可序列化。
2. 不输出任何 key 级、用户级或 IP 级信息。
3. near-limit 初始定义为：允许但 `remaining == 0`。

### S2：通用限流入口埋点

目标：所有通用限流调用自动产出运行态指标。

任务：

1. `enforce_rate_limit` 成功走 Redis 主路径时记录 Redis outcome。
2. `enforce_rate_limit` Redis error 后走本地 fallback 时记录 Redis error 与 fallback outcome。
3. `enforce_rate_limit_with_disabled_fallback` Redis disabled 时记录 disabled fallback outcome。
4. 指标记录时写入最近一次 `limit/window/burst`。
5. Redis error 日志补充必要结构化字段，但不记录 raw key。

验收：

1. Redis allowed/rejected 可区分。
2. fallback allowed/rejected 可区分。
3. Redis error 与 disabled fallback 不混淆。
4. 现有 429 响应契约不变。

### S3：Internal Metrics Endpoint

目标：提供内部可查询的限流运行态快照。

任务：

1. 新增 `AppState::get_rate_limit_metrics` 或等价方法。
2. 新增 `get_rate_limit_metrics_handler`。
3. 注册路由：

```text
/api/internal/ai/infra/rate-limit/metrics
```

4. 复用 internal key middleware。
5. 在 `openapi.rs` 注册 handler 与 DTO schema。

验收：

1. 无 internal key 返回 401。
2. 有 internal key 返回 200 和完整快照。
3. 空指标时返回合法空数组，不返回 500。

### S4：测试补齐

目标：测试真实指标语义，而不是复制内部实现细节。

测试方向：

1. 指标模型：
   - Redis allowed / rejected 累计正确。
   - fallback allowed / rejected 累计正确。
   - Redis error 与 disabled fallback 分桶正确。
   - near-limit 仅在 allowed 且 remaining 为 0 时增加。

2. request guard：
   - Redis disabled fallback 产生 metrics。
   - fallback 429 不改变原有错误语义。

3. internal endpoint：
   - 401 边界。
   - 200 快照结构。
   - scope 输出不包含 raw key。

4. 代表性 route：
   - 至少执行 `rate_limit` 或已有 429 回归组，确认现有契约不变。

验收：

1. 不新增 test-only 生产分支。
2. 不通过删断言、放宽 matcher 或 skip 制造绿灯。
3. 优先比较完整输出对象或稳定 JSON 结构。

### S5：文档与收口

目标：完成本阶段证据同步。

任务：

1. 判断 `docs/architecture/README.md` 是否需要更新。
   - 若新增 metrics 只是挂在现有 `application/request_guard` 与 internal endpoint 上，通常不影响第一跳定位。
   - 若新增独立模块成为新的第一跳入口，则同步代码地图。

2. 更新当前计划执行记录。
3. 如实现偏离设计文档，回写设计文档。
4. 运行合适范围测试。
5. 使用 `post-optimization-plan-sync` 回写计划状态。
6. 使用 `post-module-commit-message` 输出 commit message 推荐。

验收：

1. 最终回复说明实际运行测试。
2. 最终回复说明新增测试保护了哪些真实行为。
3. 最终回复说明架构图是否更新及原因。

---

## 6. 验收矩阵

| 维度 | 必须验证 | 代表证据 |
| --- | --- | --- |
| 指标安全 | 不输出 raw key / user id / IP | DTO 测试、handler 响应断言 |
| Redis 主路径 | allowed/rejected 分桶正确 | metrics 单元测试 |
| Redis error | error 后 fallback 被单独计数 | request_guard 测试 |
| Redis disabled | disabled fallback 被单独计数 | request_guard 测试 |
| near limit | allowed 且 remaining 为 0 才计数 | metrics 单元测试 |
| internal 鉴权 | 无 internal key 为 401 | ai_internal handler 测试 |
| 响应契约 | 现有 429/header 不变 | rate_limit 代表测试 |
| OpenAPI | handler/schema 已注册 | openapi 编译与测试 |
| 文档收口 | 设计偏差已回写 | 文档 diff |

---

## 7. 建议运行命令

开发前：

```bash
bash skills/pre-module-prd-goal-guard/scripts/run_prd_goal_guard.sh --root /Users/panyihang/Documents/EchoIsle --task-kind refactor --module chat_server --summary '为Redis Lua GCRA限流增加运行态可观测性' --mode summary --metadata-out artifacts/harness/redis-rate-limit-metrics-prd-guard.env
```

实现后优先运行：

```bash
cargo fmt --all
cargo test -p chat-server rate_limit_metrics
cargo test -p chat-server request_guard
cargo test -p chat-server ai_internal
cargo test -p chat-server rate_limit
```

最终按变更范围运行：

```bash
bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full
```

说明：

1. 实际命令需按最终测试命名调整。
2. 本阶段不运行 Python 命令；如后续确需运行 Python，必须先执行 `python-venv-guard` 并使用项目指定虚拟环境解释器。

---

## 8. 风险与回滚判断

### 8.1 可接受风险

1. 进程内指标在服务重启后归零。
2. 多实例部署时各实例指标暂不自动聚合。
3. 第一阶段不输出 p95/p99，只输出计数和最近时间。

### 8.2 不可接受风险

1. 指标泄漏 raw key、用户标识、手机号、邮箱、交易号或 IP。
2. 指标锁竞争导致限流路径显著变慢。
3. internal metrics endpoint 绕过 internal key。
4. 现有限流 429 契约、header 或业务权限被改变。
5. 为了测试增加 test-only 生产语义。

### 8.3 回滚判断

如果指标接入导致限流主路径不稳定：

1. 优先修复指标记录实现。
2. 若无法快速修复，移除 observe 调用，保留指标类型和 endpoint 草稿。
3. 不回退 Redis Lua GCRA 算法本身。

---

## 9. 完成定义

本任务完成需同时满足：

1. 通用限流运行态指标已落地。
2. internal metrics endpoint 已落地并受 internal key 保护。
3. 指标不包含 key/user/IP 等高基数字段。
4. 现有限流响应契约保持不变。
5. 专项测试与合适范围 test gate 通过。
6. 已判断 `docs/architecture/README.md` 是否需要更新。

---

## 10. 执行记录

### 2026-05-06：Redis 限流运行态可观测性已落地

完成内容：

1. 新增 `RateLimitRuntimeMetrics`，提供全局与 scope 级运行态快照，覆盖 Redis 主路径、Redis error 后 fallback、Redis disabled fallback 与 near-limit 计数。
2. `request_guard` 通用限流入口已统一埋点，handler 无需逐个重复记录。
3. 新增 internal endpoint：`GET /api/internal/ai/infra/rate-limit/metrics`，复用 internal key 认证边界。
4. OpenAPI 已注册 handler 与 DTO schema。
5. 指标输出仅按 scope 聚合，不包含 raw key、user id、IP、手机号、邮箱或交易号；Redis error 日志也不再输出 raw key。

验证结果：

1. `pre-module-prd-goal-guard` summary 模式通过，输出 `artifacts/harness/redis-rate-limit-metrics-prd-guard.env`。
2. `cargo fmt --all` 通过。
3. `cargo test -p chat-server rate_limit_runtime_metrics` 通过。
4. `cargo test -p chat-server enforce_rate_limit_with_disabled_fallback_should_record_runtime_metrics` 通过。
5. `cargo test -p chat-server get_rate_limit_metrics_handler_should_require_internal_key_and_return_snapshot` 通过。
6. `cargo test -p chat-server request_guard` 通过。
7. `cargo test -p chat-server ai_internal` 通过。
8. `cargo test -p chat-server rate_limit` 通过。
9. `cargo test -p chat-server redis_store` 通过。
10. `bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full` 通过：chat 772 tests passed、3 skipped、1 leaky；swiftide-pgvector 通过；desktop tauri 24 tests passed。
11. `git diff --check` 通过。
12. `bash scripts/quality/harness_docs_lint.sh` 曾因 `default` slot 串到 `docs/dev_plan/active/user-debate-assistant.md` 未通过；当前 `default` slot 已恢复指向本计划，剩余 lint 阻塞属于 `user-debate-assistant` 独立 slot 的活动计划结构，不属于本轮 Redis 限流收口范围。

架构图判断：

1. 本次新增 `application/rate_limit_metrics.rs`，并新增 internal metrics endpoint。
2. 该能力已成为后续排查 Redis / 限流 / 运行态指标的第一跳入口。
3. 已更新 `docs/architecture/README.md` 的 Redis / 限流入口。

---

## 11. 下一步

### 下一开发模块建议

1. 进入 `chat-server-rate-limit-runtime-config-and-real-traffic-tuning`：用 internal metrics 与压测样本形成 scope 级调参报告。
2. 若真实部署前需要可配置策略，再设计启动时限流参数覆盖与安全上限校验；暂不做热更新或跨服务统一策略表。
3. 多实例部署前补充“指标聚合与看板方案”ADR，避免把单实例进程内指标误读为全局流量状态。

### 模块完成同步历史

- 2026-05-06：完成 Redis 限流 GCRA / explicit burst 阶段收口，归档旧活动计划，并生成本阶段“运行态可观测性”开发计划。

---

## 12. 优化回写记录（自动）

### 2026-05-05 23:46:59 | redis-rate-limit-runtime-metrics
- 阶段: S5
- 完成状态: 已完成
- 本次摘要: Redis限流运行态metrics与internal endpoint已完成
- 调整原因: 无
- 下一步建议: 全部阶段已完成，进入上线前稳定性与性能优化。

---

## 13. 阶段收口结论

### 2026-05-06：暂停 rate limit 开发，等待真实环境证据

结论：

1. `chat_server` Redis 限流底座、GCRA 主链、explicit burst、fallback 对齐、运行态 metrics、internal 查询接口、OpenAPI、测试与本地设计闭环均已完成。
2. 已补充 `Redis限流优化_运行态调参与压测基线方案.md`，明确后续只应基于 scope 级 metrics、压测样本和真实流量证据调参。
3. 当前没有 staging / Beta / production 真实运行窗口、真实流量样本、多实例指标汇总或 dashboard 证据，因此不得继续调整 `limit/window/burst`，不得宣称 real-env tuning 已完成。
4. rate limit 开发线进入暂停状态，后续只在真实环境证据齐备后重开 `chat-server-rate-limit-real-env-evidence-and-tuning`。

收口状态：

```text
local_foundation_ready
real_env_evidence_blocked
rate_limit_dev_paused
```
