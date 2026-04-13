---
name: module-turn-harness
description: "可选模块级 hook 链路预览/包装工具。仅在用户明确要求 module-turn-harness、harness dry-run、完整 hook 链路预览或调试 harness 时使用；普通 dev/refactor 开工前默认先读 task flow，不自动调用本 skill。"
---

# Module Turn Harness

## 概述

这是 EchoIsle 的可选模块级 hook 链路预览/包装工具。

它的作用是：

1. 手动预览或执行一轮既有 hook 链
2. 验证 `module_turn_harness.sh` 的参数分发和 artifact 输出
3. 调试 harness 自身
4. 在用户明确要求时统一输出结构化执行日志

当前定位：

1. 已实现
2. 是对现有 skills/scripts 的统一包装
3. 已具备结构化执行日志与 run summary 输出
4. 已具备 `knowledge-pack auto|skip|force` 策略
5. 不是普通 dev/refactor 的默认开工入口

重要边界：

1. 本 skill 会串联 pre/post hooks。
2. 因此它不适合作为每个开发任务写代码前的默认动作。
3. 日常任务应先读取 `docs/harness/task-flows/` 中对应流程文档，再按生命周期触发具体 skill。

## 适用场景

以下情况可以使用本 skill：

1. 用户明确要求 `module-turn-harness`
2. 用户明确要求 `harness dry-run`
3. 用户明确要求完整 hook 链路预览
4. 正在调试 harness 自身
5. 需要手动验证 hook 顺序或 artifact 输出

以下情况不要默认使用本 skill：

1. 普通 `dev` / `refactor` 开工前
2. 只需要 PRD/product-goals 对齐的开发前阶段
3. 代码尚未修改完成时的 post hook 执行
4. 纯分析/评审/规划

## 当前行为

### `dev`

执行：

1. PRD gate
2. `post-module-test-guard` 对应自动化步骤
3. 对于当前任务，生成 git commit message 推荐
4. `post-module-plan-sync`
5. knowledge pack 决策
6. 按策略决定是否执行 `post-module-interview-journal`
7. 按策略决定是否执行 `post-module-explanation-journal`

### `refactor`

执行：

1. PRD gate
2. `post-module-test-guard` 对应自动化步骤
3. 对于当前任务，生成 git commit message 推荐
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
   - 当并行推进多个短期计划时，可显式使用 `--slot`

6. `--prd-mode`
   - 可选
   - 取值：`auto` / `summary` / `full`
   - 默认 `auto`

7. `--stage`
   - `refactor` 模式建议提供
   - 会传给 `post_optimization_plan_sync.sh`

8. `--knowledge-pack`
   - 可选
   - 取值：`auto` / `skip` / `force`
   - 默认 `auto`

9. `--dry-run`
   - 只显示将执行的步骤，不真正执行完整链路
   - 仅在用户明确要求 harness 预览时使用

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

## 对话输出约束（commit 推荐）

执行 `module_turn_harness.sh` 后，必须额外做一次 commit 推荐回显：

```bash
bash skills/post-module-commit-message/scripts/recommend_commit_message.sh \
  --root <repo-root> \
  --task-kind <dev|refactor|non-dev> \
  --module "<module-id>" \
  --summary "<one-line-summary>"
```

规则：

1. 在最终对话中直接输出 `Recommended`（可附 `Alternatives`），不要只说 `post-commit-message pass`。
2. 不要把 commit 推荐正文写入 `summary` 产物；`summary` 仅保留结构化执行状态。
3. 若用户要求仅一条标题，可改用 `--title-only` 并直接回显标题。

## 推荐使用方式

1. 普通任务先读 `docs/harness/task-flows/` 对应流程文档。
2. 只有 task flow 或用户明确要求时，才使用本 skill。
3. 如果用户要求完整链路预览，先用 `--dry-run`。
4. 如果用户要求正式执行完整包装链路，再去掉 `--dry-run`。
5. 对关键 harness 调试任务可加 `--strict`。

## 完成标准

执行本 skill 后，应做到：

1. hook 链路预览或包装执行明确
2. artifact 输出位置明确
3. 用户能看到 commit message 推荐正文
4. 不把本 skill 误当成普通开发前置动作

