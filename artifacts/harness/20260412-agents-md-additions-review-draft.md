# EchoIsle AGENTS.md 增补建议稿（审核用）

更新时间：2026-04-11
状态：草案，未生效

---

## 1. 目的

本稿不是直接修改正式 [AGENTS.md](/Users/panyihang/Documents/EchoIsle/AGENTS.md)，而是给 EchoIsle 提供一版“可审核、可裁剪”的增补建议。

目标：

1. 保留当前 `AGENTS.md` 的 TOC / harness 导航定位
2. 补上当前缺失、但适合常驻在 agent 可见层的高杠杆规则
3. 避免把细碎实现细节堆进 `AGENTS.md`

---

## 2. 建议结论

建议不要把 OpenAI Codex 的 `AGENTS.md` 整体照搬到 EchoIsle。

更适合 EchoIsle 的做法是：

1. 保留当前 `Purpose / Harness Entry / Quick Rules / Harness Docs / Project Map / Working Guidance` 主结构
2. 在 `Quick Rules` 之后新增一个简短的“模块级工作规则”区块
3. 新区块只保留高价值触发式规则
4. 需要展开时，再逐步下沉到 `docs/harness/` 或子系统文档

本轮建议优先新增 6 个模块：

1. `Verification trigger rule`
2. `Backend / chat rule`
3. `API contract & cross-layer sync rule`
4. `AI judge service rule`
5. `Frontend / journey rule`
6. `Hotspot / large module rule`

---

## 3. 建议插入位置

建议插入到正式 [AGENTS.md](/Users/panyihang/Documents/EchoIsle/AGENTS.md) 的 `Quick Rules` 之后、`Harness Docs` 之前。

原因：

1. 这几组规则属于“当前直接可见的执行约束”
2. 它们和现有 `Mandatory Python / PRD / hook / compatibility / comment style` 属于同一层级
3. 放在 `Harness Docs` 前，agent 更容易在改代码前先看到这些触发规则

---

## 4. 可直接粘贴的建议稿

以下内容按 EchoIsle 当前文风起草，可直接作为正式 `AGENTS.md` 的候选新增章节。

