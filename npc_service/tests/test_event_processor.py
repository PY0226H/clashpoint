from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from app.chat_client import NpcChatClient
from app.event_processor import NpcEventProcessor
from app.guard import candidate_from_raw_output
from app.models import NpcDecisionContext, NpcDecisionRun

from helpers import make_context, make_settings, make_trigger


class FakeRouter:
    def __init__(self, raw_action: dict[str, Any] | None = None) -> None:
        self.raw_action = raw_action or {
            "actionType": "praise",
            "publicText": "这个回应抓住了重点。",
            "targetMessageId": 1001,
        }
        self.context: NpcDecisionContext | None = None

    async def decide(self, context: NpcDecisionContext) -> NpcDecisionRun:
        self.context = context
        settings = make_settings()
        return NpcDecisionRun(
            status="created",
            executorKind="llm_executor_v1",
            executorVersion="llm_executor_v1",
            fallbackUsed=False,
            candidate=candidate_from_raw_output(
                self.raw_action,
                context=context,
                settings=settings,
                executor_kind="llm_executor_v1",
                executor_version="llm_executor_v1",
            ),
        )


def test_event_processor_fetches_context_decides_and_submits_candidate() -> None:
    async def scenario() -> None:
        observed: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                observed["context_url"] = str(request.url)
                return httpx.Response(200, json=make_context().model_dump(by_alias=True))
            observed["candidate_payload"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "accepted": True,
                    "actionId": 901,
                    "actionUid": observed["candidate_payload"]["actionUid"],
                    "status": "created",
                    "reasonCode": None,
                },
            )

        settings = make_settings()
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            router = FakeRouter()
            processor = NpcEventProcessor(
                settings=settings,
                router=router,
                chat_client=NpcChatClient(settings=settings, client=client),
            )

            run = await processor.handle_debate_message_created(make_trigger())

        assert run.status == "submitted"
        assert run.submit_attempts == 1
        assert run.submit_result is not None
        assert run.submit_result.action_id == 901
        assert router.context is not None
        assert router.context.source_event_id == "evt-1"
        assert observed["candidate_payload"]["actionType"] == "praise"
        assert observed["candidate_payload"]["sourceMessageId"] == 1001

    asyncio.run(scenario())


def test_event_processor_does_not_retry_when_chat_rejects_candidate() -> None:
    async def scenario() -> None:
        post_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal post_count
            if request.method == "GET":
                return httpx.Response(200, json=make_context().model_dump(by_alias=True))
            post_count += 1
            payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "accepted": False,
                    "actionId": None,
                    "actionUid": payload["actionUid"],
                    "status": "rejected",
                    "reasonCode": "npc_rate_limited",
                },
            )

        settings = make_settings(event_submit_max_attempts=3)
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            processor = NpcEventProcessor(
                settings=settings,
                router=FakeRouter(),
                chat_client=NpcChatClient(settings=settings, client=client),
            )

            run = await processor.handle_debate_message_created(make_trigger())

        assert run.status == "candidate_rejected"
        assert run.submit_attempts == 1
        assert run.submit_result is not None
        assert run.submit_result.reason_code == "npc_rate_limited"
        assert post_count == 1

    asyncio.run(scenario())


def test_event_processor_retries_submit_failure_and_records_dlq() -> None:
    async def scenario() -> None:
        post_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal post_count
            if request.method == "GET":
                return httpx.Response(200, json=make_context().model_dump(by_alias=True))
            post_count += 1
            return httpx.Response(503, json={"error": "temporarily unavailable"})

        settings = make_settings(event_submit_max_attempts=2)
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            processor = NpcEventProcessor(
                settings=settings,
                router=FakeRouter(),
                chat_client=NpcChatClient(settings=settings, client=client),
            )

            run = await processor.handle_debate_message_created(make_trigger())

        assert run.status == "submit_failed"
        assert run.submit_attempts == 2
        assert len(run.failures) == 2
        assert post_count == 2
        assert processor.dlq == [run]

    asyncio.run(scenario())
