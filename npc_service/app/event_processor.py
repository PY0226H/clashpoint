from __future__ import annotations

import asyncio

from .chat_client import NpcChatClient
from .models import (
    DebateMessageCreatedTrigger,
    NpcDecisionContext,
    NpcDecisionRun,
    NpcEventProcessingRun,
)
from .settings import Settings


class DecisionRouterProtocol:
    async def decide(self, context: NpcDecisionContext) -> NpcDecisionRun:
        pass


class NpcEventProcessor:
    def __init__(
        self,
        *,
        settings: Settings,
        router: DecisionRouterProtocol,
        chat_client: NpcChatClient,
    ) -> None:
        self._settings = settings
        self._router = router
        self._chat_client = chat_client
        self.dlq: list[NpcEventProcessingRun] = []

    async def handle_debate_message_created(
        self,
        trigger: DebateMessageCreatedTrigger,
    ) -> NpcEventProcessingRun:
        context = await self._chat_client.fetch_decision_context(
            session_id=trigger.session_id,
            trigger_message_id=trigger.message_id,
            source_event_id=trigger.source_event_id,
        )
        control_plane_decision = _control_plane_silent_decision(context)
        if control_plane_decision is not None:
            return NpcEventProcessingRun(
                status="silent",
                trigger=trigger,
                decisionRun=control_plane_decision,
                failures=control_plane_decision.failures,
            )
        decision_run = await self._router.decide(context)
        if decision_run.candidate is None:
            return NpcEventProcessingRun(
                status="silent" if decision_run.status == "silent" else "decision_rejected",
                trigger=trigger,
                decisionRun=decision_run,
                failures=decision_run.failures,
            )
        failures: list[str] = []
        submit_attempts = 0
        for attempt in range(1, self._settings.event_submit_max_attempts + 1):
            submit_attempts = attempt
            try:
                submit_result = await self._chat_client.submit_action_candidate(
                    decision_run.candidate
                )
                return NpcEventProcessingRun(
                    status="submitted" if submit_result.accepted else "candidate_rejected",
                    trigger=trigger,
                    decisionRun=decision_run,
                    submitResult=submit_result,
                    submitAttempts=submit_attempts,
                    failures=[*decision_run.failures, *failures],
                )
            except Exception as err:
                failures.append(f"submit_attempt_{attempt}:{err}"[:300])
                if attempt < self._settings.event_submit_max_attempts:
                    await asyncio.sleep(self._settings.event_submit_retry_backoff_ms / 1000)
        run = NpcEventProcessingRun(
            status="submit_failed",
            trigger=trigger,
            decisionRun=decision_run,
            submitAttempts=submit_attempts,
            failures=[*decision_run.failures, *failures],
        )
        self.dlq.append(run)
        return run


def _control_plane_silent_decision(context: NpcDecisionContext) -> NpcDecisionRun | None:
    config = context.room_config
    reason: str | None = None
    if not config.enabled:
        reason = "npc_disabled"
    elif config.status != "active":
        reason = f"npc_status_{config.status}"
    elif not (config.allow_speak or config.allow_praise or config.allow_effect):
        reason = "npc_public_capabilities_disabled"
    if reason is None:
        return None
    return NpcDecisionRun(
        status="silent",
        executorKind="control_plane",
        executorVersion="ops_control_plane_v1",
        fallbackUsed=False,
        fallbackReason=reason,
        candidate=None,
        guardReason=reason,
        failures=[],
    )
