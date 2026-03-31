# AGENTS.md

## Skills

A skill is a set of local instructions stored in a `SKILL.md` file.

### Available skills (authoritative list)

- `openai-docs`: Use when the user asks how to build with OpenAI products or APIs and needs up-to-date official documentation with citations, help choosing the latest model for a use case, or explicit GPT-5.4 upgrade and prompt-upgrade guidance; prioritize OpenAI docs MCP tools, use bundled references only as helper context, and restrict any fallback browsing to official OpenAI domains. (file: `/Users/panyihang/.codex/skills/.system/openai-docs/SKILL.md`)
- `skill-creator`: Guide for creating effective skills. Use when users want to create or update a skill that extends Codex capabilities. (file: `/Users/panyihang/.codex/skills/.system/skill-creator/SKILL.md`)
- `skill-installer`: Install Codex skills into `$CODEX_HOME/skills` from a curated list or a GitHub repo path. (file: `/Users/panyihang/.codex/skills/.system/skill-installer/SKILL.md`)
- `post-module-test-guard`: Generate or update tests for changed module behavior and run repository quality gates after implementation. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-test-guard/SKILL.md`)
- `post-module-interview-journal`: Generate interview-ready development records after each module implementation. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-interview-journal/SKILL.md`)
- `post-module-explanation-journal`: Generate deep Chinese explanation documents for newly added or modified module code under `docs/explanation`. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-explanation-journal/SKILL.md`)
- `post-module-commit-message`: After each development round, generate a Conventional Commits compliant commit title that best matches the current Git changes. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-commit-message/SKILL.md`)
- `post-module-plan-sync`: After each code development turn that adds or changes module behavior, sync the currently active development plan document with module status, next-step suggestions, and completion history. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-plan-sync/SKILL.md`)
- `python-venv-guard`: Enforce Python virtual environment usage before any Python command, and forbid global python/pip usage. (file: `/Users/panyihang/Documents/EchoIsle/skills/python-venv-guard/SKILL.md`)
- `pre-module-prd-goal-guard`: Before each module development/refactor/optimization, fully read the PRD and align implementation decisions with the product target end-state. (file: `/Users/panyihang/Documents/EchoIsle/skills/pre-module-prd-goal-guard/SKILL.md`)
- `post-optimization-plan-sync`: After each module-level refactor or optimization turn, sync optimization matrix and next-step recommendation, then append optimization history. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-optimization-plan-sync/SKILL.md`)

### Skill usage rules

- Discovery: The list above is the only session skill source of truth.
- Trigger: If the user names a skill (with `$SkillName` or plain text), or the task clearly matches a skill description, that skill must be used in the turn.
- Multiples: If multiple skills match, use the minimal set that covers the task and state execution order.
- Turn scope: Do not carry skills across turns unless re-mentioned.
- Missing/blocked: If a named skill is unavailable or unreadable, say so briefly and continue with the best fallback.

### Skill execution workflow (progressive disclosure)

1. Open the target `SKILL.md` and read only what is needed.
2. Resolve relative paths relative to the skill directory first.
3. Load only required reference files; do not bulk-load folders.
4. Prefer existing `scripts/` and `assets/` over recreating content manually.
5. Announce selected skills and reason in one short line.

### Context hygiene

- Keep context small; summarize long content instead of pasting.
- Avoid deep reference chasing unless blocked.

## Mandatory Python environment rule

- For any turn that runs Python commands in this repository, run `python-venv-guard` first.
- Never use global interpreters (`python`, `python3`, `pip`, `pip3`) for project tasks.
- Always use `/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python`.

## Mandatory pre-development PRD hook

