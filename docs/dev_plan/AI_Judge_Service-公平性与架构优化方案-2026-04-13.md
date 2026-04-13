# AI_judge_service 公平性与架构优化方案（2026-04-13）

状态：待审核  
任务类型：Non-development work  
结论风格：独立评审，不以“保守维护现状”为前提

## 1. 先给结论

如果只看工程骨架，`AI_judge_service` 这条线已经不算弱：它有 `trace/replay`、failed callback、审计告警、RAG、回执快照、输入盲化兜底、终局聚合和降级语义，这些都比很多“能跑就行”的 AI 服务成熟。

但如果看你真正关心的核心价值，也就是“这个 AI 裁判是否公平、是否值得用户信任”，我的判断会更严厉一些：

1. 当前系统更像“可运维的裁判原型”，还不是“可证明更公平的裁判系统”。
2. 现阶段最大的短板不在接口完整度，而在判决科学性、偏差控制和可校准性。
3. 如果产品把 AI 裁判当成核心卖点，后续资源应该从“再补几个接口”切到“建立公平性基准 + 重构裁决引擎”。

我的推荐路线不是小修小补，也不是一步推倒重来，而是：

1. 保留现有运维骨架。
2. 重做判决内核的若干关键层。
3. 把“公平性基准与观测”提升为主线工程，而不是附属测试。

一句话概括：`留壳，换芯，先校准，再放大能力。`

## 2. 这次评审的依据

本判断主要基于以下当前实现与文档：

1. `docs/PRD/在线辩论AI裁判平台完整PRD.md`
2. `ai_judge_service/README.md`
3. `ai_judge_service/app/phase_pipeline.py`
4. `ai_judge_service/app/app_factory.py`
5. `ai_judge_service/app/openai_judge_client.py`
6. `ai_judge_service/app/runtime_rag.py`
7. `ai_judge_service/app/rag_retriever.py`
8. `ai_judge_service/app/trace_store.py`

PRD 对公平性的核心要求并不复杂，但要求非常硬：

1. 输入要盲化，避免身份偏置。
2. 要记录 `rubric_version`。
3. 要保留消息级证据链。
4. 要有双次评估差异控制。
5. 平台可以内部人工复核，但不对用户开放申诉入口。

问题在于：当前服务已经把这些要求“做进了结构里”，但还没有把它们“做成一个可靠的判决方法”。

## 3. 当前系统值得保留的部分

这些能力我建议保留，不要因为后续重构就推翻：

1. `trace/replay/receipt` 主链
   - 这是后续做公平性回放、偏差复盘、shadow evaluation 的基础。
   - 很多团队会先做模型，再补追踪；你这里这层反而已经走在前面。

2. failed callback 与审计告警主链
   - 这让“不可判”“链路失败”“合同阻断”不再是黑箱。
   - 对内部复核、运营排障和后续风控扩展都有价值。

3. phase/final 分层
   - 它天然适合把“阶段事实抽取”和“终局裁决”拆开。
   - 如果以后要升级成 claim graph、阶段证据账本、仲裁器，这个分层仍然能复用。

4. RAG 与来源白名单思路
   - 不是所有辩论都适合强依赖外部知识，但“当需要事实背景时，可追溯引用来源”是正确方向。

5. PRD 对齐后形成的新 final 合同
   - `debateSummary / sideAnalysis / verdictReason` 这组展示字段比旧的单字段更健康。
   - 它为后续“决策层”和“解释层”分离留了空间。

## 4. 我认为当前最危险的 8 个问题

### 4.1 公平性目前更像“结构承诺”，不是“方法保证”

现在系统满足了盲化、trace、winner mismatch 等结构要求，但这不等于判决本身已经公平。

真正的公平不是“字段对了”，而是以下问题能被回答：

1. 同一场辩论仅交换正反标签，结果是否稳定。
2. 同一立场只改变表达风格，结果是否不会系统性漂移。
3. 同一事实内容删去身份线索后，分数是否显著变化。
4. 模型在不同 topic/domain/rubric 下的误差是否可观测。

