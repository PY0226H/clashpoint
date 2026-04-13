# AGENTS.md

## Purpose

This file is the agent-facing table of contents for EchoIsle.

Use it to find:

1. the task flow entry for the current request
2. which rules are currently enforced
3. where the detailed harness docs and project map live

Current status:

1. `P1-1 AGENTS TOC 收敛` 已完成
2. `P1-2 docs/harness 规则主目录` 已完成
3. `P2-1 module-turn-harness skill` 已完成
4. `P2-2 module_turn_harness.sh` 已完成
5. `P2-3 结构化执行日志` 已完成
6. `P2-4 PRD guard 摘要优先` 已完成
7. `P2-5 knowledge pack 异步化` 已完成

---

## Task Flow Entry

1. If the task is `dev`, read `/Users/panyihang/Documents/EchoIsle/docs/harness/task-flows/dev.md`.
2. If the task is `refactor` or optimization, read `/Users/panyihang/Documents/EchoIsle/docs/harness/task-flows/refactor.md`.
3. If the task is `non-dev`, read `/Users/panyihang/Documents/EchoIsle/docs/harness/task-flows/non-dev.md`.
4. If the task is stage closure, read `/Users/panyihang/Documents/EchoIsle/docs/harness/task-flows/stage-closure.md`.
5. If no task type clearly matches, use `AGENTS.md`, the user's request, and relevant skill descriptions to decide whether a skill is needed.
6. Do not manually infer a full pre/post skill chain from `AGENTS.md`; use the matching task flow and lifecycle stage.
7. `module-turn-harness` is an optional wrapper tool, not the default development preflight.

---

## Quick Rules

These are the rules that remain directly visible in `AGENTS.md`.
Detailed explanations now live under `docs/harness/`.

### Mandatory Python rule

1. For any turn that runs Python commands in this repository, run `python-venv-guard` first.
2. Never use global interpreters: `python`, `python3`, `pip`, `pip3`.
3. Always use `/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python`.

### Mandatory PRD rule

1. For any development or refactor/optimization turn that changes project code, architecture, or module behavior, run `pre-module-prd-goal-guard` before coding.
2. The authority PRD remains `/Users/panyihang/Documents/EchoIsle/docs/PRD/在线辩论AI裁判平台完整PRD.md`.
3. The default fast path is now `/Users/panyihang/Documents/EchoIsle/docs/harness/product-goals.md`; high-risk modules must fall back to the authority PRD.

### Current hook rule

1. The default entry for module-level turns is now the matching task flow under `docs/harness/task-flows/`.
2. Pre hooks and post hooks must respect lifecycle timing: run pre hooks before coding, and run post hooks only after code or document changes are complete.
3. `module-turn-harness` remains available as a wrapper over existing skills/scripts, but use it only when the user explicitly requests harness dry-run, a full hook-chain preview, a full wrapper run, or harness debugging.
4. explanation/interview no longer block ordinary small turns by default; follow the matching task flow and explicit user intent.

### Pre-release compatibility rule

1. EchoIsle is still in local development and has not been released to production users.
2. By default, do not preserve compatibility layers, gray rollout paths, legacy fallbacks, dual-write logic, adapter shims, or parallel old/new code paths for not-yet-released behavior.
3. Default to hard cutover and direct cleanup when implementing new functionality, refactors, or optimizations.
4. Only keep a temporary compatibility layer when at least one of the following is true:
   - the user explicitly asks to preserve compatibility
   - multiple active in-repo callers cannot be updated in the same turn
   - a migration, test baseline, or script cutover truly requires a short transition window
5. Any temporary compatibility layer must state its removal condition in code comments or plan notes; do not leave indefinite fallback paths in place.

### Comment style rule

1. EchoIsle 默认使用精简中文注释，但只在代码本身不够自解释时添加。
2. 注释优先说明“为什么这样做”、“这段逻辑在保护什么边界”或“这里在防什么风险”，不要逐行翻译代码表面行为。
3. 新增事务补偿、Redis/DB 一致性收敛、并发/锁语义、幂等保护、时序约束、复杂分支判定时，应补精简中文注释。
4. 简单赋值、普通 CRUD、显而易见的控制流不要为了“有注释”而加注释，避免制造注释噪音。
5. 注释默认控制在 1 到 2 行，除非用户明确要求更详细的说明。

### Backend / chat rule

