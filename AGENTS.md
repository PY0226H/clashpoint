# AGENTS.md

## Skills

A skill is a set of local instructions stored in a `SKILL.md` file.

### Available skills (authoritative list)

- `skill-creator`: Guide for creating effective skills. Use when users want to create or update a skill that extends Codex capabilities. (file: `/Users/panyihang/.codex/skills/.system/skill-creator/SKILL.md`)
- `skill-installer`: Install Codex skills into `$CODEX_HOME/skills` from a curated list or a GitHub repo path. (file: `/Users/panyihang/.codex/skills/.system/skill-installer/SKILL.md`)
- `post-module-test-guard`: Generate or update tests for changed module behavior and run repository quality gates after implementation. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-test-guard/SKILL.md`)
- `post-module-interview-journal`: Generate interview-ready development records after each module implementation. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-interview-journal/SKILL.md`)
- `post-module-explanation-journal`: Generate deep Chinese explanation documents for newly added or modified module code under `docs/explanation`. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-explanation-journal/SKILL.md`)
- `post-module-plan-sync`: After each module implementation/refactor/fix, sync the currently active development plan document with module status, next-step suggestions, and completion history. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-module-plan-sync/SKILL.md`)
- `python-venv-guard`: Enforce Python virtual environment usage before any Python command, and forbid global python/pip usage. (file: `/Users/panyihang/Documents/EchoIsle/skills/python-venv-guard/SKILL.md`)
- `pre-module-prd-goal-guard`: Before each module development/refactor/optimization, fully read the PRD and align implementation decisions with the product target end-state. (file: `/Users/panyihang/Documents/EchoIsle/skills/pre-module-prd-goal-guard/SKILL.md`)
- `post-optimization-plan-sync`: After each backend optimization module, sync optimization matrix and next-step recommendation, then append optimization history. (file: `/Users/panyihang/Documents/EchoIsle/skills/post-optimization-plan-sync/SKILL.md`)

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

- For any turn that starts module-level implementation/refactor/optimization, run `pre-module-prd-goal-guard` before coding.
- Must fully read `/Users/panyihang/Documents/EchoIsle/docs/PRD/在线辩论AI裁判平台完整PRD.md`.
- The purpose is to align with the product's target end-state and avoid wrong directional decisions.
- If task scope conflicts with PRD target shape, clarify adjustment strategy before coding.

## Mandatory post-module hook

For any turn that includes module-level implementation/refactor/fix, run hooks in this order:

1. `post-module-test-guard`
2. `post-module-interview-journal`
3. `post-module-explanation-journal`

Only for code/module development turns (implementation/fix) run additionally:

4. `post-module-plan-sync`

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

## Mandatory post-optimization hook

- For any turn that completes a backend optimization/refactor module, run `post-optimization-plan-sync` before the final response.
- Optimization/refactor turns must use `post-optimization-plan-sync` instead of `post-module-plan-sync`.
- Optimization hook must:
  - resolve and read the currently active optimization/restructure plan document (dynamic resolution)
  - overwrite-sync “优化执行矩阵” and “下一步优化建议” (default rewrite sections `8,9`)
  - append optimization completion sync history and clearly state the next optimization phase
