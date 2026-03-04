from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
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
class GraphNodeTrace:
    node: str
    status: str
    duration_ms: float
    fallback: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReflectionResult:
    enabled: bool
    policy: str
    winner_first: str
    winner_second: str
    winner_mismatch: bool
    action: str
    reason: str | None = None


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
    graph_nodes: list[GraphNodeTrace]
    reflection: ReflectionResult
    compliance: dict[str, Any]


def _build_node_trace(
    *,
    node: str,
    start_at: float,
    status: str,
    fallback: bool = False,
    meta: dict[str, Any] | None = None,
) -> GraphNodeTrace:
    return GraphNodeTrace(
        node=node,
        status=status,
        duration_ms=round((perf_counter() - start_at) * 1000.0, 2),
        fallback=fallback,
        meta=meta or {},
    )


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


def _run_reflection_controller(
    *,
    first: dict[str, Any],
    second: dict[str, Any],
    enabled: bool,
    policy: str,
) -> tuple[dict[str, Any], ReflectionResult]:
    merged = _merge_two_pass(first, second)
    winner_mismatch = first["winner"] != second["winner"]

    if not enabled:
        return (
            merged,
            ReflectionResult(
                enabled=False,
                policy=policy,
                winner_first=first["winner"],
                winner_second=second["winner"],
                winner_mismatch=winner_mismatch,
                action="merge_only",
                reason="reflection_disabled",
            ),
        )

    if winner_mismatch:
        return (
            merged,
            ReflectionResult(
                enabled=True,
                policy=policy,
                winner_first=first["winner"],
                winner_second=second["winner"],
                winner_mismatch=True,
                action="draw_protection",
                reason="winner_mismatch",
            ),
        )

    return (
        merged,
        ReflectionResult(
            enabled=True,
            policy=policy,
            winner_first=first["winner"],
            winner_second=second["winner"],
            winner_mismatch=False,
            action="consistency_confirmed",
            reason=None,
        ),
    )


def _apply_compliance_guard(
    *,
    merged: dict[str, Any],
    display: dict[str, str],
) -> dict[str, Any]:
    violations: list[str] = []

    for key in ("pro_summary", "con_summary", "rationale"):
        if not str(display.get(key, "")).strip():
            violations.append(f"display_missing_{key}")
            display[key] = str(merged.get(key, "信息不足。"))

    winner = str(merged.get("winner", "")).strip().lower()
    if winner not in {"pro", "con", "draw"}:
        violations.append("invalid_winner")
        merged["winner"] = "draw"
        merged["needs_draw_vote"] = True

    return {
        "status": "warn" if violations else "ok",
        "violations": violations,
    }


async def run_openai_judge_pipeline(
    *,
    cfg: OpenAiConfigProtocol,
    request: "JudgeDispatchRequest",
    style_mode: str,
    retrieved_contexts: list[RetrievedContext],
    max_stage_agent_chunks: int,
    reflection_enabled: bool = True,
) -> OpenAiJudgePipelineResult:
    messages = [
        DebateMessage(
            message_id=msg.message_id,
            user_id=msg.user_id or 0,
            side=msg.side,
            content=msg.content,
        )
        for msg in request.messages
    ]

    graph_nodes: list[GraphNodeTrace] = []

    stage_start = perf_counter()
    stage_summaries, stage_fallback_count = await _build_stage_summaries_with_openai(
        cfg=cfg,
        request=request,
        messages=messages,
        retrieved_contexts=retrieved_contexts,
        style_mode=style_mode,
        max_stage_agent_chunks=max_stage_agent_chunks,
    )
    graph_nodes.append(
        _build_node_trace(
            node="stage_judge",
            start_at=stage_start,
            status="ok",
            fallback=stage_fallback_count > 0,
            meta={
                "stageCount": len(stage_summaries),
                "fallbackCount": stage_fallback_count,
            },
        )
    )

    aggregate_start = perf_counter()
    aggregate_summary, aggregate_fallback = await _build_aggregate_summary_with_openai(
        cfg=cfg,
        request=request,
        stage_summaries=stage_summaries,
        retrieved_contexts=retrieved_contexts,
        style_mode=style_mode,
    )
    graph_nodes.append(
        _build_node_trace(
            node="aggregate",
            start_at=aggregate_start,
            status="ok",
            fallback=aggregate_fallback,
        )
    )

    first_start = perf_counter()
    first, first_fallback = await _build_final_eval_with_openai(
        cfg=cfg,
        request=request,
        stage_summaries=stage_summaries,
        aggregate_summary=aggregate_summary,
        retrieved_contexts=retrieved_contexts,
        style_mode=style_mode,
        pass_no=1,
    )
    graph_nodes.append(
        _build_node_trace(
            node="final_pass_1",
            start_at=first_start,
            status="ok",
            fallback=first_fallback,
            meta={"winner": first.get("winner")},
        )
    )

    second_start = perf_counter()
    second, second_fallback = await _build_final_eval_with_openai(
        cfg=cfg,
        request=request,
        stage_summaries=stage_summaries,
        aggregate_summary=aggregate_summary,
        retrieved_contexts=retrieved_contexts,
        style_mode=style_mode,
        pass_no=2,
    )
    graph_nodes.append(
        _build_node_trace(
            node="final_pass_2",
            start_at=second_start,
            status="ok",
            fallback=second_fallback,
            meta={"winner": second.get("winner")},
        )
    )

    reflection_start = perf_counter()
    merged, reflection = _run_reflection_controller(
        first=first,
        second=second,
        enabled=reflection_enabled,
        policy=str(getattr(request, "judge_policy_version", "v2-default")),
    )
    graph_nodes.append(
        _build_node_trace(
            node="reflection_controller",
            start_at=reflection_start,
            status="ok",
            fallback=False,
            meta={
                "enabled": reflection.enabled,
                "action": reflection.action,
                "winnerMismatch": reflection.winner_mismatch,
            },
        )
    )

    display_fallback = False
    display_start = perf_counter()
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
    graph_nodes.append(
        _build_node_trace(
            node="display",
            start_at=display_start,
            status="ok",
            fallback=display_fallback,
        )
    )

    compliance_start = perf_counter()
    compliance = _apply_compliance_guard(merged=merged, display=display)
    graph_nodes.append(
        _build_node_trace(
            node="compliance_guard",
            start_at=compliance_start,
            status=compliance["status"],
            fallback=False,
            meta={"violations": len(compliance["violations"])},
        )
    )

    return OpenAiJudgePipelineResult(
        stage_summaries=stage_summaries,
        stage_fallback_count=stage_fallback_count,
        aggregate_summary=aggregate_summary,
        aggregate_fallback=aggregate_fallback,
        final_fallback_count=(1 if first_fallback else 0) + (1 if second_fallback else 0),
        merged=merged,
        display=display,
        display_fallback=display_fallback,
        graph_nodes=graph_nodes,
        reflection=reflection,
        compliance=compliance,
    )
