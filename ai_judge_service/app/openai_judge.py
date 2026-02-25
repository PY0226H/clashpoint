from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from .rag_retriever import RetrievedContext, summarize_retrieved_contexts
from .scoring_core import DebateMessage

if TYPE_CHECKING:
    from .models import JudgeDispatchRequest, SubmitJudgeReportInput

SIDE_PRO = "pro"
SIDE_CON = "con"
VALID_WINNERS = {SIDE_PRO, SIDE_CON, "draw"}


@dataclass(frozen=True)
class OpenAiJudgeConfig:
    api_key: str
    model: str
    base_url: str
    timeout_secs: float
    temperature: float
    max_retries: int
    max_stage_agent_chunks: int = 12


def _clamp_score(value: Any) -> int:
    try:
        score = int(round(float(value)))
    except Exception:
        score = 0
    return max(0, min(100, score))


def _winner_from_scores(pro_score: int, con_score: int) -> str:
    if abs(pro_score - con_score) <= 2:
        return "draw"
    return SIDE_PRO if pro_score > con_score else SIDE_CON


def _calc_final_score(logic: int, evidence: int, rebuttal: int, clarity: int) -> int:
    score = logic * 0.30 + evidence * 0.30 + rebuttal * 0.25 + clarity * 0.15
    return _clamp_score(score)


def _extract_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = [line for line in lines if not line.strip().startswith("```")]
        stripped = "\n".join(lines).strip()
    return json.loads(stripped)


def _safe_text(value: Any, max_len: int = 4000) -> str:
    text = str(value or "").strip()
    if not text:
        return "信息不足。"
    return text[:max_len]


def _normalize_winner_hint(value: Any, pro_score: int, con_score: int) -> str:
    raw = str(value or "").strip().lower()
    if raw in VALID_WINNERS:
        return raw
    return _winner_from_scores(pro_score, con_score)


def _messages_to_prompt_lines(messages: list[DebateMessage], max_messages: int = 400) -> str:
    lines: list[str] = []
    for msg in messages[-max_messages:]:
        side = msg.side.lower().strip()
        content = msg.content.strip().replace("\n", " ")
        lines.append(f"[{msg.message_id}][{side}] {content}")
    return "\n".join(lines)


def _build_retrieved_contexts_section(retrieved_contexts: list[RetrievedContext]) -> str:
    if not retrieved_contexts:
        return "Retrieved background knowledge:\n- (none)\n"

    blocks: list[str] = []
    for idx, snippet in enumerate(retrieved_contexts, start=1):
        source = snippet.source_url or "unknown_source"
        blocks.append(
            (
                f"[{idx}] title={snippet.title}; source={source}; score={snippet.score:.4f}\n"
                f"{snippet.content}"
            ).strip()
        )
    return "Retrieved background knowledge:\n" + "\n\n".join(blocks) + "\n"


def _build_user_prompt(
    request: JudgeDispatchRequest,
    messages: list[DebateMessage],
    retrieved_contexts: list[RetrievedContext],
) -> str:
    topic = request.topic
    session = request.session
    return (
        "Debate topic context:\n"
        f"- title: {topic.title}\n"
        f"- category: {topic.category}\n"
        f"- description: {topic.description}\n"
        f"- pro stance: {topic.stance_pro}\n"
        f"- con stance: {topic.stance_con}\n"
        f"- context seed: {topic.context_seed or ''}\n"
        f"- session status: {session.status}\n"
        f"{_build_retrieved_contexts_section(retrieved_contexts)}"
        "Messages:\n"
        f"{_messages_to_prompt_lines(messages)}\n"
    )


def _split_message_chunks(
    messages: list[DebateMessage],
    window_size: int,
    max_chunks: int,
) -> list[tuple[int, list[DebateMessage]]]:
    size = max(1, int(window_size or 1))
    chunks: list[tuple[int, list[DebateMessage]]] = []
    for idx in range(0, len(messages), size):
        stage_no = idx // size + 1
        chunks.append((stage_no, messages[idx : idx + size]))
    cap = max(0, int(max_chunks or 0))
    if cap > 0 and len(chunks) > cap:
        return chunks[-cap:]
    return chunks


def _build_chunk_side_summary(chunk: list[DebateMessage], side: str) -> str:
    snippets = [
        m.content.strip().replace("\n", " ")
        for m in chunk
        if m.side.lower().strip() == side
    ]
    if not snippets:
        return "本阶段本方有效论据较少。"
    return _safe_text("; ".join(snippets[:3]), max_len=600)


