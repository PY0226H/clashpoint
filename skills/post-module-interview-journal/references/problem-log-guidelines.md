# Problem Log Guidelines

## Write Every Problem with This Structure
- Symptom: what failed, where, and impact.
- Root Cause: concrete technical cause, not guesswork.
- Fix: exact code/config/process change.
- Verification: how you proved it was fixed.
- Prevention: what guardrail you added (test/checklist/monitoring).

## Quality Bar
- Prefer measurable facts over vague statements.
- Include one failed attempt if it taught a useful lesson.
- Tie every fix to at least one verification signal.
- Avoid blame language; describe systems and decisions.

## Example Format
- Symptom: `POST /api/upload` returned `500` for files > 20MB.
- Root Cause: handler read entire file into memory; OOM under concurrent uploads.
- Fix: switched to streaming write and set request body limit.
- Verification: load test with 50 concurrent uploads passed; memory stayed under 300MB.
- Prevention: added integration test and alert for process RSS growth.
