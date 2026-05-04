from __future__ import annotations

import httpx

from .models import NpcActionCandidate, NpcDecisionContext, SubmitActionCandidateOutput
from .settings import Settings


class NpcChatClient:
    def __init__(self, *, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    async def submit_action_candidate(
        self,
        candidate: NpcActionCandidate,
    ) -> SubmitActionCandidateOutput:
        payload = candidate.model_dump(by_alias=True, exclude_none=True)
        client = self._client
        if client is None:
            async with httpx.AsyncClient(timeout=8.0) as owned_client:
                return await self._post(owned_client, payload)
        return await self._post(client, payload)

    async def fetch_decision_context(
        self,
        *,
        session_id: int,
        trigger_message_id: int,
        source_event_id: str | None,
        limit: int | None = None,
    ) -> NpcDecisionContext:
        client = self._client
        if client is None:
            async with httpx.AsyncClient(timeout=8.0) as owned_client:
                return await self._get_context(
                    owned_client,
                    session_id=session_id,
                    trigger_message_id=trigger_message_id,
                    source_event_id=source_event_id,
                    limit=limit,
                )
        return await self._get_context(
            client,
            session_id=session_id,
            trigger_message_id=trigger_message_id,
            source_event_id=source_event_id,
            limit=limit,
        )

    async def _post(
        self,
        client: httpx.AsyncClient,
        payload: dict,
    ) -> SubmitActionCandidateOutput:
        response = await client.post(
            _join_url(self._settings.chat_server_base_url, self._settings.chat_action_candidate_path),
            headers={"x-ai-internal-key": self._settings.ai_internal_key},
            json=payload,
        )
        if response.status_code // 100 != 2:
            raise RuntimeError(
                f"npc action candidate callback failed: status={response.status_code}, "
                f"body={response.text[:500]}"
            )
        return SubmitActionCandidateOutput.model_validate(response.json())

    async def _get_context(
        self,
        client: httpx.AsyncClient,
        *,
        session_id: int,
        trigger_message_id: int,
        source_event_id: str | None,
        limit: int | None,
    ) -> NpcDecisionContext:
        params: dict[str, object] = {"triggerMessageId": trigger_message_id}
        if source_event_id:
            params["sourceEventId"] = source_event_id
        if limit is not None:
            params["limit"] = limit
        path = self._settings.chat_context_path_template.format(session_id=session_id)
        response = await client.get(
            _join_url(self._settings.chat_server_base_url, path),
            headers={"x-ai-internal-key": self._settings.ai_internal_key},
            params=params,
        )
        if response.status_code // 100 != 2:
            raise RuntimeError(
                f"npc context fetch failed: status={response.status_code}, "
                f"body={response.text[:500]}"
            )
        return NpcDecisionContext.model_validate(response.json())


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
