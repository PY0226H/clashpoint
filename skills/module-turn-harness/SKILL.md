---
name: module-turn-harness
description: "模块级开发统一入口。根据任务类型进入 dev/refactor/non-dev 三种模式，串联当前已存在的 pre/post hooks，并提供 dry-run / strict 两种使用语义。"
---

# Module Turn Harness

## 概述

这是 EchoIsle 当前模块级开发的默认入口 skill。

它的作用是：

1. 统一进入模块级开发流程
2. 根据 `task-kind` 决定要触发的 hook 链
3. 降低“记住 pre/post hook 顺序”的心智负担
4. 提供 `--dry-run` 与 `--strict` 两种可控使用方式

当前定位：

1. 已实现
2. 是对现有 skills/scripts 的统一包装
3. 已具备结构化执行日志与 run summary 输出
4. 已具备 `knowledge-pack auto|skip|force` 策略
5. 不是最终形态，后续仍会继续增强

## 适用场景

以下情况优先使用本 skill：

1. 模块级 `Code development`
2. 模块级 `Refactor/optimization`
3. 想先预览一轮任务会触发哪些 hooks

以下情况不必强制使用：

1. 纯文档改动
2. 纯分析/评审
3. 非模块级的小型非开发任务

## 当前行为

### `dev`

执行：

1. PRD gate
2. `post-module-test-guard` 对应自动化步骤
3. 对于当前任务，生成git commit message 推荐
4. `post-module-plan-sync`
5. knowledge pack 决策
6. 按策略决定是否执行 `post-module-interview-journal`
7. 按策略决定是否执行 `post-module-explanation-journal`

### `refactor`

执行：

1. PRD gate
2. `post-module-test-guard` 对应自动化步骤
3. 对于当前任务，生成git commit message 推荐
4. `post-optimization-plan-sync`
5. knowledge pack 决策
6. 按策略决定是否执行 `post-module-interview-journal`
7. 按策略决定是否执行 `post-module-explanation-journal`

### `non-dev`

执行：

1. 输出轻量模式说明
2. 优先执行 `harness_docs_lint.sh` 等轻量检查
3. 不触发模块级 pre/post hooks

## 命令

```bash
bash scripts/harness/module_turn_harness.sh \
  --task-kind <dev|refactor|non-dev> \
  --module "<module-id>" \
  --summary "<one-line-summary>" \
  [--plan "<path>"] \
  [--slot "<slot-name>"] \
  [--prd-mode "<auto|summary|full>"] \
  [--knowledge-pack "<auto|skip|force>"] \
  [--stage "<stage-id>"] \
  [--priority "<P0|P1|P2>"] \
  [--status-text "<status>"] \
  [--note "<matrix-note>"] \
  [--next-steps "<建议1;建议2>"] \
  [--issues "<问题=>修复;问题2=>修复2>"] \
  [--learnings "<点1;点2>"] \
  [--root "<repo-root>"] \
  [--dry-run] \
  [--strict]
```

## 参数语义

1. `--task-kind`
   - 必填
   - 取值：`dev` / `refactor` / `non-dev`

2. `--module`
   - 必填
   - 使用稳定模块标识，例如 `module-turn-harness-bootstrap`

3. `--summary`
   - 必填
   - 一句话说明本轮做了什么、为什么做

4. `--plan`
   - 可选
   - 显式指定计划文档，避免自动探测误判

5. `--slot`
   - 可选
   - 用于选择命名活动计划槽位，例如 `backend-signin`、`frontend-ui`
   - 当并行推进多个短期计划时，优先使用 `--slot`

6. `--prd-mode`
   - 可选
   - 取值：`auto` / `summary` / `full`
   - 默认 `auto`
   - `auto` 表示默认先读 `docs/harness/product-goals.md`，命中高风险范围时自动回读完整 PRD

7. `--stage`
   - `refactor` 模式建议提供
   - 会传给 `post_optimization_plan_sync.sh`

8. `--knowledge-pack`
   - 可选
   - 取值：`auto` / `skip` / `force`
   - 默认 `auto`
   - `auto` 会在 `security` / `reliability` / `architecture` / `cross-service` / `release` 以及复杂故障修复场景自动触发 knowledge pack

9. `--dry-run`
   - 只显示将执行的步骤，不真正执行

10. `--strict`

- 任一步失败即停止

## 当前产物

每次执行后（包含 `dry-run`），默认会写出：

1. `artifacts/harness/<timestamp>-<module>.jsonl`
2. `artifacts/harness/<timestamp>-<module>.summary.json`
3. `artifacts/harness/<timestamp>-<module>.summary.md`

这些产物用于记录：

1. 每一步的开始/结束/退出码
2. 关键证据路径
3. 整轮回合的最终状态

注意：

1. `summary.json` / `summary.md` 只记录步骤状态与证据路径，不承载 commit 推荐正文。
2. commit 推荐正文应由 agent 在对话中直接回显给用户。

## 当前限制

1. PRD gate 已支持 `product-goals` 摘要优先，但高风险判定目前仍基于关键词与任务摘要
2. 高风险判定当前仍主要基于关键词、摘要与 issues，不是代码语义级识别
3. 已有 `journey_verify.sh` 统一 runtime verify 入口，但还没有接入当前主链
4. 当前结构化日志记录的是“执行过程”，不等于 runtime verify
5. commit 推荐依赖 `post-module-commit-message` 脚本启发式，不是语义级变更理解

## 对话输出约束（commit 推荐）

执行 `module_turn_harness.sh` 后，必须额外做一次 commit 推荐回显：

1. 使用与本轮一致的参数调用：
```bash
bash skills/post-module-commit-message/scripts/recommend_commit_message.sh \
  --root <repo-root> \
  --task-kind <dev|refactor|non-dev> \
  --module "<module-id>" \
  --summary "<one-line-summary>"
```
2. 在最终对话中直接输出 `Recommended`（可附 `Alternatives`），不要只说“post-commit-message pass”。
3. 不要把 commit 推荐正文写入 `summary` 产物；`summary` 仅保留结构化执行状态。
4. 若用户要求仅一条标题，可改用 `--title-only` 并直接回显标题。

## 推荐使用方式

1. 先用 `--dry-run` 看一轮会触发什么
2. 确认无误后再正式执行
3. 对关键任务加 `--strict`
4. 单计划时期可直接使用 `default` 活动计划入口
5. 并行计划时期优先显式传 `--slot`
6. 日常小回合保持 `--knowledge-pack auto`
7. 如果这是高价值回合且你确定要沉淀 explanation/interview，可显式传 `--knowledge-pack force`
8. 如果目标文档非常明确，优先显式传 `--plan`

## 完成标准

执行本 skill 后，应做到：

1. 模块级回合入口明确
2. hook 顺序不再依赖人工记忆
3. 用户能通过 `--dry-run` 预览整轮任务
