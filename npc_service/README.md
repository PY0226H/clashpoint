# EchoIsle NPC Service

Virtual judge NPC service for room-visible entertainment actions.

Current slice: P2-D service skeleton and executor router.

Responsibilities:

1. Accept a public debate decision context.
2. Prefer `llm_executor_v1` through an OpenAI-compatible provider.
3. Fall back to `rule_executor_v1` when LLM is unavailable or blocked by guard.
4. Produce `NpcActionCandidate` payloads for `chat`.

Non-responsibilities:

1. No official verdict generation.
2. No private chat with users.
3. No direct database writes.
4. No direct WebSocket broadcast.

Run locally:

```bash
cd /Users/panyihang/Documents/EchoIsle/npc_service
/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m uvicorn app.main:app --reload --port 6690
```