def _build_stage_summary_fallback(
    chunk: list[DebateMessage],
    stage_no: int,
) -> dict[str, Any]:
    pro_count = sum(1 for m in chunk if m.side.lower().strip() == SIDE_PRO)
    con_count = sum(1 for m in chunk if m.side.lower().strip() == SIDE_CON)
    pro_score = 50 + min(25, pro_count)
    con_score = 50 + min(25, con_count)
    return {
        "stage_no": stage_no,
        "from_message_id": chunk[0].message_id,
        "to_message_id": chunk[-1].message_id,
        "pro_score": pro_score,
        "con_score": con_score,
        "summary": {
            "messageCount": len(chunk),
            "proMessageCount": pro_count,
            "conMessageCount": con_count,
            "proSummary": _build_chunk_side_summary(chunk, SIDE_PRO),
            "conSummary": _build_chunk_side_summary(chunk, SIDE_CON),
            "rationale": "stage agent fallback: 使用规则摘要生成阶段结果。",
            "winnerHint": _winner_from_scores(pro_score, con_score),
        },
    }


def _normalize_stage_eval(
    eval_payload: dict[str, Any],
    chunk: list[DebateMessage],
    stage_no: int,
) -> dict[str, Any]:
    pro_score = _clamp_score(eval_payload.get("pro_score"))
    con_score = _clamp_score(eval_payload.get("con_score"))
    winner_hint = _normalize_winner_hint(
        eval_payload.get("winner_hint"),
        pro_score,
        con_score,
    )
    pro_count = sum(1 for m in chunk if m.side.lower().strip() == SIDE_PRO)
    con_count = sum(1 for m in chunk if m.side.lower().strip() == SIDE_CON)
    return {
        "stage_no": stage_no,
        "from_message_id": chunk[0].message_id,
        "to_message_id": chunk[-1].message_id,
        "pro_score": pro_score,
        "con_score": con_score,
        "summary": {
            "messageCount": len(chunk),
            "proMessageCount": pro_count,
            "conMessageCount": con_count,
            "proSummary": _safe_text(eval_payload.get("pro_summary"), max_len=800),
            "conSummary": _safe_text(eval_payload.get("con_summary"), max_len=800),
            "rationale": _safe_text(eval_payload.get("rationale"), max_len=1000),
            "winnerHint": winner_hint,
        },
    }


def _build_stage_system_prompt(style_mode: str, stage_no: int) -> str:
    return (
        "You are Stage Agent in a multi-agent debate judging system. "
        "Analyze only the provided message chunk and output ONLY JSON object with keys: "
        "pro_score, con_score, winner_hint, pro_summary, con_summary, rationale. "
        "winner_hint must be one of pro|con|draw, score range 0..100. "
        f"Style mode: {style_mode}. Stage number: {stage_no}."
    )


def _build_stage_user_prompt(
    request: JudgeDispatchRequest,
    chunk: list[DebateMessage],
    retrieved_contexts: list[RetrievedContext],
    stage_no: int,
    stage_count: int,
) -> str:
    return (
        f"Stage window: {stage_no}/{stage_count}.\n"
        f"Rubric version: {request.rubric_version}.\n"
        f"{_build_user_prompt(request, chunk, retrieved_contexts)}"
    )


def _build_aggregate_system_prompt(style_mode: str) -> str:
    return (
        "You are Aggregate Agent in a multi-agent debate judging system. "
        "You receive stage summaries and must output ONLY JSON object with keys: "
        "pro_summary, con_summary, rationale, winner_hint. "
        "winner_hint must be one of pro|con|draw. "
        f"Style mode: {style_mode}."
    )


def _build_aggregate_user_prompt(
    request: JudgeDispatchRequest,
    stage_summaries: list[dict[str, Any]],
    retrieved_contexts: list[RetrievedContext],
) -> str:
    lines: list[str] = []
    for stage in stage_summaries:
        summary = stage.get("summary") or {}
        lines.append(
            " | ".join(
                [
                    f"stage={stage.get('stage_no')}",
                    f"range={stage.get('from_message_id')}..{stage.get('to_message_id')}",
                    f"proScore={stage.get('pro_score')}",
                    f"conScore={stage.get('con_score')}",
                    f"winnerHint={summary.get('winnerHint')}",
                    f"proSummary={_safe_text(summary.get('proSummary'), max_len=240)}",
                    f"conSummary={_safe_text(summary.get('conSummary'), max_len=240)}",
                ]
            )
        )
    stage_text = "\n".join(lines)
    return (
        "Debate aggregate input:\n"
        f"- title: {request.topic.title}\n"
        f"- category: {request.topic.category}\n"
        f"- context seed: {request.topic.context_seed or ''}\n"
        f"{_build_retrieved_contexts_section(retrieved_contexts)}"
        "Stage summaries:\n"
        f"{stage_text}\n"
    )


