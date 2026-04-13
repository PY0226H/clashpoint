# EchoIsle Task Classification

更新时间：2026-04-13
状态：当前已生效

---

## 1. 分类目的

任务分类用于回答两个问题：

1. 这次任务是不是模块级任务
2. 这次任务应该读取哪个任务流程文档

---

## 2. 当前分类定义

### 2.1 `Code development`

满足任一情况即可归类为 `Code development`：

1. 新增功能
2. 修复外部可见行为
3. 修改业务逻辑
4. 新增或修改接口、schema、数据流
5. 其它会改变模块对外行为的改动

### 2.2 `Refactor/optimization`

满足以下特征时归类为 `Refactor/optimization`：

1. 主要目标是结构优化、可读性、可维护性或性能
2. 不是以新增产品能力为主
3. 原则上不改变外部行为

### 2.3 `Non-development work`

以下任务归类为 `Non-development work`：

1. 纯文档更新
2. 纯分析或评审
3. prompt 草拟
4. 不修改项目代码路径的工作

### 2.4 `Module-level`

满足以下任一情况即可视为 `Module-level`：

1. 修改生产代码
2. 修改共享运行时配置
3. 修改数据流或接口边界
4. 修改组件/服务间协作方式
5. 修改任何应被计划文档追踪的代码路径

### 2.5 冲突判定

如果一个任务同时含有开发与重构内容：

1. 以主要交付目标为准
2. 新行为或行为变更优先归类为 `Code development`

---

## 3. 当前任务流程入口

### 3.1 `Non-development work`

默认：

1. 不触发模块级 pre/post hooks
2. 仅当用户显式要求某个 skill，或任务本身直接命中 skill 语义时再执行
3. 具体流程见 `docs/harness/task-flows/non-dev.md`

### 3.2 `Code development`

默认：

1. 先读 `docs/harness/task-flows/dev.md`
2. 开发前只执行 pre hooks，例如 PRD/product-goals 对齐
3. 代码实现完成后，再按流程执行 test guard、commit message、plan sync 等 post hooks

### 3.3 `Refactor/optimization`

默认：

1. 先读 `docs/harness/task-flows/refactor.md`
2. 开发前只执行 pre hooks，例如 PRD/product-goals 对齐
3. 代码实现完成后，再按流程执行 test guard、commit message、optimization plan sync 等 post hooks

### 3.4 `Stage closure`

默认：

1. 先读 `docs/harness/task-flows/stage-closure.md`
2. 将主体已完成内容写入 `completed.md`
3. 将明确延后的技术债/收口债写入 `todo.md`
4. 清空、重置或归档活动计划

---

## 4. 当前强制规则摘要

### 4.1 Python

1. 任何仓库内 Python 命令前，先执行 `python-venv-guard`
2. 必须使用 `/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python`

### 4.2 PRD

1. 任何开发或重构/优化任务，在真正改代码前先执行 `pre-module-prd-goal-guard`
2. 当前默认先读取 `docs/harness/product-goals.md`
3. 命中高风险模块时，必须再回读权威 PRD：`docs/PRD/在线辩论AI裁判平台完整PRD.md`

### 4.3 Post hooks

1. 当前 explanation/interview 已从默认阻塞链移出
2. post hooks 只在代码或文档改动完成后触发，不在写代码前触发
3. explanation/interview 仅在高价值回合或用户明确要求时补写

---

## 5. 当前与后续的边界

以下内容还不是当前规则：

1. `journey_verify.sh` 已成为统一运行态验证入口，但尚未成为模块级默认收口动作
2. CI 三层拆分全面生效
3. knowledge pack 周期补写

这些属于后续阶段计划，不能提前当成当前默认行为。
