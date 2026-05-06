# 当前开发计划：Redis 限流优化

更新时间：2026-05-06
任务类型：refactor / optimization
当前状态：已完成

---

## 1. 计划目标

将 `chat_server` 当前 Redis 固定窗口限流升级为 **Redis Lua GCRA**，把限流能力从局部 API 保护优化为更适合真实部署和未来微服务演进的分布式流量治理底座。

本轮只优化通用限流底座，不重设所有接口阈值，不改业务权限、验证码、支付、AI Judge 合法性判断或 Ops RBAC 语义。

---

## 2. 上游设计文档

1. [Redis限流优化_意图与边界说明.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/chat_server/rate_limit/Redis限流优化_意图与边界说明.md)
2. [Redis限流优化_ADR_GCRA方案决策.md](/Users/panyihang/Documents/EchoIsle/docs/module_design/chat_server/rate_limit/Redis限流优化_ADR_GCRA方案决策.md)

执行开发前必须先阅读以上两份文档，并以其中边界为准。

---

## 3. 当前代码入口

优先检查以下代码事实：

1. `chat/chat_server/src/redis_store.rs`
   - `RedisStore::check_rate_limit`
   - `RateLimitDecision`
   - Redis 健康检查、disabled / enabled 分支

2. `chat/chat_server/src/application/request_guard.rs`
   - `enforce_rate_limit`
   - `enforce_rate_limit_with_disabled_fallback`
   - 本地 fallback bucket
   - `build_rate_limit_headers`
   - `rate_limit_exceeded_response`

3. 代表性调用方：
   - `chat/chat_server/src/handlers/auth.rs`
   - `chat/chat_server/src/handlers/debate_room.rs`
   - `chat/chat_server/src/handlers/debate_judge.rs`
   - `chat/chat_server/src/handlers/payment.rs`
   - `chat/chat_server/src/handlers/debate_ops.rs`
   - `chat/chat_server/src/handlers/debate_ops/calibration_decision.rs`

---

## 4. 开发边界

### 4.1 本轮要做

1. 用 Redis Lua GCRA 替换通用 Redis 固定窗口限流主路径。
2. 使用新 namespace 隔离旧 fixed-window key，例如 `rate_limit:gcra:{scope}`。
3. 单次 Lua 脚本完成读取、判断、写入、TTL 与返回。
4. 保持 `RateLimitDecision { allowed, limit, remaining, reset_at_epoch_secs }` 对调用方的主要语义稳定。
5. 明确并测试 Redis disabled / Redis error / auth fail-closed 场景。
6. 补充 GCRA 关键边界测试与代表性 route 回归。

### 4.2 本轮不做

1. 不引入独立 rate-limit service。
2. 不引入 API Gateway / Edge 限流。
3. 不重设所有接口限流阈值。
4. 不重写 auth、payment、judge、ops 等业务 handler。
5. 不长期保留 fixed-window 与 GCRA 双轨逻辑。
6. 不新增未明确要求的 `Retry-After` 对外契约；如实现中需要内部 `retry_after_ms`，暂不暴露为稳定 API。

---

## 5. 开发切片

### S0：开发前核验

目标：确认实现条件和风险。

任务：

1. 运行 `pre-module-prd-goal-guard`，确认本优化不偏离产品目标与安全边界。
2. 核验当前 Redis crate 的 `EVAL` 返回数组解析方式。
3. 核验 Lua 脚本内是否可用 Redis `TIME`。
4. 确认测试环境是否具备 Redis 集成测试条件；若不具备，明确用 mock / 单元测试覆盖的边界。

验收：

1. 明确时间源选择：Redis `TIME` 优先；若不可用，记录应用传入 `now_ms` 的风险。
2. 明确本地 fallback 是否同步升级为 GCRA；若继续 fixed-window，说明它只是 Redis 故障下的近似保护。

### S1：Redis GCRA 主路径

目标：实现单 bucket 的 GCRA 原子限流。

任务：

1. 在 `RedisStore::check_rate_limit` 中切换到 GCRA Lua 脚本。
2. 使用 `rate_limit:gcra:{scope}` 新 namespace，避免误读旧 fixed-window value。
3. 使用毫秒级计算：
   - `emission_interval_ms`
   - `burst_tolerance_ms`
   - `tat_ms`
   - `reset_after_ms`
4. 设置合理 TTL，确保闲置 key 自然回收。
5. 将 Lua 返回转换为 `RateLimitDecision`。

验收：

1. `limit == 0` 或 `window_secs == 0` 仍保持放行。
2. `remaining` 不为负。
3. `reset_at_epoch_secs` 不早于当前可解释时间。
4. 超出 burst 后稳定拒绝。

### S2：降级路径与安全边界