当前这些问题没有被系统性度量，所以你还不能说服务“公平”，只能说它“开始具备公平性治理接口”。

### 4.2 当前 phase 打分里存在明显的风格偏置风险

`phase_pipeline.py` 里现在有大量启发式信号直接或间接影响分数，例如：

1. 平均消息长度
2. 标点密度
3. 数字密度
4. token diversity
5. 检索命中条数
6. 反驳标记密度

这类信号的问题不是“完全没用”，而是它们很容易奖励会说话、会堆字、会引用、会用格式的人，而不是奖励论证更真、更稳、更能回应对方核心主张的人。

更直白一点说：

1. `表达强` 很容易被误当成 `逻辑强`
2. `写得长` 很容易被误当成 `覆盖广`
3. `会抛数字` 很容易被误当成 `证据强`
4. `更像搜索 query` 的一方可能更容易拿到 retrieval 支持

这是当前系统最真实的偏差源。

### 4.3 输入盲化还是“键级盲化”，不是“语义盲化”

现在的兜底主要是：

1. `extra=forbid`
2. 敏感 key 命中拒绝

这能挡住 `user_id`、`vip`、`balance` 一类透传字段，但挡不住内容层泄漏，例如：

1. 用户在消息里自报身份、职业、学历、地区、性别
2. `speaker_tag` 暗含身份风格
3. 消息内容里出现财富、段位、头衔、平台级身份标签

这意味着当前盲化更像“接口净化”，不是“裁判语境净化”。

如果你真把公平性当主线，这里必须升级成语义脱敏，而不是继续停留在字段层。

### 4.4 双次评估还不够独立

PRD 要求“双次评估差异控制”。当前实现虽然有 `winner_first / winner_second / rejudge_triggered`，但从方法论上看，它们仍然高度相关：

1. 共享同一套输入事实
2. 强依赖同一条 phase 聚合链
3. 很多信号来自同一批摘要与检索材料
4. 默认 provider 仍是单一模型系

这意味着：

1. 它能发现部分不稳定样本
2. 但它不是真正意义上的“独立第二裁判”

如果第一裁判的方法本身有系统偏差，第二次评估很可能只是“同偏差的再计算”。

### 4.5 final 展示文本现在更像模板，不像裁决书

当前 final 展示字段虽然已经切到新合同，但 `app_factory.py` 里的 final display 仍主要是模板拼接：

1. 把 winner/score/missing phase 等事实塞进句子
2. 生成固定结构的 `debateSummary`
3. 生成固定结构的 `sideAnalysis`
4. 生成固定结构的 `verdictReason`

这有两个问题：

1. 对用户来说，它“稳定”，但不够像真正的裁决说明
2. 对内部来说，它没有把证据账本真正转译成“为何判这样”

我的判断是：现在 final 展示层满足了合同，但还没有满足“解释质量”。

### 4.6 topic memory 目前不该被当成成熟能力

从实现上看，`trace_store.py` 里已经有 `save_topic_memory/list_topic_memory`，配置里也有 `topic_memory_enabled`。

但从主链接入看，它当前更像“准备好了存储接口”，还没有成为稳定、受约束、可审计的核心策略层。

更重要的是，即使它今天完整接入，我也不建议你马上把 topic memory 放大使用，因为它会带来两个风险：

1. 会把旧判决偏差带进新判决
2. 会让“历史惯例”压过“本场论证质量”

在公平性基准没有跑稳之前，topic memory 容易从“经验复用”变成“偏见放大器”。

### 4.7 服务的一致性仍受 Redis fail-open 策略影响

`trace_store.py` 现在允许 Redis 不可用时回退到进程内存存储。这对开发便利很好，但对生产一致性并不友好。

如果未来是多实例部署，那么以下能力都会受影响：

1. 幂等
2. trace
3. replay
4. audit alert
5. topic memory

我会很明确地说：

1. 开发环境可以 fail-open
2. 生产环境不应该继续把这类状态能力建立在进程内 fallback 上

