# Stage Closure Task Flow

更新时间：2026-04-13
状态：当前默认阶段收口流程

---

## 1. 适用场景

当某个活动计划达到“这轮先到这里”的状态时，按 `stage-closure` 处理。

典型场景：

1. 当前开发计划大部分已完成，但暂时不需要完全收口
2. 有上线前收口、压测、真实环境联调、告警/看板、故障注入等延后项
3. 需要把活动计划整合进长期文档，并清空或重置活动计划

---

## 2. 收口动作

按以下顺序处理：

1. 从活动计划中提取主体已完成模块，写入 `docs/dev_plan/completed.md`。
2. 从活动计划中提取明确延后的技术债/收口债，写入 `docs/dev_plan/todo.md`。
3. 给 `completed.md` 条目标注 `归档来源`。
4. 给 `todo.md` 条目标注 `来源模块`。
5. 归档活动计划文档到 `docs/dev_plan/archive`
6. 清空、重置活动计划文档。
7. 必要时回收或重绑对应 `slot`。

---

## 3. 不要做

1. 不要把活动计划全文原样复制进 `completed.md`。
2. 不要把所有未完成内容都扔进 `todo.md`。
3. 不要把产品 wishlist 或脑暴内容混进技术债池。
4. 不要触发普通 dev/refactor 的 post hooks，除非用户明确要求。

---

## 4. 可触发内容

1. 收口后可运行 `harness_docs_lint.sh` 验证长期文档结构。
2. 用户需要提交时，可使用 `post-module-commit-message` 输出 commit message 推荐。
3. 如果收口内容涉及运行态验证证据，可按需单独运行 `journey_verify.sh`。
4. 若需要先评审草案，可先运行 `scripts/harness/ai_judge_stage_closure_draft.sh` 输出 `completed/todo` 候选项，再决定是否正式写入长期文档。
5. 若需要自动执行“写入 completed/todo + 归档并重置活动计划”，可运行 `scripts/harness/ai_judge_stage_closure_execute.sh`。
6. 若需要生成“收口草案 + runtime ops pack”关联证据，可运行 `scripts/harness/ai_judge_stage_closure_evidence.sh`。
