# 模块深度讲解：post-module-explanation-journal-bootstrap-v1

## 元信息
- 生成时间: `2026-02-22 23:06:13 -0800`
- 分支: `main`
- 提交: `7110347`
- 讲解规范: `docs/explanation/00-讲解规范.md`
- 改动摘要: 新增讲解规范与自动讲解 Skill，并接入 AGENTS 强制后置钩子，实现每次模块改动后的标准化深度讲解文档产出。
- 改动文件:
- AGENTS.md
- docs/explanation/00-讲解规范.md
- docs/explanation/modules-01-02-讲解.md
- skills/post-module-explanation-journal/SKILL.md
- skills/post-module-explanation-journal/agents/openai.yaml
- skills/post-module-explanation-journal/assets/explanation-template.md
- skills/post-module-explanation-journal/references/explanation-style-spec.md
- skills/post-module-explanation-journal/scripts/write_explanation_doc.sh

## 讲解正文

## 1. 架构定位与边界

这一批改动不是业务接口改造，而是“开发流程基础设施”改造：在仓库内新增一个可复用的讲解自动化能力，让每次模块代码改动后都能自动产出高质量讲解文档。

在整体协作链路中的角色是：
1. `post-module-test-guard` 负责测试收口。
2. `post-module-interview-journal` 负责开发/问题/面试日志沉淀。
3. `post-module-explanation-journal` 负责“深度技术讲解文档”沉淀。

这次新增能力的边界是：
1. 负责讲解文档结构化生成与落盘。
2. 不替代业务测试。
3. 不替代 interview 三份日志；它们是并行资产。

## 2. 改造前问题与改造目标

### 2.1 改造前问题
1. 讲解深度高度依赖临时对话，缺少稳定模板。
2. 已有 interview 文档偏“记录”，缺少“逐函数执行路径 + 架构链路”型讲解稿。
3. 每次改完模块都手工整理讲解，重复劳动大且一致性差。

### 2.2 改造目标
1. 固化“讲解规范”，把讲解质量要求写成可执行规则。
2. 新增 skill，把讲解生成流程标准化。
3. 把 skill 接入 `AGENTS.md` 强制后置钩子，确保默认自动执行。

### 2.3 非目标
1. 不在本批次引入新的业务功能。
2. 不在本批次修改 CI 流程。
3. 不在本批次引入自动解析 AST 的重型工具链。

## 3. 文件级改动地图

1. `/Users/panyihang/Documents/aicomm/AGENTS.md`
- 新增 skill 注册项（`post-module-explanation-journal`）。
- 在 Mandatory post-module hook 中加入第三步自动触发。
- 明确 explanation hook 的产出约束：遵循规范、写新文档、解释新增/修改代码路径。

2. `/Users/panyihang/Documents/aicomm/skills/post-module-explanation-journal/SKILL.md`
- 定义 skill 的触发场景、工作流、输入参数和完成标准。
- 要求输出中文，并保留技术关键字英文。

3. `/Users/panyihang/Documents/aicomm/skills/post-module-explanation-journal/references/explanation-style-spec.md`
- 沉淀深度讲解规范（从样例提炼）。
- 固定讲解顺序、硬性深度要求、质量评分标准。

4. `/Users/panyihang/Documents/aicomm/skills/post-module-explanation-journal/scripts/write_explanation_doc.sh`
- 实现讲解文档自动落盘脚本。
- 负责参数解析、改动文件聚合、元信息注入、输出命名。

5. `/Users/panyihang/Documents/aicomm/skills/post-module-explanation-journal/assets/explanation-template.md`
- 兜底模板：没有自定义正文文件时，仍可产出结构化文档。

6. `/Users/panyihang/Documents/aicomm/skills/post-module-explanation-journal/agents/openai.yaml`
- 提供 UI 侧 metadata：display_name、short_description、default_prompt。

7. `/Users/panyihang/Documents/aicomm/docs/explanation/00-讲解规范.md`
- 仓库级讲解规范入口文件，作为所有讲解文档统一准绳。

8. `/Users/panyihang/Documents/aicomm/docs/explanation/modules-01-02-讲解.md`
- 作为已有讲解资产保留在同目录，便于后续统一检索。

## 4. 核心代码深讲

### 4.1 `write_explanation_doc.sh` 的执行路径

关键函数与逻辑点在 `/Users/panyihang/Documents/aicomm/skills/post-module-explanation-journal/scripts/write_explanation_doc.sh`：

1. 参数入口与容错
- `usage()`（:4）定义脚本参数契约。
- 主参数校验（:82）要求 `--module` 和 `--summary` 必填，避免生成无语义文档。

2. 文本清洗与列表输出
- `trim()`（:18）去掉首尾空白，避免列表脏数据。
- `emit_bullets()`（:25）将分号分隔列表转为 Markdown bullet，并处理空列表兜底文本（:37）。

3. 仓库上下文自动发现
- `ROOT` 未传入时自动 `git rev-parse --show-toplevel`（:88-93），保持脚本在不同 cwd 下可用。
- `CHANGES` 未传入时自动从 `git status --short` 推断（:96-98）。

