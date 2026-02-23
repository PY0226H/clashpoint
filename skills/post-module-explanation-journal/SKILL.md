---
name: post-module-explanation-journal
description: "在每次模块开发完成或代码修改后，按高深度讲解规范自动生成中文代码讲解文档并写入 docs/explanation。用于需要沉淀可复述、可面试、可追溯的技术讲解材料的场景。"
---

# Post Module Explanation Journal

## 概述
把“代码改动”转成“可复述的深度讲解文档”。
每次模块开发、重构、修复后，生成一份新文档到 `docs/explanation`，覆盖架构定位、执行路径、关键函数、设计取舍、测试验证和面试问答。

## 输出语言
- 默认使用中文。
- 代码、命令、路径、协议名保留原文（如 `Axum`、`JWT`、`CORS`）。

## 工作流
1. 收集改动上下文（模块名、改动文件、测试结果、设计动机）。
2. 打开讲解规范：`references/explanation-style-spec.md`。
3. 读取改动代码并带行号定位关键实现。
4. 按规范生成“深入讲解正文”（先写到一个临时 body 文件）。
5. 运行脚本写入 `docs/explanation` 新文档。
6. 自检文档质量并在最终回复中给出文档绝对路径。

## Step 1: 收集输入
最少收集以下信息：
- `module`: 模块标识，例如 `auth-header-only-v1`。
- `summary`: 本次改动一句话摘要（改了什么 + 为什么）。
- `changes`: 改动文件列表（分号分隔），例如 `chat/a.rs;chatapp/b.js`。
- `tests`: 关键测试命令与结果（用于文档中的验证章节）。

如果 `changes` 未提供，允许脚本从 `git status` 自动推断。

## Step 2: 生成讲解正文
严格按 `references/explanation-style-spec.md` 组织正文，至少覆盖：
1. 架构角色与边界。
2. 文件级改动地图。
3. 关键函数逐段执行路径（含错误分支与状态变化）。
4. 请求/数据流的端到端路径。
5. 设计取舍、兼容策略、风险与回滚。
6. 测试证据与覆盖边界。
7. 面试深挖问答。

建议先写入临时文件，例如 `/tmp/explanation_body.md`。

## Step 3: 写入 docs/explanation
运行：

```bash
bash skills/post-module-explanation-journal/scripts/write_explanation_doc.sh \
  --module "<module-name>" \
  --summary "<what changed and why>" \
  --changes "<path1;path2;...>" \
  --body-file "/tmp/explanation_body.md"
```

脚本会自动生成新文件：
- `docs/explanation/<timestamp>-<module>.md`

## Step 4: 质量自检
自检标准（全部满足才算完成）：
1. 全文中文且结构完整。
2. 每个关键改动文件都有解释。
3. 每个核心函数有“执行步骤 + 状态码/错误语义 + 边界行为”。
4. 有测试验证与风险边界，而不是只写“已通过”。
5. 有可直接复述的面试话术。

## 最终回复要求
执行本 skill 后，在最终回复中必须：
1. 明确说明已生成讲解文档。
2. 给出生成文档的绝对路径。
3. 给出 2-4 条可面试复述的关键点。

## 资源

### scripts/
- `scripts/write_explanation_doc.sh`: 将讲解正文封装并写入 `docs/explanation` 新文档。

### references/
- `references/explanation-style-spec.md`: 讲解风格与深度规范（从你的样例文档提炼）。

### assets/
- `assets/explanation-template.md`: 兜底模板（当未提供 body 文件时使用）。