def _normalize_aggregate_eval(
    eval_payload: dict[str, Any],
    stage_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    if not stage_summaries:
        return {
            "pro_summary": "信息不足。",
            "con_summary": "信息不足。",
            "rationale": "阶段摘要为空，无法形成有效汇总。",
            "winner_hint": "draw",
            "pro_score_hint": 50,
            "con_score_hint": 50,
        }

    pro_score_hint = int(round(sum(v["pro_score"] for v in stage_summaries) / len(stage_summaries)))
    con_score_hint = int(round(sum(v["con_score"] for v in stage_summaries) / len(stage_summaries)))
    winner_hint = _normalize_winner_hint(
        eval_payload.get("winner_hint"),
        pro_score_hint,
        con_score_hint,
    )
    return {
        "pro_summary": _safe_text(eval_payload.get("pro_summary"), max_len=1200),
        "con_summary": _safe_text(eval_payload.get("con_summary"), max_len=1200),
        "rationale": _safe_text(eval_payload.get("rationale"), max_len=1600),
        "winner_hint": winner_hint,
        "pro_score_hint": pro_score_hint,
        "con_score_hint": con_score_hint,
    }


def _build_final_system_prompt(style_mode: str, pass_no: int) -> str:
    return (
        "You are Final Judge Agent in a multi-agent debate judging system. "
        "You must score by rubric dimensions: logic, evidence, rebuttal, clarity. "
        "Output ONLY JSON object with keys: "
        "winner, logic_pro, logic_con, evidence_pro, evidence_con, rebuttal_pro, rebuttal_con, "
        "clarity_pro, clarity_con, pro_summary, con_summary, rationale. "
        "Winner must be one of pro|con|draw. "
        f"Style mode: {style_mode}. Evaluation pass number: {pass_no}."
    )


def _build_final_user_prompt(
    request: JudgeDispatchRequest,
    stage_summaries: list[dict[str, Any]],
    aggregate_summary: dict[str, Any],
    retrieved_contexts: list[RetrievedContext],
) -> str:
    stage_lines: list[str] = []
    for stage in stage_summaries:
        summary = stage.get("summary") or {}
        stage_lines.append(
            " | ".join(
                [
                    f"stage={stage.get('stage_no')}",
                    f"range={stage.get('from_message_id')}..{stage.get('to_message_id')}",
                    f"proScore={stage.get('pro_score')}",
                    f"conScore={stage.get('con_score')}",
                    f"winnerHint={summary.get('winnerHint')}",
                ]
            )
        )
    return (
        "Final verdict input:\n"
        f"- title: {request.topic.title}\n"
        f"- category: {request.topic.category}\n"
        f"- description: {request.topic.description}\n"
        f"- pro stance: {request.topic.stance_pro}\n"
        f"- con stance: {request.topic.stance_con}\n"
        f"- context seed: {request.topic.context_seed or ''}\n"
        f"- rubricVersion: {request.rubric_version}\n"
        f"{_build_retrieved_contexts_section(retrieved_contexts)}"
        "Aggregate summary:\n"
        f"- proSummary: {aggregate_summary['pro_summary']}\n"
        f"- conSummary: {aggregate_summary['con_summary']}\n"
        f"- rationale: {aggregate_summary['rationale']}\n"
        f"- winnerHint: {aggregate_summary['winner_hint']}\n"
        "Stage score snapshots:\n"
        f"{'\n'.join(stage_lines)}\n"
    )


def _build_display_system_prompt(style_mode: str) -> str:
    return (
        "You are Display Agent in a multi-agent debate judging system. "
        "Rewrite final judgment into user-facing concise Chinese explanation. "
        "Output ONLY JSON object with keys: pro_summary_display, con_summary_display, rationale_display. "
        f"Style mode: {style_mode}."
    )


def _build_display_user_prompt(
    merged: dict[str, Any],
    aggregate_summary: dict[str, Any],
) -> str:
    return (
        "Final judge raw output:\n"
        f"- winner: {merged['winner']}\n"
        f"- proScore: {merged['pro_score']}\n"
        f"- conScore: {merged['con_score']}\n"
        f"- proSummaryRaw: {merged['pro_summary']}\n"
        f"- conSummaryRaw: {merged['con_summary']}\n"
        f"- rationaleRaw: {merged['rationale']}\n"
        "Aggregate hints:\n"
        f"- proSummary: {aggregate_summary['pro_summary']}\n"
        f"- conSummary: {aggregate_summary['con_summary']}\n"
        f"- rationale: {aggregate_summary['rationale']}\n"
    )


def _normalize_display_eval(eval_payload: dict[str, Any], merged: dict[str, Any]) -> dict[str, str]:
    return {
        "pro_summary": _safe_text(eval_payload.get("pro_summary_display") or merged["pro_summary"], max_len=1200),
        "con_summary": _safe_text(eval_payload.get("con_summary_display") or merged["con_summary"], max_len=1200),
        "rationale": _safe_text(eval_payload.get("rationale_display") or merged["rationale"], max_len=2000),
    }


async def _call_openai_json(
    *,
    cfg: OpenAiJudgeConfig,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    body = {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    last_err: Exception | None = None
    for _ in range(max(1, cfg.max_retries)):
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_secs) as client:
                resp = await client.post(f"{cfg.base_url}/chat/completions", headers=headers, json=body)
            if resp.status_code // 100 != 2:
                raise RuntimeError(f"openai status={resp.status_code}, body={resp.text[:500]}")
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return _extract_json_object(content)
        except Exception as err:  # pragma: no cover
            last_err = err
    raise RuntimeError(f"openai call failed after retries: {last_err}")


async def _build_stage_summaries_with_openai(
    *,
    cfg: OpenAiJudgeConfig,
    request: "JudgeDispatchRequest",
    messages: list[DebateMessage],
    retrieved_contexts: list[RetrievedContext],
    style_mode: str,
) -> tuple[list[dict[str, Any]], int]:
    chunks = _split_message_chunks(
        messages,
        request.message_window_size,
        cfg.max_stage_agent_chunks,
    )
    if not chunks:
        return [], 0

    stage_summaries: list[dict[str, Any]] = []
    fallback_count = 0
    stage_count = len(chunks)
    for stage_no, chunk in chunks:
        try:
            raw = await _call_openai_json(
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
    cfg: OpenAiJudgeConfig,
    request: "JudgeDispatchRequest",
    stage_summaries: list[dict[str, Any]],
    retrieved_contexts: list[RetrievedContext],
    style_mode: str,
) -> tuple[dict[str, Any], bool]:
    fallback = False
    try:
        raw = await _call_openai_json(
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
    cfg: OpenAiJudgeConfig,
    request: "JudgeDispatchRequest",
    stage_summaries: list[dict[str, Any]],
    aggregate_summary: dict[str, Any],
    retrieved_contexts: list[RetrievedContext],
    style_mode: str,
    pass_no: int,
) -> dict[str, Any]:
    return await _call_openai_json(
        cfg=cfg,
        system_prompt=_build_final_system_prompt(style_mode, pass_no),
        user_prompt=_build_final_user_prompt(
            request,
            stage_summaries,
            aggregate_summary,
            retrieved_contexts,
        ),
    )


def _normalize_eval(eval_payload: dict[str, Any]) -> dict[str, Any]:
    logic_pro = _clamp_score(eval_payload.get("logic_pro"))
    logic_con = _clamp_score(eval_payload.get("logic_con"))
    evidence_pro = _clamp_score(eval_payload.get("evidence_pro"))
    evidence_con = _clamp_score(eval_payload.get("evidence_con"))
    rebuttal_pro = _clamp_score(eval_payload.get("rebuttal_pro"))
    rebuttal_con = _clamp_score(eval_payload.get("rebuttal_con"))
    clarity_pro = _clamp_score(eval_payload.get("clarity_pro"))
    clarity_con = _clamp_score(eval_payload.get("clarity_con"))

    pro_score = _calc_final_score(logic_pro, evidence_pro, rebuttal_pro, clarity_pro)
    con_score = _calc_final_score(logic_con, evidence_con, rebuttal_con, clarity_con)
    winner_raw = str(eval_payload.get("winner", "")).strip().lower()
    winner = winner_raw if winner_raw in VALID_WINNERS else _winner_from_scores(pro_score, con_score)
    return {
        "winner": winner,
        "logic_pro": logic_pro,
        "logic_con": logic_con,
        "evidence_pro": evidence_pro,
        "evidence_con": evidence_con,
        "rebuttal_pro": rebuttal_pro,
        "rebuttal_con": rebuttal_con,
        "clarity_pro": clarity_pro,
        "clarity_con": clarity_con,
        "pro_score": pro_score,
        "con_score": con_score,
        "pro_summary": _safe_text(eval_payload.get("pro_summary")),
        "con_summary": _safe_text(eval_payload.get("con_summary")),
        "rationale": _safe_text(eval_payload.get("rationale")),
    }


def _merge_two_pass(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in [
        "logic_pro",
        "logic_con",
        "evidence_pro",
        "evidence_con",
        "rebuttal_pro",
        "rebuttal_con",
        "clarity_pro",
        "clarity_con",
    ]:
        merged[key] = _clamp_score((first[key] + second[key]) / 2)
    merged["pro_score"] = _calc_final_score(
        merged["logic_pro"],
        merged["evidence_pro"],
        merged["rebuttal_pro"],
        merged["clarity_pro"],
    )
    merged["con_score"] = _calc_final_score(
        merged["logic_con"],
        merged["evidence_con"],
        merged["rebuttal_con"],
        merged["clarity_con"],
    )
    merged["winner_first"] = first["winner"]
    merged["winner_second"] = second["winner"]
    merged["winner"] = first["winner"] if first["winner"] == second["winner"] else "draw"
    merged["needs_draw_vote"] = merged["winner"] == "draw"
    merged["rejudge_triggered"] = merged["winner_first"] != merged["winner_second"]
    merged["pro_summary"] = _safe_text(first["pro_summary"])
    merged["con_summary"] = _safe_text(first["con_summary"])
    merged["rationale"] = _safe_text(
        first["rationale"]
        if not merged["rejudge_triggered"]
        else (
            f"双次评估胜方不一致({merged['winner_first']}/{merged['winner_second']}), "
            "触发重判保护并输出平局建议。"
        )
    )
    return merged


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
        style_mode=effective_style_mode,
    )
    aggregate_summary, aggregate_fallback = await _build_aggregate_summary_with_openai(
        cfg=cfg,
        request=request,
        stage_summaries=stage_summaries,
        retrieved_contexts=retrieved_contexts,
        style_mode=effective_style_mode,
    )

    first_raw = await _call_openai_final_pass(
        cfg=cfg,
        request=request,
        stage_summaries=stage_summaries,
        aggregate_summary=aggregate_summary,
        retrieved_contexts=retrieved_contexts,
        style_mode=effective_style_mode,
        pass_no=1,
    )
    second_raw = await _call_openai_final_pass(
        cfg=cfg,
        request=request,
        stage_summaries=stage_summaries,
        aggregate_summary=aggregate_summary,
        retrieved_contexts=retrieved_contexts,
        style_mode=effective_style_mode,
        pass_no=2,
    )

    first = _normalize_eval(first_raw)
    second = _normalize_eval(second_raw)
    merged = _merge_two_pass(first, second)

    display_fallback = False
    try:
        display_raw = await _call_openai_json(
            cfg=cfg,
            system_prompt=_build_display_system_prompt(effective_style_mode),
            user_prompt=_build_display_user_prompt(merged, aggregate_summary),
        )
    except Exception:
        display_raw = {}
        display_fallback = True
    display = _normalize_display_eval(display_raw, merged)

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
        "agentPipelineVersion": "multi-agent-v1",
        "agentPipeline": {
            "stageAgent": "openai",
            "aggregateAgent": "openai" if not aggregate_fallback else "fallback",
            "finalJudgeAgent": "openai",
            "displayAgent": "openai" if not display_fallback else "fallback",
            "stageCount": len(stage_summaries),
            "stageFallbackCount": stage_fallback_count,
            "maxStageAgentChunks": cfg.max_stage_agent_chunks,
        },
        "aggregateSummary": {
            "winnerHint": aggregate_summary["winner_hint"],
            "proScoreHint": aggregate_summary["pro_score_hint"],
            "conScoreHint": aggregate_summary["con_score_hint"],
        },
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
        stage_summaries=stage_summaries,
    )
