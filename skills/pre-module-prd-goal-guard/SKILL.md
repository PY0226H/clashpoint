---
name: pre-module-prd-goal-guard
description: "在每次模块开发/重构/优化开始前，默认先读取 product-goals 摘要，并在高风险场景自动回读完整 PRD，对齐产品目标与最终形态，避免方向性错误决策。"
---

# Pre Module PRD Goal Guard

## 目标
在任何模块级开发动作开始前，先用 `product-goals` 摘要校准方向；若命中高风险范围，再回读完整 PRD，确保实现决策不偏离产品最终形态。

## 默认 PRD 文档
- `/Users/panyihang/Documents/EchoIsle/docs/PRD/在线辩论AI裁判平台完整PRD.md`
- `/Users/panyihang/Documents/EchoIsle/docs/harness/product-goals.md`

## 输出语言
- 中文。
- 路径、命令、模块标识保持原文。

## 执行时机（强制）
任何“准备开始模块开发/重构/优化”的回合，在真正改代码前先执行本 skill。

## 强制规则
1. 默认必须先读取 `docs/harness/product-goals.md`。
2. 命中高风险范围时，必须再回读完整 PRD。
3. 未完成本轮所需的 PRD 对齐前，不得进入编码。
4. 若当前任务与 PRD 中目标形态冲突，先明确冲突点与调整方案，再进入编码。

## 工作流
1. 默认读取 `product-goals.md`。
2. 判断是否命中高风险范围：
   - 认证、权限、短信验证码、微信登录、密码链路
   - 支付、钱包、账本、充值、置顶扣费
   - AI 裁判结果结构、draw、投票、二番战、RAG、解释性字段
   - 运营后台、发布、审核、App Store、合规
   - 跨服务边界、关键数据流、核心用户主流程改动
3. 若命中高风险，则回读完整 PRD。
4. 提炼与本次任务相关的目标约束：用户价值、关键流程、边界条件、非目标范围。
5. 对齐本次模块方案，判断是否偏离产品中级目标与最终形态。
6. 若存在偏离风险：先记录原因与修正策略，再开始编码。
7. 在最终回复中简要说明“已完成 PRD 对齐”及结论。

## Step 1: 阅读摘要
```bash
cat /Users/panyihang/Documents/EchoIsle/docs/harness/product-goals.md
```

## Step 2: 必要时回读完整 PRD
```bash
cat /Users/panyihang/Documents/EchoIsle/docs/PRD/在线辩论AI裁判平台完整PRD.md
```

## Step 3: 可执行脚本接口
```bash
bash /Users/panyihang/Documents/EchoIsle/skills/pre-module-prd-goal-guard/scripts/run_prd_goal_guard.sh \
  --root /Users/panyihang/Documents/EchoIsle \
  --task-kind dev \
  --module "example-module" \
  --summary "一句话摘要" \
  --mode auto
```

## Step 4: 对齐检查
在进入编码前，至少确认以下问题：
1. 本次模块目标是否服务于 PRD 的中级目标。
2. 本次方案是否破坏最终形态中的关键流程或架构方向。
3. 本次范围是否误做了 PRD 明确排除的能力。
4. 若当前任务属于高风险范围，是否已回读完整 PRD。

## Step 5: 进入开发
仅在本轮所需的 PRD 阅读与对齐结论明确后开始编码。

## 完成标准
1. 已读取 `product-goals.md`。
2. 若命中高风险范围，已回读完整 PRD。
3. 已完成本次任务与 PRD 目标形态的对齐判断。
4. 若有偏离，已明确记录偏离原因与修正策略。
5. 最终回复包含对齐结论（对齐/偏离并已处理）。
