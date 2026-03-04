from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .openai_judge_helpers import (
    _build_user_prompt,
    _merge_two_pass,
    _normalize_aggregate_eval,
    _normalize_display_eval,
    _normalize_eval,
    _normalize_stage_eval,
    _split_message_chunks,
)
from .openai_judge_pipeline import (
    _build_stage_summaries_with_openai,
    run_openai_judge_pipeline,
)
from .rag_retriever import RetrievedContext, summarize_retrieved_contexts
from .scoring_core import DebateMessage, build_verdict_evidence_refs

if TYPE_CHECKING:
    from .models import JudgeDispatchRequest, SubmitJudgeReportInput


@dataclass(frozen=True)
class OpenAiJudgeConfig:
    api_key: str
    model: str
    base_url: str
    timeout_secs: float
    temperature: float
    max_retries: int
    max_stage_agent_chunks: int = 12
    reflection_enabled: bool = True
    graph_v2_enabled: bool = True
    reflection_policy: str = "winner_mismatch_only"
    reflection_low_margin_threshold: int = 3
    fault_injection_nodes: tuple[str, ...] = ()


async def build_report_with_openai(
    *,
    request: "JudgeDispatchRequest",
    effective_style_mode: str,
    style_mode_source: str,
    cfg: OpenAiJudgeConfig,
    retrieved_contexts: list[RetrievedContext] | None = None,
) -> "SubmitJudgeReportInput":
    from .models import SubmitJudgeReportInput

    retrieved_contexts = retrieved_contexts or []
    pipeline = await run_openai_judge_pipeline(
        cfg=cfg,
        request=request,
        style_mode=effective_style_mode,
        retrieved_contexts=retrieved_contexts,
        max_stage_agent_chunks=cfg.max_stage_agent_chunks,
        reflection_enabled=cfg.reflection_enabled,
        reflection_policy=cfg.reflection_policy,
        reflection_low_margin_threshold=cfg.reflection_low_margin_threshold,
        fault_injection_nodes=cfg.fault_injection_nodes,
    )
    reflection = getattr(pipeline, "reflection", None)
    graph_nodes = getattr(pipeline, "graph_nodes", [])
    compliance = getattr(pipeline, "compliance", {"status": "ok", "violations": []})
    merged = pipeline.merged
    aggregate_summary = pipeline.aggregate_summary
    display = pipeline.display
    debate_messages = [
        DebateMessage(
            message_id=msg.message_id,
            user_id=msg.user_id or 0,
            side=msg.side,
            content=msg.content,
        )
        for msg in request.messages
    ]

    payload = {
        "provider": "openai",
        "model": cfg.model,
        "winnerFirst": merged["winner_first"],
        "winnerSecond": merged["winner_second"],
        "rubricVersion": request.rubric_version,
        "requestedStyleMode": request.job.style_mode,
        "effectiveStyleMode": effective_style_mode,
        "styleModeSource": style_mode_source,
        "ragEnabled": True,
        "ragUsedByModel": bool(retrieved_contexts),
        "ragSnippetCount": len(retrieved_contexts),
        "ragSources": summarize_retrieved_contexts(retrieved_contexts),
        "agentPipelineVersion": "multi-agent-v2" if cfg.graph_v2_enabled else "multi-agent-v1",
        "judgePolicyVersion": getattr(request, "judge_policy_version", "v2-default"),
        "agentPipeline": {
            "stageAgent": "openai",
            "aggregateAgent": "openai" if not pipeline.aggregate_fallback else "fallback",
            "finalJudgeAgent": "openai",
            "displayAgent": "openai" if not pipeline.display_fallback else "fallback",
            "stageCount": len(pipeline.stage_summaries),
            "stageFallbackCount": pipeline.stage_fallback_count,
            "finalPassFallbackCount": pipeline.final_fallback_count,
            "maxStageAgentChunks": cfg.max_stage_agent_chunks,
            "executionMode": "dag",
            "reflectionEnabled": reflection.enabled if reflection is not None else cfg.reflection_enabled,
            "reflectionPolicy": cfg.reflection_policy,
            "reflectionLowMarginThreshold": cfg.reflection_low_margin_threshold,
            "reflectionAction": reflection.action if reflection is not None else "unknown",
            "reflectionWinnerMismatch": (
                reflection.winner_mismatch if reflection is not None else False
            ),
            "reflectionAvgScoreMargin": (
                getattr(reflection, "avg_score_margin", None) if reflection is not None else None
            ),
            "faultInjectionNodes": list(cfg.fault_injection_nodes),
            "graphNodes": [
                {
                    "node": node.node,
                    "status": node.status,
                    "durationMs": node.duration_ms,
                    "fallback": node.fallback,
                    "meta": node.meta,
                }
                for node in graph_nodes
            ],
            "compliance": compliance,
        },
        "aggregateSummary": {
            "winnerHint": aggregate_summary["winner_hint"],
            "proScoreHint": aggregate_summary["pro_score_hint"],
            "conScoreHint": aggregate_summary["con_score_hint"],
        },
        "verdictEvidenceRefs": build_verdict_evidence_refs(
            debate_messages,
            merged["winner"],
        ),
    }

    return SubmitJudgeReportInput(
        winner=merged["winner"],
        pro_score=merged["pro_score"],
        con_score=merged["con_score"],
        logic_pro=merged["logic_pro"],
        logic_con=merged["logic_con"],
        evidence_pro=merged["evidence_pro"],
        evidence_con=merged["evidence_con"],
        rebuttal_pro=merged["rebuttal_pro"],
        rebuttal_con=merged["rebuttal_con"],
        clarity_pro=merged["clarity_pro"],
        clarity_con=merged["clarity_con"],
        pro_summary=display["pro_summary"],
        con_summary=display["con_summary"],
        rationale=display["rationale"],
        style_mode=effective_style_mode,
        needs_draw_vote=merged["needs_draw_vote"],
        rejudge_triggered=request.job.rejudge_triggered or merged["rejudge_triggered"],
        payload=payload,
        winner_first=merged["winner_first"],
        winner_second=merged["winner_second"],
        stage_summaries=pipeline.stage_summaries,
    )