1. 修改 `chat/` Rust 主线时，优先保护事务边界、幂等语义、Redis/DB 一致性、事件/outbox 收敛和权限边界，不要只看接口表面行为。
2. 新增或修改后端接口时，应同步检查 route、handler、model、RBAC / middleware、OpenAPI、错误语义与测试是否一起更新。
3. 对尚未发布的能力，默认直接切主链并清理旧路径，不为“未来可能兼容”预留长期双轨逻辑。
4. 对复杂一致性保护、补偿、时序或防重逻辑，补精简中文注释，优先解释边界和风险。

### API contract & cross-layer sync rule

1. 只要改动 API、DTO、错误码、分页字段、状态字段或 WS payload，就必须同步检查跨层调用方。
2. 后端契约变更时，至少同步检查 `openapi.rs`、前端相关 domain / SDK（如 `auth-sdk`、`realtime-sdk`、`ops-domain`）、必要测试，以及需要留痕的学习或计划文档。
3. 默认保持单一主语义字段，不为未发布能力长期保留 alias 字段、双字段并存或旧新 payload 双写。
4. 如果一个回合内无法同步所有调用方，才允许保留短期兼容层，并在计划或注释里写清移除条件。

### Frontend / journey rule

1. 修改 `frontend/` 时，优先把共享业务逻辑放在 `packages/*`，应用壳 `apps/web` 与 `apps/desktop` 只保留平台装配和入口差异。
2. 改动登录、绑手机、Lobby、Room、Wallet、Ops 等主流程时，应同时检查页面层、domain / SDK 层、路由守卫和异常提示是否一致。
3. 已有 Web/Desktop 共用语义时，优先收敛到共享包，不要在双端重复堆逻辑。
4. 前端主流程改动完成后，优先补 smoke 或专项运行态证据，而不只停留在静态 typecheck。

---

## Harness Docs

Use these files as the detailed source of truth:

1. [docs/harness/00-overview.md](/Users/panyihang/Documents/EchoIsle/docs/harness/00-overview.md): what the harness docs cover, current phase status, and where to look first
2. [docs/harness/10-task-classification.md](/Users/panyihang/Documents/EchoIsle/docs/harness/10-task-classification.md): task types, module-level definition, and task flow routing
3. [docs/harness/task-flows/README.md](/Users/panyihang/Documents/EchoIsle/docs/harness/task-flows/README.md): task-specific lifecycle flows for dev/refactor/non-dev/stage-closure
4. [docs/harness/20-orchestration.md](/Users/panyihang/Documents/EchoIsle/docs/harness/20-orchestration.md): optional `module-turn-harness` wrapper semantics
5. [docs/harness/product-goals.md](/Users/panyihang/Documents/EchoIsle/docs/harness/product-goals.md): summary-first product constraints for everyday module work
6. [docs/harness/30-runtime-verify.md](/Users/panyihang/Documents/EchoIsle/docs/harness/30-runtime-verify.md): current verification model and the gap before unified runtime verify lands
7. [docs/harness/40-doc-governance.md](/Users/panyihang/Documents/EchoIsle/docs/harness/40-doc-governance.md): plan docs, evidence docs, explanation/interview docs, and current document ownership rules
8. [docs/harness/50-quality-gates.md](/Users/panyihang/Documents/EchoIsle/docs/harness/50-quality-gates.md): current quality gates, guards, and CI responsibilities

Related planning document:

1. [docs/dev_plan/EchoIsle-Harness-Engineering-落地方案与开发计划-v2.md](/Users/panyihang/Documents/EchoIsle/docs/dev_plan/EchoIsle-Harness-Engineering-落地方案与开发计划-v2.md)

---

## Project Map

Use this file when you need a lightweight codebase map before opening implementation files:

1. [docs/architecture/README.md](/Users/panyihang/Documents/EchoIsle/docs/architecture/README.md): current code map for backend, AI service, frontend, harness, and "where to look first"

---

## Working Guidance

1. Read only the harness doc section needed for the current task.
2. Prefer concise summaries over loading long documents wholesale.
3. Treat `docs/harness/` as the detailed rules layer, and `AGENTS.md` as the navigation layer.
4. Do not assume future-phase behavior is already active unless a harness doc explicitly marks it as current.
5. Do not use `module-turn-harness` as the default pre-coding action; use it only when a task flow or the user explicitly asks for the wrapper.
6. 阶段收口时，`completed.md` 只记录主体完成快照，`todo.md` 只记录延后技术债；不要把活动计划正文原样复制进长期文档。
