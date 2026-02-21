## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.

### Available skills
- skill-creator: Guide for creating effective skills. Use when users want to create a new skill (or update an existing skill) that extends Codex capabilities with specialized knowledge, workflows, or tool integrations. (file: /Users/panyihang/.codex/skills/.system/skill-creator/SKILL.md)
- skill-installer: Install Codex skills into `$CODEX_HOME/skills` from a curated list or a GitHub repo path. Use when users ask to list installable skills, install a curated skill, or install a skill from another repo (including private repos). (file: /Users/panyihang/.codex/skills/.system/skill-installer/SKILL.md)
- post-module-test-guard: Generate or update tests for changed module behavior and run repository quality gates after implementation. Use when a turn includes module-level code changes and you must ensure tests are present and passing before considering the module complete. (file: /Users/panyihang/Documents/aicomm/skills/post-module-test-guard/SKILL.md)
- post-module-interview-journal: Generate interview-ready development records after each module implementation. Use when a turn includes feature/module code changes and you need to update development log, troubleshooting log, and interview Q&A materials. (file: /Users/panyihang/Documents/aicomm/skills/post-module-interview-journal/SKILL.md)

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

### Mandatory post-module hook
- For any turn that includes module-level code implementation/refactor/fix in this repository, run `post-module-test-guard` after coding and before final verification sign-off.
- Then run `post-module-interview-journal` before the final user response.
- The testing hook must:
  - check whether test changes are missing for production/module code changes
  - generate or update tests when needed
  - run project test gates and only pass when all required checks succeed
- The interview journal hook must update:
  - `docs/interview/01-development-log.md`
  - `docs/interview/02-troubleshooting-log.md`
  - `docs/interview/03-interview-qa-log.md`