目标：保持 Redis 异常下的现有安全语义。

任务：

1. 校准 `enforce_rate_limit` 的 Redis error fallback。
2. 校准 `enforce_rate_limit_with_disabled_fallback` 的 Redis disabled fallback。
3. 检查 auth v2 短信 fail-closed 路径不被放松。
4. 对复杂边界补精简中文注释，说明 Redis 故障时保护什么风险。

验收：

1. 普通链路 Redis error 仍可本地 fallback。
2. 显式使用 disabled fallback 的链路仍受本地保护。
3. auth fail-closed 场景仍返回安全阻断，不变成 fail-open。

### S3：代表性调用方回归

目标：确认通用限流替换不会破坏主要业务链路。

任务：

1. Auth：
   - 登录限流
   - 短信发送 phone / ip 限流
   - session revoke 限流

2. Debate Room：
   - 消息发送 user / ip 限流
   - 消息列表读取限流
   - join / pin 代表路径

3. AI Judge：
   - judge request 限流
   - judge report read 限流

4. Payment / Wallet：
   - IAP verify user-global / user-transaction / ip 限流
   - wallet balance / ledger read 限流

5. Ops：
   - RBAC read/write
   - Observability evaluate once
   - Calibration decision

验收：

1. 代表性 route 仍返回 `429` 与稳定错误码。
2. `x-ratelimit-limit`、`x-ratelimit-remaining`、`x-ratelimit-reset` 均存在。
3. 权限、幂等、业务校验不因限流优化被绕过或重排。

### S4：测试补齐

目标：测试真实算法语义，而不是复制实现细节。

测试方向：

1. `RedisStore::check_rate_limit`：
   - 初始请求允许
   - burst 内允许
   - 超出 burst 拒绝
   - 等待足够时间后恢复允许
   - namespace 使用 `gcra`
   - TTL 能自然回收

2. `request_guard`：
   - Redis error fallback
   - Redis disabled fallback
   - header 非负与 reset 可解释

3. 代表性 route：
   - 至少覆盖 Auth、Debate Room、Judge、Payment、Ops 各一组限流 429 路径。

4. 并发语义：
   - 同一 key 并发请求不能突破限制。
   - 如本地无法稳定跑 Redis 并发集成测试，应在最终说明中明确未验证项。

验收：

1. 新增或修改测试必须验证业务契约和真实限流边界。
2. 不允许通过删断言、放宽 matcher、skip/ignore 或 test-only 分支制造绿灯。
3. 优先比较完整对象或完整 response 关键结构，而不是逐字段复制生产算法。

### S5：文档与收口

目标：开发完成后同步必要文档与证据。

任务：

1. 判断 `docs/architecture/README.md` 是否需要更新。
   - 若只是 `redis_store.rs` 内部算法替换，通常不影响第一跳定位，不更新。
   - 若新增共享限流模块、crate 或主入口变化，则更新代码地图。

2. 更新当前计划状态与验证结果。
3. 如开发中偏离 ADR，需要回写 ADR 决策变更。
4. 使用 `post-module-test-guard` 运行合适测试门禁。
5. 使用 `post-optimization-plan-sync` 回写优化计划状态。

验收：

1. 最终回复说明实际运行的测试。
2. 最终回复说明新增/修改测试保护了哪些真实行为。
3. 最终回复说明架构图是否更新及原因。

---

## 6. 验收矩阵

| 维度 | 必须验证 | 代表证据 |
| --- | --- | --- |
| 平滑限流 | 固定窗口边界不再允许短时间双倍突刺 | GCRA 单元/集成测试 |
| burst | 合理 burst 内允许，超出后拒绝 | `check_rate_limit` 测试 |
| 原子性 | Redis 主路径单次 Lua 决策 | 代码审查 + 并发测试 |
| Header | limit / remaining / reset 存在且非负可解释 | route 测试 |
| 错误契约 | 仍返回 429 和稳定错误码 | route 测试 |
| Redis disabled | disabled fallback 行为不退化 | request_guard 测试 |
| Redis error | 普通链路本地 fallback 生效 | request_guard 测试 |
| auth fail-closed | 短信安全链路不放松 | auth 测试 |
| 多模块调用 | Auth / Room / Judge / Payment / Ops 代表路径稳定 | targeted cargo test |
| 文档收口 | ADR 偏差已回写，架构图按需判断 | 文档 diff |

---

## 7. 建议运行命令

开发前：

```bash
bash skills/pre-module-prd-goal-guard/scripts/run_prd_goal_guard.sh --module chat_server --task redis-rate-limit-gcra
```

实现后优先运行：

```bash
cargo fmt --all
cargo test -p chat-server rate_limit
cargo test -p chat-server request_rate_limit
cargo test -p chat-server auth_sms
cargo test -p chat-server debate_room
cargo test -p chat-server judge
cargo test -p chat-server payment
cargo test -p chat-server ops_rbac
```