否则“同一场次所有用户看到同一结果”这个 PRD 要求，在极端情况下是会被基础设施策略侵蚀的。

### 4.8 最大缺口不是模型，而是 benchmark

现在服务已经有不少运行态指标，但还缺少一个真正能回答“裁判有没有变好”的公平性基准集与评测框架。

没有 benchmark，所有优化都容易退化成：

1. 体感更像样
2. 文案更流畅
3. 运营更好查
4. 但判决未必更公平

这是我认为下一阶段最该补的主轴。

## 5. 我建议的目标架构

我的推荐不是直接改成“一个更复杂的大 prompt”，而是把 AI judge 明确拆成 5 层。

### 5.1 Layer 1：输入规范化与盲化层

职责：

1. 做字段级校验
2. 做语义级脱敏
3. 做 side 对齐与消息窗口归一化
4. 输出不可逆的 redaction map 供审计使用

这里的关键原则：

1. 给裁判模型的输入应该是最小必要信息
2. 身份线索进入模型前就应被清洗，而不是等模型“自己别偏心”

### 5.2 Layer 2：主张与证据账本层

职责：

1. 从双方消息中提取 claim
2. 标记每条 claim 的支持消息、反驳消息、外部证据
3. 构造“本场到底争了什么、回应了什么、漏了什么”的结构化账本

这层一旦建立，后面的 scoring 就不必那么依赖长度、标点、数字密度等风格代理信号。

### 5.3 Layer 3：阵营评分层

职责：

1. 只对 claim coverage、evidence support、rebuttal quality、coherence 做评分
2. 明确区分“表达好看”和“论证有效”
3. 将风格相关信号降为弱约束或只做校准，不直接推高胜负分

我的建议是：

1. `logic/evidence/rebuttal` 继续保留
2. `clarity` 保留，但不要让它成为能左右胜负的强因子
3. 长度、标点、数字只允许作为异常提示，不要直接主导分数

### 5.4 Layer 4：仲裁与差异控制层

职责：

1. 执行双次评估
2. 执行 side-swap consistency check
3. 对低分差、高冲突、高降级样本自动转 draw 或 internal review

这里的核心不是“再跑一次”，而是“第二次评估要尽量独立”。

最实用的独立化手段：

1. prompt family 不同
2. 先后顺序互换
3. 正反标签镜像
4. 可选第二模型或第二策略器

### 5.5 Layer 5：解释与运营层

职责：

1. 基于已锁定的 verdict ledger 生成用户可读说明
2. 不允许 explanation 回写或改动 verdict facts
3. 输出 internal fairness metrics、审计快照和 shadow report

这里我建议强制执行一个原则：

1. `判决先锁定`
2. `解释后生成`
3. `解释不能反向影响判决`

## 6. 三条可选路线

### 路线 A：修补型优化

特点：

1. 保持现有 phase/final 主体结构
2. 主要替换高风险启发式与补 benchmark
3. 周期短、风险低、收益中等

适合：

1. 近期必须继续交付功能
2. 团队不想一次改太深

问题：

1. 能缓解偏差，但很难从根上建立“裁判可信度护城河”

### 路线 B：保留骨架、重做判决内核

特点：

1. 保留 callback/trace/replay/receipt/audit/ops 主链
2. 重做 blindization、claim ledger、scoring、arbiter、explanation
3. 先建立 benchmark，再替换旧 scoring

这是我推荐的路线。

原因：

1. 工程成本比彻底推倒重来小
2. 能把你已经做好的运维骨架利用起来
3. 能真正把公平性变成“可校准能力”，而不是“主观相信”

### 路线 C：推倒重做成“裁判平台”

特点：

1. 从 phase/final 直接演进成多代理裁判平台
2. 引入 claim graph、evidence verifier、arbiter committee、shadow benchmark registry
3. 目标是做成产品级核心壁垒

适合：

1. 你确认 AI judge 是产品第一核心
2. 未来会扩多领域、多语言、多玩法

问题：

1. 周期长
2. 需要更稳定的评测数据资产
3. 会占掉不少后续产品节奏

