# AGENTS.md

## Purpose

This file is the agent-facing table of contents for EchoIsle.

Use it to find:

1. which skills exist
2. which rules are currently enforced
3. where the detailed harness docs live

Current status:

1. `P1-1 AGENTS TOC 收敛` 已完成
2. `P1-2 docs/harness 规则主目录` 已完成
3. `P2-1 module-turn-harness skill` 已完成
4. `P2-2 module_turn_harness.sh` 已完成
5. `P2-3 结构化执行日志` 已完成
6. `P2-4 PRD guard 摘要优先` 已完成
7. `P2-5 knowledge pack 异步化` 已完成

---

## Skills

A skill is a set of local instructions stored in a `SKILL.md` file.

### Available skills (authoritative list)

- `openai-docs`: Use when the user asks how to build with OpenAI products or APIs and needs up-to-date official documentation with citations, help choosing the latest model for a use case, or explicit GPT-5.4 upgrade and prompt-upgrade guidance; prioritize OpenAI docs MCP tools, use bundled references only as helper context, and restrict any fallback browsing to official OpenAI domains. (file: `/Users/panyihang/.codex/skills/.system/openai-docs/SKILL.md`)
- `skill-creator`: Guide for creating effective skills. Use when users want to create or update a skill that extends Codex capabilities. (file: `/Users/panyihang/.codex/skills/.system/skill-creator/SKILL.md`)
- `skill-installer`: Install Codex skills into `$CODEX_HOME/skills` from a curated list or a GitHub repo path. (file: `/Users/panyihang/.codex/skills/.system/skill-installer/SKILL.md`)
- `post-module-test-guard`: Generate or update tests for changed module behavior and run repository quality gates after implementation. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-test-guard/SKILL.md`)
- `module-turn-harness`: Single entry skill for module-level development turns. It classifies the task, runs the current pre/post hook chain, and exposes `--dry-run` / `--strict` orchestration semantics. (file: `/Users/panyihang/Documents/EchoIsle/skills/module-turn-harness/SKILL.md`)
- `post-module-interview-journal`: Generate interview-ready development records after each module implementation. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-interview-journal/SKILL.md`)
- `post-module-explanation-journal`: Generate deep Chinese explanation documents for newly added or modified module code under `docs/explanation`. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-explanation-journal/SKILL.md`)
- `post-module-commit-message`: After each development round, generate a Conventional Commits compliant commit title that best matches the current Git changes. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-commit-message/SKILL.md`)
- `post-module-plan-sync`: After each code development turn that adds or changes module behavior, sync the currently active development plan document with module status, next-step suggestions, and completion history. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-plan-sync/SKILL.md`)
- `python-venv-guard`: Enforce Python virtual environment usage before any Python command, and forbid global python/pip usage. (file: `/Users/panyihang/Documents/EchoIsle/skills/python-venv-guard/SKILL.md`)
- `pre-module-prd-goal-guard`: Before each module development/refactor/optimization, default to `product-goals` summary and automatically fall back to the full PRD for high-risk work. (file: `/Users/panyihang/Documents/EchoIsle/skills/pre-module-prd-goal-guard/SKILL.md`)
- `post-optimization-plan-sync`: After each module-level refactor or optimization turn, sync optimization matrix and next-step recommendation, then append optimization history. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-optimization-plan-sync/SKILL.md`)

### Skill usage rules

1. The list above is the only skill source of truth for this repository.
2. If the user names a skill, or the task clearly matches a skill description, that skill must be used.
3. Use the minimal set of skills needed for the turn.
4. Do not carry skills across turns unless the user re-mentions them.
5. If a skill is unavailable or unreadable, say so briefly and continue with the best fallback.

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

1. The default entry for module-level turns is now `module-turn-harness`.
2. The underlying hook matrix is still defined in `docs/harness/10-task-classification.md` and executed according to `docs/harness/20-orchestration.md`.
3. `module-turn-harness` now supports `--knowledge-pack auto|skip|force`; explanation/interview no longer block ordinary small turns by default.
4. `module-turn-harness` is the current wrapper over existing skills/scripts; later phases may expand it further, but the current implementation is already active.

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

---

## Harness Docs

Use these files as the detailed source of truth:

1. [docs/harness/00-overview.md](/Users/panyihang/Documents/EchoIsle/docs/harness/00-overview.md): what the harness docs cover, current phase status, and where to look first
2. [docs/harness/10-task-classification.md](/Users/panyihang/Documents/EchoIsle/docs/harness/10-task-classification.md): task types, module-level definition, and the current hook matrix
3. [docs/harness/20-orchestration.md](/Users/panyihang/Documents/EchoIsle/docs/harness/20-orchestration.md): how module turns are currently orchestrated through `module-turn-harness`
4. [docs/harness/product-goals.md](/Users/panyihang/Documents/EchoIsle/docs/harness/product-goals.md): summary-first product constraints for everyday module work
5. [docs/harness/30-runtime-verify.md](/Users/panyihang/Documents/EchoIsle/docs/harness/30-runtime-verify.md): current verification model and the gap before unified runtime verify lands
6. [docs/harness/40-doc-governance.md](/Users/panyihang/Documents/EchoIsle/docs/harness/40-doc-governance.md): plan docs, evidence docs, explanation/interview docs, and current document ownership rules
7. [docs/harness/50-quality-gates.md](/Users/panyihang/Documents/EchoIsle/docs/harness/50-quality-gates.md): current quality gates, guards, and CI responsibilities

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
5. 阶段收口时，`completed.md` 只记录主体完成快照，`todo.md` 只记录延后技术债；不要把活动计划正文原样复制进长期文档。