4. Git 元数据采集
- 分支名通过 `symbolic-ref` 获取（:104），兼容 detached/unborn 回退值。
- 提交号通过 `rev-parse` 获取（:105-109），失败回退 `uncommitted`。

5. 输出文件命名与防冲突
- 文档目录固定为 `docs/explanation`（:111-112）。
- 模块名转 slug（:114）并清洗非法字符，保证文件名稳定。
- 文件名采用 `timestamp + slug`（:119-121），避免覆盖历史文档。

6. 文档拼装策略
- 先写元信息头：时间、分支、提交、规范路径、改动摘要、改动文件（:123-134）。
- 若传 `--body-file` 且存在，则拼接正文（:136-137）。
- 否则回退到模板（:138-139），保证最小可用产物。

### 4.2 `AGENTS.md` 的“自动触发链”改动

在 `/Users/panyihang/Documents/aicomm/AGENTS.md:29-44`，后置钩子从两段扩展为三段：
1. 先测试守门。
2. 再 interview 日志。
3. 最后 explanation 文档。

这代表流程语义是“先保证代码正确，再保证复盘资料完整，再产出深度讲解资产”，顺序合理，因为讲解基于已验证代码更可靠。

### 4.3 讲解规范双层存储设计

1. 仓库级入口规范：`docs/explanation/00-讲解规范.md`。
2. skill 内部参考规范：`skills/.../references/explanation-style-spec.md`。

这样做的意义：
1. 仓库参与者可直接在 docs 中查看规范。
2. skill 执行时也能在本地 reference 中读到完整规则，降低耦合。

## 5. 端到端流程示例（本次实际执行链路）

以“本次请求：给当前批次改动生成第一份标准讲解文档”为例：

1. 打开 skill 定义，确认输入契约和输出目标。
2. 收集当前批次改动（`git status` + 关键文件内容/差异）。
3. 按讲解规范生成深入正文（包含架构、执行路径、测试证据、面试问答）。
4. 执行 `write_explanation_doc.sh --module ... --summary ... --changes ... --body-file ...`。
5. 脚本生成 `docs/explanation/<timestamp>-<module>.md`。
6. 回读文档并检查结构完整性与可复述性。

## 6. 设计取舍与替代方案

### 6.1 选择“脚本 + body-file”的原因
1. 优点：可控、可审计、易复用，且生成逻辑与内容逻辑解耦。
2. 相比“全写死模板”：可扩展性更高，便于不同模块注入深度正文。
3. 相比“纯手工写文档”：一致性和效率更高。

### 6.2 为什么不直接做成单一规范文件
1. 仅放在 docs 中：skill 执行时耦合仓库路径，复用性差。
2. 仅放在 skill reference 中：人类阅读入口不友好。
3. 双层存储能同时满足“人可读”与“工具可用”。

## 7. 测试验证与风险边界

### 7.1 已完成验证
1. `python3 /Users/panyihang/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/panyihang/Documents/aicomm/skills/post-module-explanation-journal` -> `Skill is valid!`
2. `bash /Users/panyihang/Documents/aicomm/skills/post-module-explanation-journal/scripts/write_explanation_doc.sh --help` -> 正常输出参数说明。

### 7.2 当前未覆盖边界
1. 尚未加入脚本级自动化单元测试（例如 shellspec/bats）。
2. `git status --short` 推断改动文件对重命名/复杂状态的表现未做专项验证。
3. 文档质量评分目前靠人工自检，尚未自动打分。

### 7.3 残留风险与缓解
1. 风险：正文质量受输入 body 质量影响。
- 缓解：在 `SKILL.md` 中强制读取规范并列出自检项。
2. 风险：路径含特殊字符时 slug 清洗可能不够精细。
- 缓解：当前已清洗非字母数字，后续可增加更严格文件名测试。

## 8. 面试深挖问答

1. 为什么要把讲解自动化，而不是继续人工总结？
- 因为人工总结在频繁迭代中不稳定，自动化能保证每次都有结构化、可追溯、可复述的产物。

2. 你如何保证“自动生成”不变成流水账？
- 通过规范硬约束（固定顺序、函数级要求、测试映射、评分门槛）约束输出质量。

3. 为什么后置顺序是 test -> interview-journal -> explanation-journal？
- 先确定代码正确，再记录过程，再做深度讲解；否则讲解可能建立在未验证实现上。

4. 这个方案最大的可维护性收益是什么？
- 讲解生产链条被产品化：规范、脚本、目录、触发点都有明确职责，后续升级成本可控。

## 9. 一分钟复述稿

我这次做的是“讲解基础设施升级”，不是业务功能开发。核心是新增 `post-module-explanation-journal` skill，把每次模块改动后的讲解流程标准化：先按规范组织深度正文，再由脚本自动写入 `docs/explanation` 新文件。脚本负责参数校验、改动文件收集、git 元信息注入和文件命名，保证文档可追溯。与此同时，我把它接入 `AGENTS.md` 的强制后置钩子，形成 test-guard、interview-journal、explanation-journal 的三段收口链路。这样每次开发完不仅有测试和日志，也有可直接用于面试复述的高质量讲解稿。
