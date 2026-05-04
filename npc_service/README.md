# EchoIsle NPC Service

Virtual judge NPC service for room-visible entertainment actions.

Current slice: P1-B event consumer cutover.

Responsibilities:

1. Accept a public debate decision context.
2. Prefer `llm_executor_v1` through an OpenAI-compatible provider.
3. Fall back to `rule_executor_v1` when LLM is unavailable or blocked by guard.
4. Produce `NpcActionCandidate` payloads for `chat`.
5. Consume `DebateMessageCreated` through the long-term event consumer and fetch public room context from `chat`.

Non-responsibilities:

1. No official verdict generation.
2. No private chat with users.
3. No direct database writes.
4. No direct WebSocket broadcast.

P1-B long-term event path:

1. Install the Kafka runtime extra for deployments that enable the consumer.
2. `NPC_EVENT_CONSUMER_ENABLED=true` starts the background event consumer.
3. The consumer reads `DebateMessageCreated` envelopes from Kafka / event bus.
4. `npc_service` fetches context from `chat` through `/api/internal/ai/debate/npc/sessions/{session_id}/context`.
5. The executor router decides, then submits the guarded candidate to `/api/internal/ai/debate/npc/actions/candidates`.
6. The legacy webhook trigger is disabled by default and can only be enabled for local development with `NPC_EVENT_WEBHOOK_ENABLED=true`.

Run locally:

```bash
cd /Users/panyihang/Documents/EchoIsle/npc_service
/Users/panyihang/Documents/EchoIsle/ai_judge_service/.venv/bin/python -m uvicorn app.main:app --reload --port 6690
```
