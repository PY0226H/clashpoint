---
name: post-module-plan-sync
description: "在每次模块开发完成后，自动同步当前正在使用的产品开发计划文档：更新已完成/未完成矩阵、下一开发模块建议，并追加模块完成历史，避免计划与代码状态脱节。"
---

# Post Module Plan Sync

## 概述
用于“模块级开发完成后的计划回写”。
每次模块完成后，必须：
1. 识别当前正在使用的开发计划文档（不写死单一路径）。
2. 更新“已完成/未完成矩阵”。
3. 更新“下一开发模块建议”（可选）。
4. 追加“模块完成同步历史”。

## 输出语言
- 中文。
- 路径、命令、模块标识保持原文。

## 执行时机（强制）
当本回合包含模块实现/重构/修复并达到可交付状态时，在最终回复前执行。

## 计划文档识别规则（按优先级）
1. 显式参数 `--plan <path>`。
2. 环境变量：`POST_MODULE_ACTIVE_PLAN` / `ACTIVE_PLAN_DOC` / `PLAN_DOC`。
3. 当前工作区已改动文件中，名称匹配 `*开发计划*.md` 的文档。
4. `docs/dev_plan/` 下名称匹配 `*开发计划*.md` 的最新文件。
5. `docs/` 下名称匹配 `*开发计划*.md` 的最新文件。

> 建议：若本回合明确了目标文档，优先传 `--plan`，避免误判。

## Step 1: 执行同步脚本
```bash
bash skills/post-module-plan-sync/scripts/post_module_plan_sync.sh \
  --module "<module-name>" \
  --summary "<本次模块完成内容>" \
  --priority "P0" \
  --status "进行中（phase1 已完成）" \
  --note "<矩阵说明>" \
  --next-steps "<建议1;建议2;建议3>"
```

可选参数：
- `--plan <path>`: 显式指定计划文档。
- `--history-date <YYYY-MM-DD>`: 指定历史记录日期。
- `--matrix-heading/--next-heading/--history-heading`: 自定义章节标题（适配不同模板）。
- `--dry-run`: 只输出目标文档与解析结果，不写文件。

## Step 2: 阻塞或部分完成场景
若模块未完全完成，按真实状态回写：
```bash
bash skills/post-module-plan-sync/scripts/post_module_plan_sync.sh \
  --module "<module-name>" \
  --summary "<当前进展与阻塞点>" \
  --priority "P0" \
  --status "进行中（blocked）" \
  --note "<阻塞原因与影响>"
```

## 完成标准
1. 已回写到“当前正在使用”的计划文档（或显式指定文档）。
2. 已完成矩阵状态同步。
3. 已追加模块完成历史。
4. 最终回复明确下一开发模块建议。

## 资源
- `scripts/post_module_plan_sync.sh`: 模块完成后的计划同步脚本（自动识别当前计划文档）。
- `references/plan-doc-detection.md`: 计划文档识别与冲突处理说明。
