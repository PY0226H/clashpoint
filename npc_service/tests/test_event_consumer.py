from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from app.event_consumer import (
    EVENT_TYPE_DEBATE_MESSAGE_CREATED,
    NpcConsumerRecord,
    NpcEventConsumer,
    NpcEventSource,
    debate_message_created_trigger_from_envelope,
    decode_event_envelope,
    resolve_topic_name,
)
from app.models import (
    DebateMessageCreatedTrigger,
    NpcDecisionRun,
    NpcEventProcessingRun,
)

from helpers import make_settings, make_trigger


def make_record(*, event_id: str = "evt-1", event_type: str = EVENT_TYPE_DEBATE_MESSAGE_CREATED) -> NpcConsumerRecord:
    trigger = make_trigger()
    return NpcConsumerRecord(
        topic="echoisle.debate.message.created.v1",
        partition=0,
        offset=42,
        key="session:77",
        value=json.dumps(
            {
                "eventId": event_id,
                "eventType": event_type,
                "source": "chat-server",
                "aggregateId": "session:77",
                "occurredAt": "2026-05-03T00:00:00Z",
                "payload": {
                    "sessionId": trigger.session_id,
                    "messageId": trigger.message_id,
                    "userId": trigger.user_id,
                    "side": trigger.side,
                    "content": trigger.content,
                    "createdAt": trigger.created_at,
                },
            }
        ),
    )


def silent_run(trigger: DebateMessageCreatedTrigger) -> NpcEventProcessingRun:
    return NpcEventProcessingRun(
        status="silent",
        trigger=trigger,
        decisionRun=NpcDecisionRun(
            status="silent",
            executorKind="llm_executor_v1",
            executorVersion="llm_executor_v1",
            fallbackUsed=False,
        ),
    )


class FakeProcessor:
    def __init__(self, runs: list[NpcEventProcessingRun | Exception]) -> None:
        self.runs = runs
        self.triggers: list[DebateMessageCreatedTrigger] = []

    async def handle_debate_message_created(
        self,
        trigger: DebateMessageCreatedTrigger,
    ) -> NpcEventProcessingRun:
        self.triggers.append(trigger)
        next_run = self.runs.pop(0)
        if isinstance(next_run, Exception):
            raise next_run
        return next_run


class FakeSource(NpcEventSource):
    def __init__(self, records: list[NpcConsumerRecord]) -> None:
        self._records = records
        self.committed: list[str] = []
        self.closed = False

    async def records(self) -> AsyncIterator[NpcConsumerRecord]:
        for record in self._records:
            yield record

    async def commit(self, record: NpcConsumerRecord) -> None:
        self.committed.append(record.record_id)

    async def close(self) -> None:
        self.closed = True


def test_consumer_decodes_kafka_envelope_into_debate_message_trigger() -> None:
    envelope = decode_event_envelope(make_record(event_id="evt-kafka-1"))
    trigger = debate_message_created_trigger_from_envelope(envelope)

    assert trigger == DebateMessageCreatedTrigger(
        event="DebateMessageCreated",
        sessionId=77,
        messageId=1001,
        userId=42,
        side="pro",
        content="这段发言把核心矛盾说清楚了，值得回应。",
        createdAt="2026-05-03T00:00:00Z",
        sourceEventId="evt-kafka-1",
    )


def test_consumer_processes_terminal_event_and_should_commit() -> None:
    async def scenario() -> None:
        record = make_record(event_id="evt-terminal")
        processor = FakeProcessor([silent_run(make_trigger())])
        consumer = NpcEventConsumer(
            settings=make_settings().event_consumer,
            processor=processor,  # type: ignore[arg-type]
        )

        result = await consumer.process_record(record)

        assert result.status == "processed_committed"
        assert result.should_commit is True
        assert result.event_id == "evt-terminal"
        assert processor.triggers[0].source_event_id == "evt-terminal"

    asyncio.run(scenario())