- For any development turn that changes project code, architecture, or module behavior, run `pre-module-prd-goal-guard` before coding.
- `pre-module-prd-goal-guard` is mandatory for every development task. There is no opt-out for feature development, bug fixes, refactors, or optimizations.
- Must fully read `/Users/panyihang/Documents/EchoIsle/docs/PRD/在线辩论AI裁判平台完整PRD.md`.
- The purpose is to align with the product's target end-state and avoid wrong directional decisions.
- If task scope conflicts with PRD target shape, clarify adjustment strategy before coding.

## Task classification rules

- `Code development`: Adds features, fixes behavior, changes business logic, introduces endpoints, alters schemas, or otherwise changes externally observable module behavior.
- `Refactor/optimization`: Improves structure, readability, maintainability, or performance without adding a new product capability as the primary goal.
- `Non-development work`: Pure documentation updates, prompt drafting, analysis, reviews without code changes, or other tasks that do not modify project code paths.
- `Module-level`: A task is module-level when it modifies production code, shared runtime configuration, data flow, interfaces between components, or any code path that should be tracked in project planning docs.
- If a task includes both development and refactor/optimization work, classify it by the primary delivery goal. New behavior or changed behavior takes precedence over refactor labeling.

## Mandatory post-module hook

For any module-level code development or module-level refactor/optimization turn, run hooks in this order:

1. `post-module-test-guard`
2. `post-module-interview-journal`
3. `post-module-explanation-journal`
4. `post-module-commit-message`

The three hooks above are mandatory for:

- code development
- feature implementation
- bug fixes
- refactors
- optimizations

Only for code development turns run additionally:

5. `post-module-plan-sync`

`Code development` includes functional additions and behavior-changing fixes.
`post-module-plan-sync` must run when the task is feature development, code implementation, or behavior-changing bug fixing.
`post-module-plan-sync` must NOT run in refactor/optimization turns.

### Post-module hook requirements

- Testing hook must:
  - check whether test changes are missing for production/module code changes
  - generate or update tests when needed
  - run project test gates and pass only when required checks succeed
- Interview journal hook must update:
  - `docs/interview/01-development-log.md`
  - `docs/interview/02-troubleshooting-log.md`
  - `docs/interview/03-interview-qa-log.md`
- Explanation journal hook must:
  - follow `docs/explanation/00-讲解规范.md`
  - create a new markdown file under `docs/explanation/`
  - explain only new/modified code paths with architecture, execution flow, tradeoffs, and testing evidence
- Plan sync hook must:
  - sync the currently active development plan document (dynamic resolution; do not hardcode a single path)
  - update module status matrix and next-step suggestions
  - append module completion sync history
- Commit message hook must:
  - generate at least 1 recommended commit title for current round changes
  - ensure the title follows Conventional Commits format
  - ensure title semantics align with actual diff intent (`feat/fix/refactor/docs/style/test/chore/...`)

## Mandatory post-optimization hook

- For any turn whose primary goal is module-level refactor or optimization, run `post-optimization-plan-sync` before the final response.
- `post-optimization-plan-sync` is mandatory for refactor and optimization work, and it replaces `post-module-plan-sync` in those turns.
- Do not run both `post-module-plan-sync` and `post-optimization-plan-sync` in the same turn.
- Optimization hook must:
  - resolve and read the currently active optimization/restructure plan document (dynamic resolution)
  - overwrite-sync “优化执行矩阵” and “下一步优化建议” (default rewrite sections `8,9`)
  - append optimization completion sync history and clearly state the next optimization phase

## Hook matrix

- `Non-development work`: no mandatory pre/post module hooks unless a named skill is explicitly requested.
- `Code development`: run `pre-module-prd-goal-guard` before coding, then run `post-module-test-guard`, `post-module-interview-journal`, `post-module-explanation-journal`, `post-module-commit-message`, and `post-module-plan-sync`.
- `Refactor/optimization`: run `pre-module-prd-goal-guard` before coding, then run `post-module-test-guard`, `post-module-interview-journal`, `post-module-explanation-journal`, `post-module-commit-message`, and `post-optimization-plan-sync`.
