# EchoIsle NPC Service

Virtual judge NPC service for room-visible entertainment actions.

Current slice: P2-E event consumption loop.

Responsibilities:

1. Accept a public debate decision context.
2. Prefer `llm_executor_v1` through an OpenAI-compatible provider.
3. Fall back to `rule_executor_v1` when LLM is unavailable or blocked by guard.
4. Produce `NpcActionCandidate` payloads for `chat`.
5. Receive internal `DebateMessageCreated` triggers and fetch public room context from `chat`.

Non-responsibilities:

1. No official verdict generation.
2. No private chat with users.
3. No direct database writes.
4. No direct WebSocket broadcast.

P2-E local MVP path:

1. `POST /api/internal/npc/events/debate-message-created` receives an internal trigger.
2. `npc_service` fetches context from `chat` through `/api/internal/ai/debate/npc/sessions/{session_id}/context`.
3. The executor router decides, then submits the guarded candidate to `/api/internal/ai/debate/npc/actions/candidates`.
4. This webhook trigger should be removed after the Kafka/event-bus consumer owns ingestion end to end.

Run locally:

```bash
cd /Users/panyihang/Documents/EchoIsle/npc_service
/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m uvicorn app.main:app --reload --port 6690
```
