# 模块深度讲解：sse-ticket-reconnect-resilience-v1

## 元信息
- 生成时间: `2026-02-22 23:57:34 -0800`
- 分支: `main`
- 提交: `bcaf0a3`
- 讲解规范: `docs/explanation/00-讲解规范.md`
- 改动摘要: 第四模块完成：SSE 链路新增自动重连与 ticket 自动轮转，提升短时票据场景下的实时消息可用性。
- 改动文件:
- chatapp/src/store/index.js
- chatapp/src/utils.js
- chat/notify_server/src/middlewares.rs

## 讲解正文

## 1. 架构定位与边界

本模块是“可靠性层”补强，针对上一模块引入的短时 `notify ticket` 做生命周期治理。

上一模块把 URL 长期 token 风险解决了，但新引入了一个现实问题：
1. `notify ticket` 过期后，SSE 会断开。
2. 旧实现在 `onerror` 里只 `close()`，没有重连与换票。
3. 结果是实时消息链路会静默中断，直到用户刷新页面。

本模块的边界：
1. 只改 `chatapp` 的 SSE 状态机与重连逻辑。
2. 后端协议不变，仍走 `/api/tickets`。
3. 补一条 `notify_server` 中间件测试，锁定 401 语义。

## 2. 改造前问题与改造目标

### 2.1 改造前
- `initSSE` 只负责一次建连。
- 失败处理：`sse.onerror -> close`，无恢复路径。

### 2.2 改造目标
1. SSE 失败后自动重连。
2. 重连前自动刷新 `notify ticket`。
3. 防止重连风暴（指数退避 + 抖动 + 单定时器）。
4. 保持退出登录时清理连接和重连定时器。

## 3. 文件级改动地图

1. `chatapp/src/store/index.js`
- 新增状态：`sseReconnectAttempts`、`sseReconnectTimer`。
- 新增 mutation：设置重试次数和 timer。
- `initSSE` 改为：先换票、注册 `onOpen/onError` 回调。
- `closeSSE` 改为：同时清理 timer 与重试计数。
- 新增 action：`scheduleSSEReconnect`（指数退避 + jitter + 单实例调度）。

2. `chatapp/src/utils.js`
- `initSSE` 新增 `handlers` 参数。
- 支持 `onOpen` 和 `onError` 回调，把连接生命周期事件上抛给 store 状态机。

3. `chat/notify_server/src/middlewares.rs`
- 新增单测 `verify_notify_ticket_middleware_should_return_401_when_missing_query_token`，确保 query 缺 token 分支稳定返回 401。

## 4. 核心代码深讲

### 4.1 store 侧 SSE 状态机

位置：`chatapp/src/store/index.js`

1. 新状态字段（:46-47）
- `sseReconnectAttempts`：记录连续重连次数。
- `sseReconnectTimer`：保证同一时刻只有一个重连调度。

2. `initSSE`（:143-169）
- 先清理已有重连 timer（避免并发重连）。
- 调用 `refreshAccessTickets` 获取可用 `notifyToken`。
- 若已有旧连接先关闭。
- 通过 `initSSE(this, notifyToken, handlers)` 建连：
  - `onOpen`：重置重连次数为 0。
  - `onError`：触发 `scheduleSSEReconnect`。

3. `scheduleSSEReconnect`（:354-379）
- 防御条件：未登录直接返回；已有 timer 不重复调度。
- 退避计算：`min(30s, 2^(n-1) * 1s) + [0,300ms] jitter`。
- 到时后再执行 `initSSE`，失败则继续调度下一轮。

4. `closeSSE`（:170-180）
- 关闭 EventSource。
- 清理重连 timer。
- 重置重连计数，避免下次登录继承旧状态。

### 4.2 utils 侧事件回调桥接

位置：`chatapp/src/utils.js`

`initSSE` 从“纯工具函数”升级为“可回调生命周期函数”：
1. `onopen` 回调（:41-46）通知 store 连接恢复。
2. `onerror` 回调（:61-67）在 close 后通知 store 触发重连策略。

这使业务状态机（store）和传输细节（utils）职责分离。

### 4.3 中间件语义测试补强

位置：`chat/notify_server/src/middlewares.rs:109-125`

新增测试验证：当 query 中缺少 `token` 时，`verify_notify_ticket` 返回 `401 UNAUTHORIZED`。

价值：
1. 防止后续改动把“缺凭证”误变成 403/500。
2. 保证前端在错误分流时可依赖稳定语义。

## 5. 端到端恢复流程示例

以“连接成功后 ticket 过期”为例：
1. SSE 因 ticket 过期触发 `onerror`。
2. utils 关闭连接并触发 `onError` 回调。
3. store 调用 `scheduleSSEReconnect`，按指数退避安排重连。
4. 定时器触发后执行 `initSSE`。
5. `initSSE` 先 `refreshAccessTickets` 拿新 `notifyToken`。
6. 使用新 token 重建 EventSource。
7. `onopen` 回调把重连次数归零，链路恢复。

## 6. 设计取舍与替代方案

1. 为什么不是固定间隔重连？
- 固定间隔在服务端抖动时会造成重连风暴；指数退避更稳。

2. 为什么加 jitter？
- 避免多个客户端同一时刻雪崩重连。

3. 为什么在 store 做状态机而不是 utils 自治？
- store 能拿到登录态与 ticket 刷新能力，适合做全局连接编排。

4. 为什么重连前一定先 refresh ticket？
- 否则会用旧 token 连续失败，形成无效重试。

## 7. 测试验证与边界

### 7.1 已验证
1. `cargo test -p notify-server verify_notify_ticket_middleware_should_only_accept_notify_ticket_query` 通过。
2. `cargo test -p notify-server verify_notify_ticket_middleware_should_return_401_when_missing_query_token` 通过。
3. `test_change_guard.sh` 对本模块改动通过。

### 7.2 环境阻塞
1. `run_test_gate.sh --mode quick` 仍受 `utoipa-swagger-ui` 下载 github 资源失败影响（运行时网络环境限制），非本模块逻辑回归。

### 7.3 残留风险
1. 当前还没有前端自动化测试框架（vitest/jest）来回归 SSE 状态机。
2. 重连失败上限与告警策略尚未做产品化配置（目前无限重试）。

## 8. 面试深挖问答

1. 你如何避免重连风暴？
- 单 timer + 指数退避 + 抖动，且连接成功后重置计数。

2. 为什么重连逻辑放在 store？
- 需要访问登录态、ticket 刷新动作、全局连接状态，store 是天然编排层。

3. 为什么 query 缺 token 要返回 401？
- 401 表示“未提供有效凭证”，与 403 的“凭证存在但被拒绝”区分明确。

4. 这次改造的核心收益是什么？
- 把“安全改造后可能出现的可用性回退”补上，实现安全与稳定并行。

## 9. 一分钟复述稿

我在短时 ticket 方案上线后，补了一次可靠性增强：SSE 链路从“失败即终止”升级为“失败可恢复”。具体做法是把 SSE 生命周期接入 store 状态机，新增重连次数和 timer 状态，采用指数退避和抖动调度重连，并且每次重连前先刷新 notify ticket，避免旧票据反复失败。同时补了 notify 中间件缺 token 返回 401 的单测，锁定错误语义。这样可以在不牺牲安全策略的前提下，保证实时消息能力在票据过期后自动恢复。
