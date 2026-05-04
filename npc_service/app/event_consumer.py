from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .event_processor import NpcEventProcessor
from .models import DebateMessageCreatedTrigger, NpcEventProcessingRun, utc_now_iso
from .settings import EventConsumerSettings

EVENT_TYPE_DEBATE_MESSAGE_CREATED = "debate.message.created"
TOPIC_DEBATE_MESSAGE_CREATED = "debate.message.created.v1"
TERMINAL_PROCESSING_STATUSES = {
    "submitted",
    "candidate_rejected",
    "silent",
    "decision_rejected",
}


class NpcConsumerDecodeError(ValueError):
    pass


class KafkaEventEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(alias="eventId")
    event_type: str = Field(alias="eventType")
    source: str
    aggregate_id: str = Field(alias="aggregateId")
    occurred_at: str = Field(alias="occurredAt")
    payload: dict[str, Any]


@dataclass(frozen=True)
class NpcConsumerRecord:
    topic: str
    partition: int
    offset: int
    value: str
    key: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)

    @property
    def record_id(self) -> str:
        return f"{self.topic}:{self.partition}:{self.offset}"


@dataclass(frozen=True)
class NpcConsumerProcessResult:
    status: str
    should_commit: bool
    record_id: str
    event_id: str | None = None
    failure_count: int = 0
    processing_run: NpcEventProcessingRun | None = None
    error: str | None = None


class NpcEventSource(Protocol):
    async def records(self) -> AsyncIterator[NpcConsumerRecord]:
        pass

    async def commit(self, record: NpcConsumerRecord) -> None:
        pass

    async def close(self) -> None:
        pass


class NpcConsumerDlqWriter:
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def write(
        self,
        *,
        record: NpcConsumerRecord,
        failure_count: int,
        error: str,
        event_id: str | None = None,
        processing_run: NpcEventProcessingRun | None = None,
    ) -> None:
        if self._path.parent != Path("."):
            self._path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "writtenAt": utc_now_iso(),
            "record": {
                "topic": record.topic,
                "partition": record.partition,
                "offset": record.offset,
                "key": record.key,
            },
            "eventId": event_id,
            "failureCount": failure_count,
            "error": error[:1000],
        }
        if processing_run is not None:
            payload["processingRun"] = processing_run.model_dump(by_alias=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


class NpcEventConsumer:
    def __init__(
        self,
        *,
        settings: EventConsumerSettings,
        processor: NpcEventProcessor,
        dlq_writer: NpcConsumerDlqWriter | None = None,
    ) -> None:
        self._settings = settings
        self._processor = processor
        self._dlq_writer = dlq_writer or NpcConsumerDlqWriter(settings.dlq_path)
        self._failure_counts: dict[str, int] = {}

    async def process_record(self, record: NpcConsumerRecord) -> NpcConsumerProcessResult:
        try:
            envelope = decode_event_envelope(record)
        except NpcConsumerDecodeError as err:
            self._dlq_writer.write(
                record=record,
                failure_count=1,
                error=str(err),
                event_id=None,
            )
            return NpcConsumerProcessResult(
                status="invalid_dlq_committed",
                should_commit=True,
                record_id=record.record_id,
                failure_count=1,
                error=str(err),
            )

        if envelope.event_type != EVENT_TYPE_DEBATE_MESSAGE_CREATED:
            return NpcConsumerProcessResult(
                status="ignored_unsupported_event",
                should_commit=True,
                record_id=record.record_id,
                event_id=envelope.event_id,
            )

        try:
            trigger = debate_message_created_trigger_from_envelope(envelope)
            processing_run = await self._processor.handle_debate_message_created(trigger)
        except Exception as err:
            return await self._handle_retryable_failure(
                record=record,
                event_id=envelope.event_id,
                error=str(err),
                processing_run=None,
            )

        if processing_run.status in TERMINAL_PROCESSING_STATUSES:
            self._failure_counts.pop(envelope.event_id, None)
            return NpcConsumerProcessResult(
                status="processed_committed",
                should_commit=True,
                record_id=record.record_id,
                event_id=envelope.event_id,
                processing_run=processing_run,
            )

        return await self._handle_retryable_failure(
            record=record,
            event_id=envelope.event_id,
            error=f"processing_status:{processing_run.status}",
            processing_run=processing_run,
        )

    async def consume(self, source: NpcEventSource) -> None:
        try:
            async for record in source.records():
                result = await self.process_record(record)
                if result.should_commit:
                    await source.commit(record)
                elif self._settings.retry_backoff_ms > 0:
                    await asyncio.sleep(self._settings.retry_backoff_ms / 1000)
        finally:
            await source.close()

    async def _handle_retryable_failure(
        self,
        *,
        record: NpcConsumerRecord,
        event_id: str,
        error: str,
        processing_run: NpcEventProcessingRun | None,
    ) -> NpcConsumerProcessResult:
        failure_count = self._failure_counts.get(event_id, 0) + 1
        self._failure_counts[event_id] = failure_count
        if failure_count >= self._settings.max_attempts:
            self._dlq_writer.write(
                record=record,
                event_id=event_id,
                failure_count=failure_count,
                error=error,
                processing_run=processing_run,
            )
            self._failure_counts.pop(event_id, None)
            return NpcConsumerProcessResult(
                status="retry_exhausted_dlq_committed",
                should_commit=True,
                record_id=record.record_id,
                event_id=event_id,
                failure_count=failure_count,
                processing_run=processing_run,
                error=error,
            )
        return NpcConsumerProcessResult(
            status="retry_scheduled",
            should_commit=False,
            record_id=record.record_id,
            event_id=event_id,
            failure_count=failure_count,
            processing_run=processing_run,
            error=error,
        )


class KafkaNpcEventSource:
    def __init__(self, settings: EventConsumerSettings) -> None:
        self._settings = settings
        self._consumer: Any | None = None

    async def records(self) -> AsyncIterator[NpcConsumerRecord]:
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError as err:
            raise RuntimeError(
                "NPC_EVENT_CONSUMER_SOURCE=kafka requires aiokafka to be installed"
            ) from err

        topics = tuple(resolve_topic_name(self._settings.topic_prefix, topic) for topic in self._settings.consume_topics)
        self._consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self._settings.brokers,
            group_id=self._settings.group_id,
            client_id=self._settings.client_id,
            enable_auto_commit=False,
        )
        await self._consumer.start()
        try:
            async for msg in self._consumer:
                value = msg.value.decode("utf-8") if isinstance(msg.value, bytes) else str(msg.value)
                key = msg.key.decode("utf-8") if isinstance(msg.key, bytes) else msg.key
                yield NpcConsumerRecord(
                    topic=msg.topic,
                    partition=msg.partition,
                    offset=msg.offset,
                    key=key,
                    value=value,
                )
        finally:
            await self.close()

    async def commit(self, record: NpcConsumerRecord) -> None:
        if self._consumer is not None:
            await self._consumer.commit()

    async def close(self) -> None:
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None


