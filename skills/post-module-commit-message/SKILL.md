---
name: post-module-commit-message
description: "在每轮开发收尾时，根据当前 Git 改动生成符合 Conventional Commits 规范的 commit 标题。用于功能开发、缺陷修复、重构、优化、文档与测试改动等场景，帮助快速产出可读、可检索、可审计的标准化提交命名。"
---

# Post Module Commit Message

## 概述

在每次一轮开发完成后，生成当前改动对应的 commit 标题。
输出必须符合 Conventional Commits 规范，优先给出 1 条主推荐，并可附 1-2 条备选。
默认推荐应像人工整理过的提交标题，而不是把模块流水号直接拼进标题。

## 输出要求

- 使用中文解释，commit 标题本身使用英文。
- 默认输出格式：`<type>(<scope>): <subject>`。
- 若 scope 不明确，允许省略 scope：`<type>: <subject>`。
- subject 使用小写开头的祈使语气短句，不加句号，建议不超过 72 字符。
- 对话中至少回显 `Recommended` 主推荐；若用户需要可附 `Alternatives`。
- 不允许仅以“步骤通过/step pass”代替推荐正文。
- 不要把完整模块 ID 当 scope，例如避免 `ai-judge-p36-artifact-store-port-local-pack` 这类长 scope。
- 不要使用 `advance <module> workflow`、`sync module follow-up` 这类机械泛化 subject 作为主推荐。
- `summary` 产物仅记录执行状态，不承载推荐正文。

## 工作流

1. 收集本轮改动上下文：
```bash
git status --short
git diff --name-only
git diff --cached --name-only
```

2. 判定本次提交类型（type）：
- `feat`: 新功能、能力新增、可见行为新增。
- `fix`: 缺陷修复、错误纠正、回归修复。
- `refactor`: 仅重构或结构优化，不改变外部行为。
- `perf`: 性能优化，目标是时延/吞吐/资源占用改进。
- `docs`: 文档内容变更。
- `style`: 纯样式或格式调整，不影响逻辑。
- `test`: 测试新增或调整。
- `chore`: 构建、依赖、脚本、工具链等杂项维护。
- `build`: 构建系统或依赖管理流程改动。
- `ci`: CI/CD 流程改动。
- `revert`: 回滚历史提交。

3. 推断 scope：
- 优先使用业务模块或目录名，例如 `login`、`cart`、`user`、`api`、`order`。
- 避免使用过深路径或无语义词（如 `src`、`utils`）作为 scope。
- 将长模块编号归并为稳定短 scope，例如：
  - `ai-judge-p36-*` -> `ai-judge`
  - `post-module-commit-message-*` -> `commit-message`
  - `harness-*` -> `harness`
- 若改动跨多个模块且无主次，省略 scope。

4. 生成 subject：
- 聚焦“本次改动最核心结果”，不用堆砌细节。
- 优先使用动词短语，如 `support github oauth`、`correct total price calculation`。
- 避免模糊表述，如 `update code`、`fix bug`。
- 优先从 `summary` 和主要文件变化提取用户可读结果；只有缺少上下文时才回退到模块名。

5. 质量检查：
- 检查标题是否与实际改动一致。
- 检查 type 是否过宽或过窄。
- 检查 scope 是否清晰、稳定、可复用。
- 检查是否满足 Conventional Commits 语法。

## 脚本入口

本 skill 可直接通过脚本入口生成 commit 推荐：

```bash
bash skills/post-module-commit-message/scripts/recommend_commit_message.sh \
  --root /Users/panyihang/Documents/EchoIsle \
  --task-kind dev \
  --module <module-id> \
  --summary "<summary>"
```

仅需要标题时可加：

```bash
--title-only
```

## 默认输出模板

```text
Recommended:
<type>(<scope>): <subject>

Alternatives:
1. <type>(<scope>): <subject>
2. <type>: <subject>
```

若不需要备选，可只输出 `Recommended` 一条。

## 对话协作约定

1. agent 负责将本脚本输出的推荐正文在最终对话中明确展示给用户。
2. 默认展示 `Recommended + Alternatives`；若用户明确要求精简，展示 `--title-only` 结果。
3. 脚本输出应作为最终推荐；只有脚本仍明显偏机械时，agent 才补充一条人工修订版，并应说明原因。
4. 不要把 commit 推荐正文写入 summary 或计划文档，除非用户明确要求。

## 示例

- `feat(login): support github oauth`
- `fix(cart): correct total price calculation`
- `refactor(user): extract validation logic`
- `docs(api): add webhook example`
- `style(home): format header component`
- `test(order): add refund test cases`
- `chore: update pre-commit hooks`
- `feat(ai-judge): add local artifact store adapter`
- `refactor(commit-message): improve commit message recommendations`