最终按变更范围运行：

```bash
bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full
```

说明：

1. 实际命令需按仓库当前测试命名调整。
2. 若 Redis 集成环境不可用，必须在最终说明中列出未验证风险。
3. 不运行 Python 命令；如后续确需运行 Python，必须先执行 `python-venv-guard` 并使用项目指定虚拟环境解释器。

---

## 8. 风险与回滚判断

### 8.1 可接受风险

1. 切换到 `rate_limit:gcra:{scope}` 后，旧 fixed-window key 不再参与判断，第一窗口内可能出现少量额度重置。
2. `x-ratelimit-reset` 语义从“固定窗口 TTL 结束”变为“预计下一次可接受或恢复时间”。
3. 本地 fallback 若不升级为 GCRA，Redis 故障时与主路径存在近似差异。

### 8.2 不可接受风险

1. 短信验证码、登录、支付、AI Judge 高成本操作保护强度下降。
2. 限流超限不返回 429。
3. Redis 脚本错误导致所有普通请求失败。
4. Header 出现负数、时间倒退或不可解析值。
5. 新增长期 fixed-window / GCRA 双轨兼容层且没有移除条件。

### 8.3 回滚判断

如果 GCRA 主路径在测试或本地联调中出现不可控错误：

1. 优先修正脚本和解析逻辑。
2. 若无法在本轮完成，回退代码到 fixed-window 主路径。
3. 保留 ADR 与计划，记录阻塞原因，不留下半切换状态。

---

## 9. 完成定义

本任务完成需同时满足：

1. Redis 主限流算法已切换为 Lua GCRA。
2. 代表性业务链路的 429、header、降级、安全边界均有测试或明确运行证据。
3. `cargo fmt --all` 通过。
4. 合适范围的 `cargo test` 或 test gate 通过；如有未运行项，原因和风险已说明。
5. 文档已按实际实现回写。
6. 已判断 `docs/architecture/README.md` 是否需要更新。

---

## 10. 执行记录

### 2026-05-06：Redis Lua GCRA 主路径已落地

完成内容：

1. `RedisStore::check_rate_limit` 已从 `INCR` + `EXPIRE` + `TTL` 固定窗口切换为 Redis Lua GCRA。
2. Redis 限流 key 已切换到 `rate_limit:gcra:{scope}` namespace，避免误读旧 fixed-window 短 TTL value。
3. Lua 脚本使用 Redis `TIME` 作为时间源，并在单次 `EVAL` 内完成读取、判断、写入、TTL 与返回。
4. 本地 fallback 已从固定窗口升级为近似 GCRA，保持 Redis error / disabled fallback 下的平滑保护。
5. `RateLimitDecision` 对调用方保持原结构：`allowed`、`limit`、`remaining`、`reset_at_epoch_secs`。
6. 未新增 `Retry-After` 对外契约，未重设各业务接口阈值。

验证结果：

1. `pre-module-prd-goal-guard` summary 模式通过，输出 `artifacts/harness/redis-rate-limit-gcra-prd-guard.env`。
2. 本机 Redis 验证 Lua `TIME` 可用。
3. 本机 Redis 验证生产 GCRA Lua 脚本：`limit=3/window=3s` 时前三次允许、第四次拒绝，等待约一个 emission interval 后恢复允许。
4. `cargo fmt --all` 通过。
5. `cargo test -p chat-server gcra_fallback` 通过。
6. `cargo test -p chat-server request_guard` 通过。
7. `cargo test -p chat-server redis_store` 通过。
8. `cargo test -p chat-server rate_limit` 通过，覆盖 Auth、Debate Room、Payment、Ops 等代表性 429/header 回归。
9. `cargo test -p chat-server judge` 通过，覆盖 Judge 高成本链路与相关 route/model 回归。
10. `bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full` 通过：chat 764 tests passed、3 skipped；swiftide-pgvector check/clippy/nextest 通过；desktop tauri check/clippy/nextest 24 tests passed。

架构图判断：

1. 本次只替换 `chat_server` 内部 Redis 限流算法与本地 fallback 数据结构。
2. 未新增 workspace/package、主入口、handler/service/domain 第一跳位置或跨层调用入口。
3. `docs/architecture/README.md` 不需要更新。

---

## 11. 优化回写记录（自动）

### 2026-05-05 22:52:07 | redis-rate-limit-gcra
- 阶段: S5
- 完成状态: 已完成
- 本次摘要: Redis Lua GCRA限流主路径、fallback与测试门禁已完成
- 调整原因: 无
- 下一步建议: 全部阶段已完成，进入上线前稳定性与性能优化。
