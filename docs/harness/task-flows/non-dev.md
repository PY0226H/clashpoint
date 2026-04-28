# Non-Dev Task Flow

更新时间：2026-04-28
状态：当前默认 non-dev 流程

---

## 1. 适用场景

以下任务按 `non-dev` 处理：

1. 纯文档更新
2. 纯分析或评审
3. 规划、方案讨论、prompt 草拟
4. 不修改项目代码路径的工作

---

## 2. 默认行为

默认不触发模块级 pre/post hooks：

1. 不跑 `pre-module-prd-goal-guard`，除非文档改动会影响产品/架构约束。
2. 不跑 `post-module-test-guard`。
3. 不生成 commit message 推荐，除非用户明确要求。
4. 不执行 plan sync，除非任务目标就是同步计划文档。
5. 不触发 explanation/interview。

---

## 3. 可触发内容

以下情况可以触发轻量工具：

1. 修改 harness 文档、计划文档结构或 evidence 规则后，可运行 `harness_docs_lint.sh`。
2. 用户明确点名某个 skill 时，按该 skill 的说明执行。
3. 文档任务涉及阶段收口时，改用 `stage-closure.md`。

---

## 4. 代码事实问答

当 non-dev 任务是在询问当前项目代码事实、调用链、配置、测试或行为时：

1. 先查当前代码，再回答。
2. 文档仅作入口或背景，不作为最终事实来源。
3. 结论应尽量附带代码位置；无法核实时明确说明。

---

## 5. 不要做

1. 不要默认触发 dev/refactor 的 post hooks。
2. 不要把纯分析任务写入 `todo.md` / `completed.md`，除非用户明确要求沉淀。
