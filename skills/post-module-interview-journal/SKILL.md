---
name: post-module-interview-journal
description: "Generate and maintain interview-ready development documentation after each module implementation. Use when a coding task modifies module logic, APIs, data models, infrastructure, or tests and the team needs three outputs immediately after coding: (1) development log, (2) troubleshooting/incident log, and (3) interview Q&A/knowledge points for campus or social hiring preparation."
---

# Post Module Interview Journal

## Overview
Convert every module change into reusable interview assets with minimal manual work.
Write structured records for what changed, why it changed, what broke, how it was fixed, and how to explain it in interviews.

## Workflow
1. Collect module context after implementation and verification.
2. Run the update script to append documentation entries.
3. Review generated entries and fill missing technical depth.
4. Reference updated docs in the final user response.

## Output Language
- Generate log content in Chinese by default.
- Keep technical keywords in English only when necessary (for example: `JWT`, `CORS`, `SSE`).

## Step 1: Collect Inputs
Collect the following data before writing docs:
- Module name: stable identifier like `auth-hardening` or `file-upload-streaming`.
- Business/engineering summary: what changed and why.
- Changed files: semicolon-separated paths.
- Tests/verification: commands and outcomes.
- Issues and fixes: issue-to-fix pairs, semicolon-separated.
- Learnings/interview points: semicolon-separated keywords.

Use this format:
- `changes`: `path/a.rs;path/b.ts;path/c.yml`
- `issues`: `panic in middleware => replace unwrap with error mapping;SSE reconnect storm => add backoff`
- `learnings`: `JWT auth chain;Rust error handling;CORS least privilege`

## Step 2: Run Script
Run:

```bash
bash skills/post-module-interview-journal/scripts/update_module_docs.sh \
  --module "<module-name>" \
  --summary "<what changed and why>" \
  --changes "<path1;path2;...>" \
  --tests "<verification commands and results>" \
  --issues "<issue => fix;issue2 => fix2>" \
  --learnings "<point1;point2;point3>"
```

If `--changes` is omitted, the script tries to infer changed files from git status.

## Step 3: Check Outputs
Verify these files were updated:
- `docs/interview/01-development-log.md`
- `docs/interview/02-troubleshooting-log.md`
- `docs/interview/03-interview-qa-log.md`

Ensure entries are concrete and interview-safe:
- Mention design tradeoff, not just final solution.
- Mention failure mode and mitigation.
- Mention test strategy and confidence boundaries.

## Step 4: Enrich for Interview Value
Open references only when needed:
- `references/interview-knowledge-map.md`: map changes to interview topics and follow-up questions.
- `references/problem-log-guidelines.md`: ensure issue/fix writing quality.

When a module is security/performance/reliability related, add at least one deep-dive Q&A in `03-interview-qa-log.md`.

## Final Response Requirements
After running this skill in a coding turn:
- Explicitly state documentation was updated.
- Provide absolute paths to the three output files.
- List 2-4 key interview talking points extracted from the module.

## Resources

### scripts/
- `scripts/update_module_docs.sh`: append standardized entries to the three interview documentation files.

### references/
- `references/interview-knowledge-map.md`: backend/frontend/devops/testing topic map.
- `references/problem-log-guidelines.md`: rules for documenting failures, root causes, and fixes.

### assets/
- `assets/module-entry-template.md`: canonical entry template for manual refinements.
