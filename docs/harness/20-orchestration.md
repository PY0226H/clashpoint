# EchoIsle Orchestration

更新时间：2026-04-12
状态：当前编排规则（P2-1 / P2-2 / P2-3 / P2-4 / P2-5 已落地）

---

## 1. 当前事实

EchoIsle 现在已经有统一的模块级入口：

1. `skills/module-turn-harness/SKILL.md`
2. `scripts/harness/module_turn_harness.sh`

这意味着：

1. 模块级开发与模块级重构现在优先走 `module-turn-harness`
2. 现有 pre/post hooks 由该入口统一串联
3. explanation/interview 已改为 knowledge pack 策略触发
4. hook matrix 仍然有效，但默认不再要求人工记忆顺序

本文件描述“当前已生效的统一入口”，同时保留 legacy fallback 说明。

---

## 2. 当前模块级回合编排

### 2.1 `Code development`

默认执行顺序：

1. 通过 `module-turn-harness --task-kind dev` 进入
2. 执行 PRD gate
3. 执行 `post-module-test-guard` 对应自动化步骤
4. 输出 commit message 建议（正文用于终端/对话回显，不写入 summary 正文）
5. 执行 `post-module-plan-sync`
6. 执行 knowledge pack 决策
7. 若策略命中，再执行 `post-module-interview-journal`
8. 若策略命中，再执行 `post-module-explanation-journal`

### 2.2 `Refactor/optimization`

默认执行顺序：

1. 通过 `module-turn-harness --task-kind refactor` 进入
2. 执行 PRD gate
3. 执行 `post-module-test-guard` 对应自动化步骤
4. 输出 commit message 建议（正文用于终端/对话回显，不写入 summary 正文）
5. 执行 `post-optimization-plan-sync`
6. 执行 knowledge pack 决策
7. 若策略命中，再执行 `post-module-interview-journal`
8. 若策略命中，再执行 `post-module-explanation-journal`

### 2.3 `Non-development work`

默认：

1. 可通过 `module-turn-harness --task-kind non-dev` 进入轻量模式
2. 优先执行 `scripts/quality/harness_docs_lint.sh` 等轻量检查
3. 不进入模块级 pre/post hook 链
4. 仍会输出当前任务分类和建议动作

---

## 3. 当前使用方式

当前的推荐使用方式是：

1. 先在 `AGENTS.md` 确认这是模块级任务
2. 使用 `bash scripts/harness/module_turn_harness.sh --help` 查看参数
3. 以 `--task-kind dev|refactor|non-dev` 进入对应模式
4. 单计划时期使用 `default` 活动计划入口
5. 并行计划时期显式传 `--slot`
6. 优先使用 `--dry-run` 查看即将执行的步骤
7. 正式执行时按需要加 `--strict`
8. 纯文档/规则调整时，可用 `--task-kind non-dev` 先跑 docs lint
9. 每次执行后（包含 `dry-run`），可直接查看 `artifacts/harness/` 下的 `.jsonl/.summary.json/.summary.md`
10. 若你想强制覆盖自动判定，可显式传 `--prd-mode summary|full`
11. 若你想控制 explanation/interview 是否补写，可显式传 `--knowledge-pack auto|skip|force`
12. 回合结束后，agent 应在对话里直接展示 commit 推荐正文，不要只反馈 `post-commit-message` 步骤通过

如果你不想使用统一入口，仍可按旧方式手工执行 hook，但那已退化为兼容 fallback，不再是默认主路径。

### 3.0 代码注释规范

当前已生效规则：

1. 默认使用精简中文注释，但只给“非自解释逻辑”补注释。
2. 注释优先解释原因、边界和风险，不解释代码表面动作。
3. 当本轮新增以下逻辑时，应主动补精简中文注释：
   - 事务补偿或回滚保护
   - Redis/DB 一致性收敛
   - 锁、并发或时序约束
   - 幂等、防重、重试或降级判定
   - 不容易一眼看懂的复杂分支
4. 普通参数搬运、明显的 CRUD、简单条件分支不要求注释。
5. 每轮实现结束前，agent 应自查一次：“新增复杂逻辑是否已补必要的精简中文注释”。

### 3.1 单计划

推荐做法：

1. 让 `default` slot 指向 `docs/dev_plan/当前开发计划.md`
2. 先生成短期计划并写入该文档
3. 后续每个开发回合都默认回写该文档
4. 到阶段收口时，再把已完成内容整合进 `completed.md`，未完成内容整合进 `todo.md`

示例：

```bash
bash scripts/harness/module_turn_harness.sh \
  --task-kind dev \
  --module "auth-session-hardening" \
  --summary "加固 auth session revoke 一致性与回收链路" \
  --dry-run
```

### 3.2 并行计划

推荐做法：

1. 每个线程使用独立 `slot`
2. 每个 `slot` 绑定独立活动计划文档
3. 一个线程从“生成计划 -> 执行 -> 回写 -> 收口”始终只操作自己的 `slot`
4. 只要存在多个活动计划，就不要依赖 `default` 自动猜测

示例：

```bash
bash scripts/harness/module_turn_harness.sh \
  --task-kind refactor \
  --slot "backend-signin" \
  --module "post-api-signin-flow-optimization" \
  --summary "优化 POST /api/auth/v2/signin 流程与鉴权链路" \
  --dry-run
```

```bash
bash scripts/harness/module_turn_harness.sh \
  --task-kind dev \
  --slot "frontend-ui" \
  --module "frontend-ui-polish" \
  --summary "优化前端 UI 结构与交互表现" \
  --dry-run
```

### 3.3 收口整合

当某个活动计划达到“这轮先到这里”的阶段时：

1. 将已完成内容整理进 `docs/dev_plan/completed.md`
2. 将未完成但后续仍要继续的内容整理进 `docs/dev_plan/todo.md`
3. 清空、重置或归档该活动计划文档
4. 如果不再继续该计划，对应 `slot` 也应回收或改指向新文档

---

## 4. 当前限制

1. 当前 orchestrator 仍是对既有 skill/script 的薄包装，不是最终形态
2. 已有 `journey_verify.sh` 统一入口，但它还没有接入 `module-turn-harness` 主链
3. 当前 harness 日志记录的是“执行过程”，`journey_verify` 记录的是“运行态验证结论”，两者尚未汇合
4. PRD guard 已有独立脚本接口，但高风险判定当前仍基于关键词与任务摘要，不是代码语义级识别
5. knowledge pack 的 auto 判定当前仍基于关键词、摘要和 issues，不是模块注册表

---

## 5. 后续目标形态（仅说明，不视为当前已生效）

后续仍要推进的内容是：

1. 更完整的 PRD gate 接口
2. runtime verify 主链化
3. knowledge pack 周期补写
4. 更强的证据聚合与失败恢复

当前入口已经生效，但仍会在后续阶段继续增强。
