## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.

### Available skills
- skill-creator: Guide for creating effective skills. Use when users want to create a new skill (or update an existing skill) that extends Codex capabilities with specialized knowledge, workflows, or tool integrations. (file: /Users/panyihang/.codex/skills/.system/skill-creator/SKILL.md)
- skill-installer: Install Codex skills into `$CODEX_HOME/skills` from a curated list or a GitHub repo path. Use when users ask to list installable skills, install a curated skill, or install a skill from another repo (including private repos). (file: /Users/panyihang/.codex/skills/.system/skill-installer/SKILL.md)
- post-module-test-guard: Generate or update tests for changed module behavior and run repository quality gates after implementation. Use when a turn includes module-level code changes and you must ensure tests are present and passing before considering the module complete. (file: /Users/panyihang/Documents/aicomm/skills/post-module-test-guard/SKILL.md)
- post-module-interview-journal: Generate interview-ready development records after each module implementation. Use when a turn includes feature/module code changes and you need to update development log, troubleshooting log, and interview Q&A materials. (file: /Users/panyihang/Documents/aicomm/skills/post-module-interview-journal/SKILL.md)
- post-module-explanation-journal: Generate deep Chinese explanation documents for newly added or modified module code and write a new file under `docs/explanation` after each module change. Use when a turn includes module-level implementation/refactor/fix and explanation assets must be updated for learning/interview review. (file: /Users/panyihang/Documents/aicomm/skills/post-module-explanation-journal/SKILL.md)
- python-venv-guard: Enforce Python virtual environment usage before any Python command, and forbid global python/pip usage. Use whenever a turn includes Python dependency install, Python test run, Python script execution, or service startup. (file: /Users/panyihang/Documents/aicomm/skills/python-venv-guard/SKILL.md)
- pre-module-mvp-plan-guard: Before starting each development module, read the productization MVP plan, verify planned work alignment, and update the plan document with a pre-development alignment record. (file: /Users/panyihang/Documents/aicomm/skills/pre-module-mvp-plan-guard/SKILL.md)
- post-module-plan-sync: After each module completion, sync the product MVP plan by writing completed/incomplete matrix and next-step recommendation based on contract/test/linkage probes. (file: /Users/panyihang/Documents/aicomm/skills/post-module-plan-sync/SKILL.md)

### How to use skills
- Discovery: The list above is the skills available in this session (name + description + file path). Skill bodies live on disk at the listed paths.
- Trigger rules: If the user names a skill (with `$SkillName` or plain text) OR the task clearly matches a skill's description shown above, you must use that skill for that turn. Multiple mentions mean use them all. Do not carry skills across turns unless re-mentioned.
- Missing/blocked: If a named skill isn't in the list or the path can't be read, say so briefly and continue with the best fallback.
- How to use a skill (progressive disclosure):
  1) After deciding to use a skill, open its `SKILL.md`. Read only enough to follow the workflow.
  2) When `SKILL.md` references relative paths (for example `scripts/foo.py`), resolve them relative to the skill directory listed above first, and only consider other paths if needed.
  3) If `SKILL.md` points to extra folders such as `references/`, load only the specific files needed for the request; do not bulk-load everything.
  4) If `scripts/` exist, prefer running or patching them instead of retyping large code blocks.
  5) If `assets/` or templates exist, reuse them instead of recreating from scratch.
- Coordination and sequencing:
  - If multiple skills apply, choose the minimal set that covers the request and state the order.
  - Announce which skill(s) are being used and why in one short line.
- Context hygiene:
  - Keep context small: summarize long sections instead of pasting them; only load extra files when needed.
  - Avoid deep reference chasing: prefer opening only files directly linked from `SKILL.md` unless blocked.
- Safety and fallback: If a skill cannot be applied cleanly (missing files, unclear instructions), state the issue, pick the next-best approach, and continue.

### Mandatory Python environment rule
- For any turn that runs Python commands in this repository, run `python-venv-guard` first.
- Never run Python with global interpreters (`python`, `python3`, `pip`, `pip3`) for project tasks.
- Always use project virtual environment interpreter directly (for this repo: `/Users/panyihang/Documents/aicomm/ai_judge_service/.venv/bin/python`).

### Mandatory pre-development hook
- For any turn that starts module-level implementation/refactor/fix in this repository, run `pre-module-mvp-plan-guard` before coding.
- The pre-development hook must read `/Users/panyihang/Documents/aicomm/docs/产品化开发计划-在线辩论AI裁判平台.md`.
- It must verify that the target module is within MVP roadmap scope; if off-road, record adjustment reason and update the plan doc first.
- It must append an alignment record in the plan doc before coding starts.

### Mandatory post-module hook
- For any turn that includes module-level code implementation/refactor/fix in this repository, run `post-module-test-guard` after coding and before final verification sign-off.
- Then run `post-module-plan-sync` before interview/explanation journaling.
- Then run `post-module-interview-journal` before the final user response.
- Then run `post-module-explanation-journal` before the final user response.
- The testing hook must:
  - check whether test changes are missing for production/module code changes
  - generate or update tests when needed
  - run project test gates and only pass when all required checks succeed
- The interview journal hook must update:
  - `docs/interview/01-development-log.md`
  - `docs/interview/02-troubleshooting-log.md`
  - `docs/interview/03-interview-qa-log.md`
- The plan sync hook must:
  - update `/Users/panyihang/Documents/aicomm/docs/产品化开发计划-在线辩论AI裁判平台.md`
  - rewrite “下一开发模块建议”与“已完成/未完成矩阵”
  - append module completion sync history
- The explanation journal hook must:
  - follow `docs/explanation/00-讲解规范.md`
  - create a new markdown file under `docs/explanation/`
  - explain only new/modified code paths with architecture, execution flow, tradeoffs, and testing evidence