## 7. 我建议你优先做的 10 件事

### P0：先证明“有没有变公平”

1. 建立 `AI Judge Fairness Benchmark`
   - 包含真实样本、镜像样本、风格改写样本、身份泄漏样本、长度扰动样本。

2. 定义核心指标
   - label swap 稳定率
   - paraphrase 稳定率
   - identity scrub 前后 winner 漂移率
   - citation precision
   - draw 触发率
   - internal reviewer agreement

3. 建 shadow evaluation
   - 新旧策略并跑，只记录，不立刻切流量。

### P1：先去掉最危险的偏差源

4. 把长度、标点、数字密度从强评分因子降级
   - 它们可以留在审计层，但不该继续强影响胜负。

5. 增加语义级 blindization
   - 对姓名、地区、职业、性别、学校、段位、财富、头衔等做清洗或占位替换。

6. 引入 side-swap consistency test
   - 同一场输入做阵营镜像，若结果大幅漂移，直接 raise fairness alert。

### P2：把“证据引用”升级成“证据账本”

7. 做 claim extraction + evidence alignment
   - 不要求一开始做到完美，但至少要让评分围绕 claim/rebuttal/evidence，而不是围绕表面写作风格。

8. 把 final explanation 改成 verdict ledger 驱动
   - 先锁事实，再生成说明；展示层不要再只靠模板句。

### P3：让系统具备长期治理能力

9. 上 internal review queue
   - 仅内部可见，用于低分差、高冲突、高告警、高降级任务。

10. 建 fairness dashboard
   - 维度至少包括 `topic_domain / rubric_version / provider / retrieval_profile / degradation_level / draw_rate / rejudge_rate`。

## 8. 我明确不建议你现在做的事

以下事项我建议先克制，不要因为“听起来高级”就提前上：

1. 不要急着把 `topic_memory` 做成强主链
   - 在 benchmark 没立起来前，它更可能放大历史偏差。

2. 不要继续奖励“写得像标准答案”的表达风格
   - 这会把裁判变成文风评分器。

3. 不要把用户画像、房间热度、历史胜率、消费能力等任何产品特征喂给 judge
   - 这些都会污染裁判中立性。

4. 不要向用户暴露 internal confidence
   - PRD 也不建议这样做。

5. 不要把“生成一段更漂亮的 verdictReason”误当成公平性升级
   - 文案不是公平本身。

## 9. 如果只允许我定一个主方向

如果你让我只拍一个板，我会建议：

1. 接下来一阶段停止把资源主要投入到“再补一些合同和接口”
2. 把主线转成“benchmark + blindization + claim/evidence ledger + side-swap consistency”
3. 在现有运维骨架上重做判决内核

因为你这个产品里，AI judge 不是点缀，它接近“裁决权”。

一旦裁决权建立在“运维不错，但偏差不可测”的系统上，后面越做越重，修正成本越高。

## 10. 推荐实施顺序

### 阶段一：两周内完成

1. 建 benchmark 样本集与 shadow 评测脚本
2. 补 fairness metrics 与 dashboard 基础字段
3. 下调风格代理信号权重
4. 上 semantic blindization 第一版

### 阶段二：一个迭代内完成

1. 引入 claim/evidence ledger
2. 上 side-swap consistency
3. explanation 改成 verdict ledger 驱动
4. internal review queue 接入 ops

### 阶段三：再决定是否升级到平台化

1. 根据 benchmark 结果决定是否引入第二模型或多仲裁器
2. 根据跨 domain 表现决定是否启用 topic memory
3. 根据业务扩展决定是否演进成 committee judge 架构

## 11. 最后一句不讨好的判断

现在的 `AI_judge_service`，我会给它两个评价：

1. 作为“可维护、可追踪、可继续迭代的 AI 服务骨架”，它已经过了及格线。
2. 作为“足以让用户长期信任其公平性”的裁判系统，它还没有过线。

这不是坏消息。

坏消息是继续自我感觉良好地往上叠功能；好消息是现在这套骨架还来得及承接一次真正有方向感的内核升级。