def test_consumer_retries_before_dlq_and_commits_after_attempts_exhausted(tmp_path: Path) -> None:
    async def scenario() -> None:
        dlq_path = tmp_path / "npc-dlq.jsonl"
        settings = make_settings(
            event_consumer_max_attempts=2,
            event_consumer_dlq_path=str(dlq_path),
        ).event_consumer
        processor = FakeProcessor([RuntimeError("chat unavailable"), RuntimeError("chat unavailable")])
        consumer = NpcEventConsumer(
            settings=settings,
            processor=processor,  # type: ignore[arg-type]
        )
        record = make_record(event_id="evt-retry")

        first = await consumer.process_record(record)
        second = await consumer.process_record(record)

        assert first.status == "retry_scheduled"
        assert first.should_commit is False
        assert first.failure_count == 1
        assert second.status == "retry_exhausted_dlq_committed"
        assert second.should_commit is True
        assert second.failure_count == 2
        lines = dlq_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["eventId"] == "evt-retry"
        assert payload["failureCount"] == 2
        assert payload["record"] == {
            "topic": "echoisle.debate.message.created.v1",
            "partition": 0,
            "offset": 42,
            "key": "session:77",
        }

    asyncio.run(scenario())


def test_consumer_writes_invalid_envelope_to_dlq_and_commits(tmp_path: Path) -> None:
    async def scenario() -> None:
        dlq_path = tmp_path / "npc-invalid-dlq.jsonl"
        settings = make_settings(event_consumer_dlq_path=str(dlq_path)).event_consumer
        consumer = NpcEventConsumer(
            settings=settings,
            processor=FakeProcessor([]),  # type: ignore[arg-type]
        )
        result = await consumer.process_record(
            NpcConsumerRecord(
                topic="echoisle.debate.message.created.v1",
                partition=0,
                offset=1,
                value="{not-json",
            )
        )

        assert result.status == "invalid_dlq_committed"
        assert result.should_commit is True
        payload = json.loads(dlq_path.read_text(encoding="utf-8"))
        assert payload["eventId"] is None
        assert payload["failureCount"] == 1

    asyncio.run(scenario())


def test_consume_commits_only_terminal_records(tmp_path: Path) -> None:
    async def scenario() -> None:
        dlq_path = tmp_path / "npc-consume-dlq.jsonl"
        settings = make_settings(
            event_consumer_max_attempts=2,
            event_consumer_dlq_path=str(dlq_path),
        ).event_consumer
        source = FakeSource(
            [
                make_record(event_id="evt-commit", event_type=EVENT_TYPE_DEBATE_MESSAGE_CREATED),
                make_record(event_id="evt-retry", event_type=EVENT_TYPE_DEBATE_MESSAGE_CREATED),
            ]
        )
        processor = FakeProcessor(
            [
                silent_run(make_trigger()),
                RuntimeError("transient context fetch failure"),
            ]
        )
        consumer = NpcEventConsumer(
            settings=settings,
            processor=processor,  # type: ignore[arg-type]
        )

        await consumer.consume(source)

        assert source.committed == ["echoisle.debate.message.created.v1:0:42"]
        assert source.closed is True
        assert not dlq_path.exists()

    asyncio.run(scenario())


def test_consumer_ignores_unsupported_event_type_and_commits() -> None:
    async def scenario() -> None:
        consumer = NpcEventConsumer(
            settings=make_settings().event_consumer,
            processor=FakeProcessor([]),  # type: ignore[arg-type]
        )
        result = await consumer.process_record(
            make_record(event_id="evt-other", event_type="debate.message.pinned")
        )

        assert result.status == "ignored_unsupported_event"
        assert result.should_commit is True
        assert result.event_id == "evt-other"

    asyncio.run(scenario())


def test_resolve_topic_name_keeps_existing_prefix_stable() -> None:
    assert resolve_topic_name("echoisle", "debate.message.created.v1") == (
        "echoisle.debate.message.created.v1"
    )
    assert resolve_topic_name("echoisle", "echoisle.debate.message.created.v1") == (
        "echoisle.debate.message.created.v1"
    )
    assert resolve_topic_name("", "debate.message.created.v1") == "debate.message.created.v1"
