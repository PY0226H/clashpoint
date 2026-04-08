# Harness Docs Lint Report

- root: `/Users/panyihang/Documents/EchoIsle`
- checks: 12
- errors: 2
- warnings: 1
- status: FAIL

## Checked

- `slots-dir:/Users/panyihang/Documents/EchoIsle/.codex/plan-slots`
- `slot-pointer:default`
- `todo-doc:/Users/panyihang/Documents/EchoIsle/docs/dev_plan/todo.md`
- `completed-doc:/Users/panyihang/Documents/EchoIsle/docs/dev_plan/completed.md`
- `harness-doc:/Users/panyihang/Documents/EchoIsle/docs/harness/00-overview.md`
- `harness-doc:/Users/panyihang/Documents/EchoIsle/docs/harness/10-task-classification.md`
- `harness-doc:/Users/panyihang/Documents/EchoIsle/docs/harness/20-orchestration.md`
- `harness-doc:/Users/panyihang/Documents/EchoIsle/docs/harness/30-runtime-verify.md`
- `harness-doc:/Users/panyihang/Documents/EchoIsle/docs/harness/40-doc-governance.md`
- `harness-doc:/Users/panyihang/Documents/EchoIsle/docs/harness/50-quality-gates.md`
- `harness-doc:/Users/panyihang/Documents/EchoIsle/docs/harness/60-usage-tutorial.md`
- `harness-doc:/Users/panyihang/Documents/EchoIsle/docs/harness/product-goals.md`

## Findings

- [ERROR] `plan_shape_unknown` `/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md`: slot:default 未匹配开发计划或优化计划的已知结构。
- [ERROR] `plan_shape_unknown` `/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md`: default-current-plan 未匹配开发计划或优化计划的已知结构。
- [WARNING] `current_plan_missing_default_slot_note` `/Users/panyihang/Documents/EchoIsle/docs/dev_plan/当前开发计划.md`: 当前开发计划未声明关联 slot 为 default。