def create_event_source(settings: EventConsumerSettings) -> NpcEventSource:
    if settings.source != "kafka":
        raise ValueError(f"unsupported NPC event consumer source: {settings.source}")
    return KafkaNpcEventSource(settings)


async def run_event_consumer_loop(
    *,
    settings: EventConsumerSettings,
    processor: NpcEventProcessor,
) -> None:
    if not settings.enabled:
        return
    consumer = NpcEventConsumer(settings=settings, processor=processor)
    source = create_event_source(settings)
    await consumer.consume(source)


def decode_event_envelope(record: NpcConsumerRecord) -> KafkaEventEnvelope:
    try:
        raw = json.loads(record.value)
    except json.JSONDecodeError as err:
        raise NpcConsumerDecodeError(f"decode envelope failed: {err}") from err
    try:
        return KafkaEventEnvelope.model_validate(raw)
    except ValidationError as err:
        raise NpcConsumerDecodeError(f"invalid envelope: {err}") from err


def debate_message_created_trigger_from_envelope(
    envelope: KafkaEventEnvelope,
) -> DebateMessageCreatedTrigger:
    payload = envelope.payload
    try:
        return DebateMessageCreatedTrigger(
            event="DebateMessageCreated",
            sessionId=payload["sessionId"],
            messageId=payload["messageId"],
            userId=payload["userId"],
            side=payload["side"],
            content=payload["content"],
            createdAt=payload["createdAt"],
            sourceEventId=envelope.event_id,
        )
    except (KeyError, ValidationError) as err:
        raise NpcConsumerDecodeError(f"invalid DebateMessageCreated payload: {err}") from err


def resolve_topic_name(prefix: str, base_topic: str) -> str:
    clean_prefix = prefix.strip()
    if not clean_prefix:
        return base_topic
    if base_topic.startswith(f"{clean_prefix}."):
        return base_topic
    return f"{clean_prefix}.{base_topic}"


async def stop_background_task(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
