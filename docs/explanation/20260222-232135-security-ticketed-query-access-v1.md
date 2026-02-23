# 模块深度讲解：security-ticketed-query-access-v1

## 元信息
- 生成时间: `2026-02-22 23:21:35 -0800`
- 分支: `main`
- 提交: `7110347`
- 讲解规范: `docs/explanation/00-讲解规范.md`
- 改动摘要: 第三模块完成：SSE 与文件下载链路引入短时 audience ticket，替换 URL 上长期用户 token；后端新增 /api/tickets，前端改为先换票再建连/取文件。
- 改动文件:
- chat/chat_core/src/utils/jwt.rs
- chat/chat_server/src/handlers/ticket.rs
- chat/chat_server/src/middlewares/ticket.rs
- chat/chat_server/src/lib.rs
- chat/chat_server/src/openapi.rs
- chat/notify_server/src/middlewares.rs
- chat/notify_server/src/lib.rs
- chatapp/src/store/index.js
- chatapp/src/utils.js
- chatapp/src/components/MessageList.vue
- chat/chat_test/tests/chat.rs

## 讲解正文

## 1. 架构定位与边界

本模块属于“鉴权传输层治理”，目标是收敛仍残留在 URL 上的长期用户 token，覆盖两条典型链路：
1. 实时通知：`notify_server /events`（EventSource 只能原生用 URL 建连）。
2. 文件下载：`chat_server /api/files/:ws_id/*path`（`img/src` 等浏览器资源请求无法自定义 Authorization 头）。

改造后形成三层鉴权模型：
1. 业务 API：继续使用 Header-only 用户 token（上一模块已完成）。
2. URL 受限链路（SSE/file）：改用短时、受众隔离（audience-scoped）的 access ticket。
3. 核心 JWT 验证：通过 audience 做 token 类型隔离，阻断“用户 token 直接塞 URL”的路径。

## 2. 改造前问题与改造目标

### 2.1 改造前问题
1. 前端 SSE 建连使用 `?token=<user-token>`（`chatapp/src/utils.js:34` 旧逻辑）。
2. 前端文件 URL 拼接使用 `?token=<user-token>`（`chatapp/src/components/MessageList.vue:81` 与 `chatapp/src/store/index.js:230` 旧逻辑）。
3. `notify_server` 与 `chat_server /files` 都允许 query token 直接走用户态 JWT 验证。

风险：长期用户 token 容易在 URL 日志、代理、历史记录、错误监控里泄露。

### 2.2 改造目标
1. 新增 `/api/tickets`，由已登录用户换取短时 ticket。
2. file/SSE query 链路只接受对应 audience 的 ticket。
3. 前端统一先换票，再用 ticket 拼 URL。
4. 兼容现有业务 API 的 Header-only 体系，不回退。

### 2.3 非目标
1. 本次不实现“按文件 path 绑定 ticket”。
2. 本次不引入 Redis 等外部票据存储，保持无状态 JWT ticket。
3. 本次不重写 EventSource 为自定义流式协议。

## 3. 文件级改动地图

1. `chat/chat_core/src/utils/jwt.rs`
- 增加 audience 常量：用户 token、file ticket、notify ticket。
- 增加签发接口：`sign_with_audience` / `sign_file_ticket` / `sign_notify_ticket`。
- 增加验签接口：`verify_file_ticket` / `verify_notify_ticket`。
- 增加单测验证 audience 隔离。

2. `chat/chat_server/src/handlers/ticket.rs`（新增）
- 新增 `/api/tickets` 处理器，签发 file/notify 双 ticket。
- 返回 `AccessTicketsOutput`（`fileToken`、`notifyToken`、`expiresInSecs`）。

3. `chat/chat_server/src/middlewares/ticket.rs`（新增）
- 新增 `verify_file_ticket`：query-only 提取 ticket，按 file audience 验签并注入 `User`。
- 明确状态码：缺参/解析失败 401，验签失败 403。

4. `chat/chat_server/src/lib.rs`
- 受保护 API 增加 `POST /api/tickets`。
- 文件路由从 permissive `verify_token` 切换为 `verify_file_ticket`。

