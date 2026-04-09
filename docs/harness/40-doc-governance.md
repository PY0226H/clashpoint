# EchoIsle Document Governance

更新时间：2026-04-08
状态：当前文档治理规则

---

## 1. 文档分层目的

当前文档治理关注四类内容：

1. 计划文档
2. 执行证据
3. explanation 沉淀
4. interview 沉淀
5. harness 产品摘要

P1 的目标是先把职责写清楚，避免继续在 `AGENTS.md` 里混放所有细则。

---

## 2. 当前目录职责

### 2.1 `docs/dev_plan`

当前定位：

1. 存放开发计划、执行矩阵、阶段收口后的长期清单
2. `当前开发计划.md` 是过程层
3. `completed.md` 是完成态索引层
4. `todo.md` 是延后技术债层
5. 当前仍存在部分历史内容尚未迁移到新结构

当前规则：

1. 新增计划文档仍可放在 `docs/dev_plan`
2. 新增执行报告不应再把 `docs/dev_plan` 作为首选默认目标
3. P1-4 之后，门禁/预检/验收类默认 Markdown 报告已迁移到 `docs/loadtest/evidence`
4. 若脚本历史上仍写入 `docs/dev_plan`，视为待迁移项，而不是新默认

### 2.2 执行证据目录

当前首选目录：

1. `docs/loadtest/evidence`
2. `docs/consistency_reports`

当新增脚本或新增报告输出时，应优先考虑以上目录，而不是继续写入 `docs/dev_plan`

当前已完成迁移的默认输出包括：

1. `V2-D` 阶段验收报告
2. `AI 裁判 M7` 阶段验收报告
3. 供应链安全门禁报告
4. 供应链 allowlist 到期巡检报告
5. 供应链预发故障注入演练报告
6. 供应链 SBOM 与许可证证明报告

### 2.3 `docs/explanation`

当前事实：

1. explanation 已从默认阻塞链移出
2. 目录中已有大量历史文档
3. 当前还没有统一索引

### 2.4 `docs/interview`

当前事实：

1. interview journal 已从默认阻塞链移出
2. 当前目录量较小，但尚未建立规则索引

### 2.5 `docs/harness/product-goals.md`

当前事实：

1. 它是 PRD guard 的默认快速入口
2. 它承接“日常模块开发的产品摘要”，不是权威 PRD
3. 高风险模块仍需回读完整 PRD

---

## 3. 当前使用规则

### 3.1 计划文档

1. 计划类文档统一放在 `docs/dev_plan`
2. 单计划时期默认活动计划文档是 `docs/dev_plan/当前开发计划.md`
3. 并行计划时期通过 `.codex/plan-slots/<slot>.txt` 绑定独立活动计划文档
4. 若当前任务会影响计划追踪，应更新对应 `slot` 或显式指定的计划文档
5. 当前开发 `module-turn-harness` 等 harness 模块时，也必须同步主计划文档
6. `当前开发计划.md` 只承载本轮计划、执行矩阵和过程回写，不直接承担长期归档职责

### 3.2 单计划 / 并行计划 / 收口整合

当前已生效规则：

1. 单计划时期：`default` slot 指向 `docs/dev_plan/当前开发计划.md`
2. 并行计划时期：每个线程必须使用独立 `slot`
3. 当检测到多个活动 slot 且未显式指定目标时，plan sync 不应猜测回写对象
4. `todo.md` 和 `completed.md` 是长期沉淀层，不是开发中每回合的默认回写目标
5. 只有在阶段收口时，才把活动计划拆分整合进入 `todo.md` 和 `completed.md`
6. 阶段收口时：
   - 主体已完成内容进入 `completed.md`
   - 明确延后的技术债进入 `todo.md`
   - `completed.md` 记录 `归档来源`
   - `todo.md` 记录 `来源模块`
   - 活动计划文档在收口后清空、重置或归档
7. 阶段收口不是把活动计划原样复制到两个长期文档，而是一次结构化拆分

### 3.3 explanation / interview

当前已生效规则：

1. explanation 与 interview 现在由 knowledge pack 策略触发
2. 默认 `auto` 不阻塞普通小回合
3. `force` 可显式要求本轮沉淀 explanation/interview
4. 高风险回合在 `auto` 下会自动触发

### 3.4 历史文档

1. 历史文档先不做一次性全量清洗
2. 若文档包含 legacy 路径，应在新文档中注明
3. P1 不要求一次性建立全目录索引

### 3.5 docs lint

当前已生效规则：

1. `scripts/quality/harness_docs_lint.sh` 已可用于本地和 CI 风格调用
2. 首版重点检查：`slot/pointer`、活动计划文档结构、`todo.md`、`completed.md`、`docs/harness/*.md`
3. 对 `.codex/plan-slots/default.txt` 空指针、悬空指针、活动计划结构缺失会报错
4. `completed.md` 重点检查新表头：`模块 / 结论 / 代码证据 / 验证结论 / 归档来源 / 关联待办`
5. `todo.md` 重点检查新表头：`债务项 / 来源模块 / 债务类型 / 当前不做原因 / 触发时机 / 完成定义（DoD） / 验证方式`
6. lint 只检查结构，不判断某条内容该归入 `todo` 还是 `completed`
7. 对状态词漂移、default slot 目标漂移、slot 误绑长期文档先以 warning 提示

---

## 4. 当前与后续的边界

以下还不是当前已生效规则：

1. `doc-gardener` 周期巡检
2. docs lint 全量接入 CI
3. knowledge pack 周期补写

这些属于后续阶段计划。

---

## 5. 后续目标形态（未生效）

后续阶段会推进：

1. docs lint
2. explanation/interview 索引
3. doc-gardening

但在这些能力落地前，当前规则仍以上述“当前事实”为准。
