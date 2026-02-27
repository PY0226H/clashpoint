from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .openai_judge_client import OpenAiConfigProtocol, call_openai_json
from .openai_judge_helpers import (
    _build_aggregate_system_prompt,
    _build_aggregate_user_prompt,
    _build_display_system_prompt,
    _build_display_user_prompt,
    _build_final_system_prompt,
    _build_final_user_prompt,
    _build_stage_summary_fallback,
    _build_stage_system_prompt,
    _build_stage_user_prompt,
    _merge_two_pass,
    _normalize_aggregate_eval,
    _normalize_display_eval,
    _normalize_eval,
    _normalize_stage_eval,
    _split_message_chunks,
)
from .rag_retriever import RetrievedContext
from .scoring_core import DebateMessage

if TYPE_CHECKING:
    from .models import JudgeDispatchRequest


@dataclass(frozen=True)
class OpenAiJudgePipelineResult:
    stage_summaries: list[dict[str, Any]]
    stage_fallback_count: int
    aggregate_summary: dict[str, Any]
    aggregate_fallback: bool
    final_fallback_count: int
    merged: dict[str, Any]
    display: dict[str, str]
    display_fallback: bool


async def _build_stage_summaries_with_openai(
    *,
    cfg: OpenAiConfigProtocol,
    request: "JudgeDispatchRequest",
    messages: list[DebateMessage],
    retrieved_contexts: list[RetrievedContext],
    style_mode: str,
    max_stage_agent_chunks: int,
) -> tuple[list[dict[str, Any]], int]:
    chunks = _split_message_chunks(
        messages,
        request.message_window_size,
        max_stage_agent_chunks,
    )
    if not chunks:
        return [], 0

    stage_summaries: list[dict[str, Any]] = []
    fallback_count = 0
    stage_count = len(chunks)
    for stage_no, chunk in chunks:
        try:
            raw = await call_openai_json(
                cfg=cfg,
                system_prompt=_build_stage_system_prompt(style_mode, stage_no),
                user_prompt=_build_stage_user_prompt(
                    request,
                    chunk,
                    retrieved_contexts,
                    stage_no,
                    stage_count,
                ),
            )
            stage_summaries.append(_normalize_stage_eval(raw, chunk, stage_no))
        except Exception:
            fallback_count += 1
            stage_summaries.append(_build_stage_summary_fallback(chunk, stage_no))

    return stage_summaries, fallback_count


async def _build_aggregate_summary_with_openai(
    *,
    cfg: OpenAiConfigProtocol,
    request: "JudgeDispatchRequest",
    stage_summaries: list[dict[str, Any]],
    retrieved_contexts: list[RetrievedContext],
    style_mode: str,
) -> tuple[dict[str, Any], bool]:
    fallback = False
    try:
        raw = await call_openai_json(
            cfg=cfg,
            system_prompt=_build_aggregate_system_prompt(style_mode),
            user_prompt=_build_aggregate_user_prompt(request, stage_summaries, retrieved_contexts),
        )
    except Exception:
        raw = {}
        fallback = True
    return _normalize_aggregate_eval(raw, stage_summaries), fallback


async def _call_openai_final_pass(
    *,
    cfg: OpenAiConfigProtocol,
    request: "JudgeDispatchRequest",
    stage_summaries: list[dict[str, Any]],
    aggregate_summary: dict[str, Any],
    retrieved_contexts: list[RetrievedContext],
    style_mode: str,
    pass_no: int,
    ) -> dict[str, Any]:
    return await call_openai_json(
        cfg=cfg,
        system_prompt=_build_final_system_prompt(style_mode, pass_no),
        user_prompt=_build_final_user_prompt(
            request,
            stage_summaries,
            aggregate_summary,
            retrieved_contexts,
        ),
    )


async def _build_final_eval_with_openai(
    *,
    cfg: OpenAiConfigProtocol,
    request: "JudgeDispatchRequest",
    stage_summaries: list[dict[str, Any]],
    aggregate_summary: dict[str, Any],
    retrieved_contexts: list[RetrievedContext],
    style_mode: str,
    pass_no: int,
) -> tuple[dict[str, Any], bool]:
    try:
        raw = await _call_openai_final_pass(
            cfg=cfg,
            request=request,
            stage_summaries=stage_summaries,
            aggregate_summary=aggregate_summary,
            retrieved_contexts=retrieved_contexts,
            style_mode=style_mode,
            pass_no=pass_no,
        )
        return _normalize_eval(raw), False
    except Exception:
        return _normalize_eval({}), True


async def run_openai_judge_pipeline(
    *,
    cfg: OpenAiConfigProtocol,
    request: "JudgeDispatchRequest",
    style_mode: str,
    retrieved_contexts: list[RetrievedContext],
    max_stage_agent_chunks: int,
) -> OpenAiJudgePipelineResult:
    messages = [
        DebateMessage(
            message_id=msg.message_id,
            user_id=msg.user_id,
            side=msg.side,
            content=msg.content,
        )
        for msg in request.messages
    ]

    stage_summaries, stage_fallback_count = await _build_stage_summaries_with_openai(
        cfg=cfg,
        request=request,
        messages=messages,
        retrieved_contexts=retrieved_contexts,
        style_mode=style_mode,
        max_stage_agent_chunks=max_stage_agent_chunks,
    )
    aggregate_summary, aggregate_fallback = await _build_aggregate_summary_with_openai(
        cfg=cfg,
        request=request,
        stage_summaries=stage_summaries,
        retrieved_contexts=retrieved_contexts,
        style_mode=style_mode,
    )

    first, first_fallback = await _build_final_eval_with_openai(
        cfg=cfg,
        request=request,
        stage_summaries=stage_summaries,
        aggregate_summary=aggregate_summary,
        retrieved_contexts=retrieved_contexts,
        style_mode=style_mode,
        pass_no=1,
    )
    second, second_fallback = await _build_final_eval_with_openai(
        cfg=cfg,
        request=request,
        stage_summaries=stage_summaries,
        aggregate_summary=aggregate_summary,
        retrieved_contexts=retrieved_contexts,
        style_mode=style_mode,
        pass_no=2,
    )

    merged = _merge_two_pass(first, second)

    display_fallback = False
    try:
        display_raw = await call_openai_json(
            cfg=cfg,
            system_prompt=_build_display_system_prompt(style_mode),
            user_prompt=_build_display_user_prompt(merged, aggregate_summary),
        )
    except Exception:
        display_raw = {}
        display_fallback = True
    display = _normalize_display_eval(display_raw, merged)

    return OpenAiJudgePipelineResult(
        stage_summaries=stage_summaries,
        stage_fallback_count=stage_fallback_count,
        aggregate_summary=aggregate_summary,
        aggregate_fallback=aggregate_fallback,
        final_fallback_count=(1 if first_fallback else 0) + (1 if second_fallback else 0),
        merged=merged,
        display=display,
        display_fallback=display_fallback,
    )