5. `chat/chat_server/src/openapi.rs`
- OpenAPI paths 和 schema 注册新增 ticket API。

6. `chat/notify_server/src/middlewares.rs`（新增）
- 新增 `verify_notify_ticket`：query-only + notify audience 验签。

7. `chat/notify_server/src/lib.rs`
- `/events` 中间件改为 `verify_notify_ticket`。

8. `chatapp/src/store/index.js`
- 新增 `accessTickets` 状态。
- 新增 `refreshAccessTickets`（缓存 + 提前 30s 刷新）。
- `initSSE` 改为先换票再建连。
- 文件上传后 preview URL 改用 `fileToken`。

9. `chatapp/src/utils.js`
- `initSSE` 改为显式接收 `notifyTicket`。

10. `chatapp/src/components/MessageList.vue`
- `getFileUrl` 改为使用 `accessTickets.fileToken`。

11. `chat/chat_test/tests/chat.rs`
- 集成测试新增 `create_access_tickets`，notify 连接改用 `notifyTicket`。

## 4. 核心代码深讲

### 4.1 JWT audience 隔离（核心机制）

位置：`chat/chat_core/src/utils/jwt.rs`

1. 新增三个 audience 常量（:6-8）：
- `chat_web`：用户 token（Header 主业务）。
- `chat_file_ticket`：文件链路 query ticket。
- `chat_notify_ticket`：SSE 链路 query ticket。

2. 新增通用签发函数 `sign_with_audience`（:24-33）：
- 输入：`User` claim、audience、TTL。
- 行为：带统一 issuer + 指定 audience 签发 JWT。
- 意义：把“token 类型”建模到 JWT 元数据层。

3. 新增类型化便捷方法（:35-49）：
- `sign_file_ticket` / `sign_notify_ticket`。

4. 验签侧新增 audience 约束（:65-89）：
- `verify_with_audience` 内部绑定 allowed audience。
- `verify_file_ticket` 与 `verify_notify_ticket` 分别固定 audience。

结果：同一个 user claim，不同 audience 的 token 无法互相冒用。

### 4.2 ticket 签发 API

位置：`chat/chat_server/src/handlers/ticket.rs`

1. 入口 `create_access_tickets_handler`（:27-43）：
- 前置：路由层已通过 Header-only 用户鉴权。
- 输入：`Extension<User>`。
- 输出：`fileToken` + `notifyToken` + `expiresInSecs`。

2. TTL 设定（:7）：
- 当前 10 分钟，属于“短时票据”。

3. 错误传播：
- 签发失败通过 `?` 进入 `AppError` 链路，统一响应。

### 4.3 文件下载 query 链路中间件

位置：`chat/chat_server/src/middlewares/ticket.rs`

执行路径：
1. 仅从 query 提取 `token`（:22）。
2. query 解析失败 -> `401 UNAUTHORIZED`（:25-28）。
3. 用 `verify_file_ticket` 验签（:31-37）。
4. audience 不匹配或 token 无效 -> `403 FORBIDDEN`。
5. 验签成功后注入 `User` 到 request extensions（:40-42）。

关键语义：
- 用户 token（aud=`chat_web`）即使放在 query，也会因 audience 不匹配被拒绝。

### 4.4 notify SSE query 链路中间件

位置：`chat/notify_server/src/middlewares.rs`

逻辑与 file middleware 对称：
1. query-only 取 token。
2. 用 `verify_notify_ticket` 验签。
3. 401/403 语义一致。

对称设计的价值：
- 两条 URL 鉴权链路共享同一安全模型，排错和维护成本更低。

### 4.5 路由挂载点改造

1. `chat_server`：`/api/tickets` 放在 `protected_api`（`chat/chat_server/src/lib.rs:77-85`）。
2. `chat_server`：`/api/files` 切到 `verify_file_ticket`（`chat/chat_server/src/lib.rs:86-88`）。
3. `notify_server`：`/events` 切到 `verify_notify_ticket`（`chat/notify_server/src/lib.rs:55-58`）。

## 5. 前端链路改造

位置：`chatapp/src/store/index.js` + `chatapp/src/utils.js` + `chatapp/src/components/MessageList.vue`

