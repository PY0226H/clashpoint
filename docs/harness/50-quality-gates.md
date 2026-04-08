# EchoIsle Quality Gates

更新时间：2026-04-06
状态：当前质量门禁说明

---

## 1. 目的

本文件用于说明 EchoIsle 当前已经存在的质量门禁与 guard。

重点是回答：

1. 当前已经有哪些机械化约束
2. 它们分别负责什么
3. 哪些是现状，哪些还只是后续规划

---

## 2. 当前已存在的质量门禁

### 2.1 `post-module-test-guard`

当前模块级开发最核心的质量门禁。

负责：

1. 检查是否“改代码未改测试”
2. 必要时提示补测
3. 运行测试门禁
4. 环境受限时要求明确阻塞原因

### 2.2 CI `build.yml`

当前主 CI workflow 仍然是：

1. `.github/workflows/build.yml`

当前承担的职责包括：

1. 格式检查
2. 编译检查
3. clippy
4. nextest
5. 部分 supply-chain 与 release-preflight 相关门禁

### 2.3 其它现有脚本

当前仓库还已有一些局部质量脚本，例如：

1. oversized backend file check
2. release / preflight / supply-chain 脚本
3. 模块专项 gate 脚本

### 2.4 `harness_docs_lint.sh`

当前已新增的文档结构门禁：

1. 脚本位置：`scripts/quality/harness_docs_lint.sh`
2. 当前检查范围：
   - `.codex/plan-slots/*.txt`
   - `docs/dev_plan/当前开发计划.md`
   - `docs/dev_plan/todo.md`
   - `docs/dev_plan/completed.md`
   - `docs/harness/*.md`
3. 当前输出：
   - markdown 摘要
   - json 报告
4. 当前失败条件：
   - 空 pointer
   - 悬空 pointer
   - 活动计划缺少关键章节
   - harness 文档缺少基础元信息

---

## 3. 当前使用规则

1. 模块级开发默认先看 `post-module-test-guard`
2. 如果仓库中已有专项 gate，应优先复用，而不是重造一套验证流程
3. 局部 guard 与 CI 结果若冲突，以更严格的一侧为准
4. 如果某个 gate 因环境阻塞失败，不得直接宣称“已通过”
5. 纯文档/规则调整可优先运行 `harness_docs_lint.sh`
6. `workspace_residual_guard` 已于 2026-04-07 退役，不再作为默认门禁；workspace 历史清理的真实性约束改由专项迁移验证与现有业务/DB 门禁承担

---

## 4. 当前缺口

当前质量门禁的主要问题不是“完全没有”，而是“分散且层级不清”：

1. PR / nightly / release 还没完全分层
2. docs lint 还未全量接入 CI
3. 统一 runtime verify 尚未主链化
4. runtime verify 与 orchestrator 仍未挂接

---

## 5. 后续目标形态（未生效）

后续阶段计划新增或重构：

1. `pr-fast-gate.yml`
2. `nightly-full-gate.yml`
3. `release-preflight.yml`
4. `harness_docs_lint.sh`
5. 更系统的结构/风格不变量检查

在这些能力落地前，当前质量门禁仍以上述现有脚本和 `build.yml` 为准。
