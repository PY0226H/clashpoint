---
name: post-optimization-plan-sync
description: "在每次代码结构优化模块完成后，强制重读后端优化计划文档，执行覆盖式更新并产出下一步优化建议，避免计划与代码状态脱节。"
---

# Post Optimization Plan Sync

## 概述
用于“代码结构优化阶段”的后置同步。每次优化模块完成后，必须：
1. 读取优化计划文档。
2. 覆盖更新执行矩阵与下一步建议。
3. 追加本次优化回写记录。

计划文档解析为动态策略（不写死路径），优先级：
1. `--plan` 显式指定。
2. `--slot` 显式指定。
3. 环境变量 `OPTIMIZATION_PLAN_FILE` / `CURRENT_PLAN_FILE`。
4. 环境变量 `OPTIMIZATION_PLAN_SLOT` / `CURRENT_PLAN_SLOT` / `PLAN_SLOT`。
5. `.codex/plan-slots/*.txt`。
6. `git` 当前改动中的 `docs/dev_plan/*.md`。
7. 自动探测最近且结构匹配的计划文档（含“优化执行矩阵/下一步优化建议”）。
8. 兼容回退旧路径（若存在）。

## 输出语言
- 中文。
- 路径、命令、模块标识保持原文。

## 执行时机（强制）
当本回合包含“后端结构优化/重构/冗余清理”并可视为一个优化模块完成时，在最终回复前执行。

## 工作流
1. 确认本次优化对应阶段（如 `R1 / V2-D / A`）与状态（`done|in-progress|blocked|todo`）。
2. 运行同步脚本，重读并覆盖更新计划文档（默认第 `8,9` 节）。
3. 追加写入优化回写记录（自动识别“回写记录”章节）。
4. 在最终回复中带出“下一步优化阶段”。

## Step 1: 执行同步脚本
```bash
bash skills/post-optimization-plan-sync/scripts/post_optimization_plan_sync.sh \
  --stage "<stage-id>" \
  --module "<optimization-module-name>" \
  --summary "<本次优化内容>" \
  --status "done" \
  [--slot "<slot-name>"] \
  [--plan "<当前聚焦计划文档路径>"] \
  --rewrite-whitelist "8,9"
```

## Step 2: 阻塞或未完成状态
若本次阶段未完成，按真实状态回写：
```bash
bash skills/post-optimization-plan-sync/scripts/post_optimization_plan_sync.sh \
  --stage "<stage-id>" \
  --module "<optimization-module-name>" \
  --summary "<当前进度与阻塞点>" \
  [--plan "<当前聚焦计划文档路径>"] \
  --status "blocked" \
  --reason "<阻塞原因>"
```

## 完成标准
1. 优化计划文档已被重新读取并完成覆盖更新（第 8/9 节，受白名单控制）。
2. 回写记录已追加（已有章节复用或自动创建）。
3. 并行计划场景下不会误写到其他 slot 对应文档。
4. 最终回复明确下一步优化阶段与建议动作。

## 资源
- `scripts/post_optimization_plan_sync.sh`: 优化模块完成后的计划同步脚本。
