# EchoIsle Task Flows

更新时间：2026-04-13
状态：当前默认任务流程入口

---

## 1. 目的

`docs/harness/task-flows/` 是 EchoIsle 的任务类型流程层。

它的职责是：

1. 按任务类型说明 Codex 日常应该如何工作
2. 明确开发前、开发中、开发后的 skill 触发边界
3. 避免把 pre hooks 和 post hooks 混在任务开始时一次性执行

它不是：

1. 完整 skill registry
2. 自动化编排器说明书
3. 替代 `AGENTS.md` 的全局规则文件

---

## 2. 当前流程文档

1. `dev.md`
   - 新功能、行为变更、接口/schema/数据流变更
2. `refactor.md`
   - 结构优化、可维护性优化、性能优化，原则上不改变外部行为
3. `non-dev.md`
   - 纯文档、分析、评审、规划、prompt 草拟等非代码任务
4. `stage-closure.md`
   - 活动计划阶段收口，整合 `completed.md` / `todo.md`

---

## 3. 使用规则

1. 如果任务明确命中某个类型，先读对应流程文档。
2. 如果任务没有命中任何类型，由 Codex 根据用户意图和 skill description 自行判断是否读取或使用具体 skill。
3. `module-turn-harness` 已退役并删除；不要调用或重建它。
4. 需要验证、回写、commit message 或运行态摘要时，直接使用对应的具体 skill/script。