```md
## Module-Specific Working Rules

These rules stay brief in `AGENTS.md`.
If a rule later needs longer explanation, move the detailed version into `docs/harness/` or subsystem docs and keep only the pointer here.

### Verification trigger rule

1. 如果本轮改动后端 handler / model / route / migration / OpenAPI，优先运行最贴近该模块的 Rust 定向测试或专项脚本。
2. 如果本轮改动前端主流程、页面状态流、鉴权跳转或 Ops 控制台，优先复用现有 Playwright smoke、`@auth-error` 用例或 `journey_verify.sh` 产出运行态证据。
3. 如果本轮改动 AI 裁判主链、RAG、runtime policy、callback 或 acceptance 语义，优先复用 `m7_acceptance_gate.py`、`b3_consistency_gate.py` 或模块专项 gate。
4. 如果仓库中已经存在更贴近该模块的验证脚本，优先复用，不要新造平行验证入口。
5. 如果验证因环境受限无法完成，必须明确说明阻塞原因，不能直接宣称“已验证通过”。

### Backend / chat rule

1. 修改 `chat/` Rust 主线时，优先保护事务边界、幂等语义、Redis/DB 一致性、事件/outbox 收敛和权限边界，不要只看接口表面行为。
2. 新增或修改后端接口时，应同步检查 route、handler、model、RBAC / middleware、OpenAPI、错误语义与测试是否一起更新。
3. 对尚未发布的能力，默认直接切主链并清理旧路径，不为“未来可能兼容”预留长期双轨逻辑。
4. 对复杂一致性保护、补偿、时序或防重逻辑，补精简中文注释，优先解释边界和风险。

### API contract & cross-layer sync rule

1. 只要改动 API、DTO、错误码、分页字段、状态字段或 WS payload，就必须同步检查跨层调用方。
2. 后端契约变更时，至少同步检查 `openapi.rs`、前端相关 domain / SDK、必要测试，以及需要留痕的学习或计划文档。
3. 默认保持单一主语义字段，不为未发布能力长期保留 alias 字段、双字段并存或旧新 payload 双写。
4. 如果一个回合内无法同步所有调用方，才允许保留短期兼容层，并在计划或注释里写清移除条件。

### AI judge service rule

1. 修改 `ai_judge_service/` 时，除遵守 Python 虚拟环境规则外，还应优先保护阶段时序、回调幂等、报告收敛和运行态策略边界。
2. 涉及 `phase_pipeline.py`、`runtime_policy.py`、RAG 检索链、rerank、callback 客户端的改动，应优先复用现有 acceptance / consistency gate。
3. 配置、阈值、provider 选择与运行策略，优先经过 `settings.py` / `wiring.py` 等集中入口，不要把环境变量读取散落到业务逻辑里。
4. 对模型降级、检索 fallback、重试和异常分支，若不是用户显式要求，默认不要新增隐藏平行路径。

### Frontend / journey rule

1. 修改 `frontend/` 时，优先把共享业务逻辑放在 `packages/*`，应用壳 `apps/web` 与 `apps/desktop` 只保留平台装配和入口差异。
2. 改动登录、绑手机、Lobby、Room、Wallet、Ops 等主流程时，应同时检查页面层、domain / SDK 层、路由守卫和异常提示是否一致。
3. 已有 Web/Desktop 共用语义时，优先收敛到共享包，不要在双端重复堆逻辑。
4. 前端主流程改动完成后，优先补 smoke 或专项运行态证据，而不只停留在静态 typecheck。

### Hotspot / large module rule

1. 下列文件已属于当前热点或大模块，应默认优先考虑“拆分”而不是“继续堆功能”：`chat/chat_server/src/handlers/auth.rs`、`chat/chat_server/src/handlers/debate.rs`、`chat/chat_server/src/handlers/debate_ops.rs`、`chat/chat_server/src/models/ops_observability.rs`、`ai_judge_service/app/phase_pipeline.py`、`ai_judge_service/app/trace_store.py`、`frontend/packages/app-shell/src/pages/OpsConsolePage.tsx`。
2. 如果改动发生在这些热点文件里，除非是局部缺陷修复，否则优先把新增逻辑抽到更窄的子模块、helper、子页面或子服务。
3. 新回合若必须继续修改热点文件，至少应在计划、总结或注释中说明这次改动的边界，以及后续可拆分方向。
4. 不要在已经过大的模块旁继续复制出新的“大而全”文件；优先按职责切分。
```

---

## 5. 为什么这 6 块最适合 EchoIsle

### 5.1 `Verification trigger rule`

最值得优先加入。

原因：

1. EchoIsle 已经有 `post-module-test-guard`、`journey_verify.sh`、Playwright smoke、`m7_acceptance_gate.py`、`b3_consistency_gate.py`
2. 现在的问题不是“没有验证资产”，而是 `AGENTS.md` 没把“改什么就优先跑什么”直接写给 agent 看
3. 这类规则非常符合 Codex `AGENTS.md` 的强项：触发式、工程化、低歧义

### 5.2 `Backend / chat rule`

适合 EchoIsle 的原因是后端不是单纯 CRUD，而是明显存在：

1. 事务边界
2. Redis/DB 一致性
3. 幂等/防重
4. RBAC / middleware
5. outbox / 事件链路

这些都是 agent 容易“只补接口，不补收敛边界”的地方。

### 5.3 `API contract & cross-layer sync rule`

EchoIsle 非常适合显式写这一条。

原因：

1. 你的后端、前端、OpenAPI、学习文档之间联动很频繁
2. 现有完成记录里大量出现“OpenAPI 契约补齐”“前后端契约同步”“SDK/domain 同步”
3. 这已经不是偶发事项，而是稳定工程模式

### 5.4 `AI judge service rule`

你现在在 `AGENTS.md` 里只有 Python 解释器规则，但 AI 服务真正高风险的并不是解释器，而是：

1. pipeline 阶段时序
2. callback 幂等
3. runtime policy
4. RAG / rerank / fallback
5. settings / wiring 集中治理

这些更值得提升到 agent 第一眼可见层。

### 5.5 `Frontend / journey rule`

前端现在也已经不是“页面零散修改”阶段，而是：

1. 有 Web/Desktop 双端
2. 有 `packages/*` 共享层
3. 有多条主用户流程
4. 已有 Playwright smoke 与 auth-error 体系

因此适合把“共享逻辑放 packages”“主流程改动优先跑 smoke”写成显式规则。

### 5.6 `Hotspot / large module rule`

这块和 Codex 的思路最像，也最适合你现在补。

当前仓库已经存在明显热点：

1. `auth.rs`
2. `debate.rs`
3. `debate_ops.rs`
4. `ops_observability.rs`
5. `phase_pipeline.py`
6. `trace_store.py`
7. `OpsConsolePage.tsx`

如果不把“热点模块默认先拆分”提升成规则，agent 很容易每轮都在原文件继续累积复杂度。

---

## 6. 本轮不建议一起加入的模块

为了不让正式 `AGENTS.md` 变厚，本轮不建议一次性再加以下内容：

1. 过细的语言/框架编码风格规则
2. 很具体的测试断言写法模板
3. 依赖升级 / lockfile / schema 生成的细碎命令级规则
4. 冗长的“每个目录怎么改”的手册式说明

这些内容更适合后续按需要下沉到：

1. `docs/harness/`
2. 子系统 README
3. 专项 skill / script

---

## 7. 建议采用方式

如果要把这份草案落到正式 [AGENTS.md](/Users/panyihang/Documents/EchoIsle/AGENTS.md)，建议分两步：

1. 先只落地 `Verification trigger rule`、`API contract & cross-layer sync rule`、`Hotspot / large module rule`
2. 如果一两轮后感觉 agent 仍经常漏掉子系统语义，再补 `Backend / chat`、`AI judge service`、`Frontend / journey`

这样可以兼顾：

1. 保持 `AGENTS.md` 简洁
2. 提升高频回合的执行稳定性
3. 避免一次引入过多新常驻规则

---

## 8. 审核提示

审核这份草案时，建议重点看三件事：

1. 哪些规则应该常驻在 `AGENTS.md`，哪些更适合留在 `docs/harness/`
2. 热点文件名单是否要缩短，只保留最核心的几个
3. `API contract & cross-layer sync rule` 是否要再显式点名 `realtime-sdk`、`auth-sdk`、`ops-domain` 等高频调用方