1. 新增 ticket 状态缓存（`accessTickets`）与刷新动作（`refreshAccessTickets`，`index.js:306-329`）。
2. `initSSE` 改为先刷新 ticket，再调用 `initSSE(this, notifyToken)`（`index.js:135-149` + `utils.js:32-35`）。
3. 文件 URL 改为使用 `fileToken`（`index.js:244-247`，`MessageList.vue:80-83`）。

工程意义：
- 前端对后端 ticket 机制“显式依赖”，避免隐藏式回退到长期 token。

## 6. 端到端流程示例

以“登录后接收实时消息 + 查看图片”为例：
1. 用户登录拿到 Header 用户 token（`chat_web`）。
2. 前端调用 `POST /api/tickets`（Header 带用户 token）。
3. 后端返回 `fileToken` 与 `notifyToken`（短时 + audience 隔离）。
4. 前端用 `notifyToken` 建立 EventSource：`/events?token=...`。
5. notify_server 仅按 `chat_notify_ticket` audience 验签后推送事件。
6. 前端渲染消息图片时，用 `fileToken` 组装 `/api/files/...?...`。
7. chat_server 仅按 `chat_file_ticket` audience 验签并返回文件。

## 7. 设计取舍与替代方案

### 7.1 为什么用 audience 分隔，而不是单纯短 TTL
1. 仅短 TTL 不能阻止“用户 token 被塞进 URL”。
2. audience 分隔能在服务端硬性拒绝错误 token 类型。
3. 配合短 TTL 才形成“可泄露面更小 + 类型可控”的组合。

### 7.2 为什么不做服务端状态化 ticket（Redis）
1. 当前优先低入侵改造，JWT 无状态即可满足阶段目标。
2. 状态化方案可支持吊销/一次性使用，但实现和运维成本更高。
3. 后续如果需要强吊销再升级，不阻塞当前上线节奏。

## 8. 测试验证与边界

### 8.1 已验证
1. `chat-core`：`audience_scoped_ticket_should_work` 通过。
2. `chat-server`：
- `create_access_tickets_should_return_audience_scoped_tickets` 通过。
- `verify_file_ticket_middleware_should_only_accept_file_ticket_query` 通过。
3. `notify-server`：`verify_notify_ticket_middleware_should_only_accept_notify_ticket_query` 通过。
4. `chat_test`：`cargo test -p chat_test --no-run` 通过（编译层验证）。
5. `test_change_guard.sh` 通过。

### 8.2 未完全通过项
1. `run_test_gate.sh --mode quick` 在当前运行时仍因 `utoipa-swagger-ui` 下载 github 资源失败（环境外网问题），非本模块业务回归。

### 8.3 残留风险
1. ticket 当前未绑定具体文件 path，若 ticket 泄露仍可在有效期内访问同 workspace 文件。
2. 前端当前是“缓存 + 提前刷新”策略，未实现请求级自动重试换票。

## 9. 面试深挖问答

1. 为什么 EventSource 还用了 query？
- 浏览器原生 EventSource 不支持自定义 Authorization header，因此需要受控 query ticket。

2. 为什么要把 file 和 notify 拆成两个 audience？
- 最小权限原则：不同链路拿不同票据，避免票据横向复用。

3. 为什么返回 401 和 403 两种状态？
- 401 表示凭证缺失/载体错误；403 表示凭证存在但校验失败或 audience 不匹配。

4. 这次改造如何控制回归风险？
- 仅改 URL 鉴权链路，主业务 Header-only 逻辑不变；并为签发与两条中间件补了专门测试。

## 10. 一分钟复述稿

我把剩余 URL token 风险链路做了统一治理。核心做法是引入短时 access ticket，并用 JWT audience 把 token 类型强隔离：`chat_web` 只给 Header 主业务，`chat_file_ticket` 只给文件 URL，`chat_notify_ticket` 只给 SSE URL。后端新增 `/api/tickets` 签发票据，`chat_server` 和 `notify_server` 分别上了 query-only 的票据中间件，拒绝用户 token 直接上 URL。前端改成先换票再建连 SSE 和拼文件 URL。这样既兼容了浏览器对 EventSource/img 的限制，又把长期 token 从 URL 移出了主路径。
