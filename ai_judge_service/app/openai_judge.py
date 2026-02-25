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


@dataclass(frozen=True)
class OpenAiJudgeConfig:
    api_key: str
    model: str
    base_url: str
    timeout_secs: float
    temperature: float
    max_retries: int


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


def _build_stage_summaries(messages: list[DebateMessage], window_size: int) -> list[dict[str, Any]]:
    if not messages:
        return []
    out: list[dict[str, Any]] = []
    size = max(1, window_size)
    for idx in range(0, len(messages), size):
        chunk = messages[idx : idx + size]
        stage_no = idx // size + 1
        pro_count = sum(1 for m in chunk if m.side.lower().strip() == SIDE_PRO)
        con_count = sum(1 for m in chunk if m.side.lower().strip() == SIDE_CON)
        out.append(
            {
                "stage_no": stage_no,
                "from_message_id": chunk[0].message_id,
                "to_message_id": chunk[-1].message_id,
                "pro_score": 50 + min(25, pro_count),
                "con_score": 50 + min(25, con_count),
                "summary": {
                    "messageCount": len(chunk),
                    "proMessageCount": pro_count,
                    "conMessageCount": con_count,
                },
            }
        )
    return out


def _messages_to_prompt_lines(messages: list[DebateMessage]) -> str:
    lines: list[str] = []
    for msg in messages[-400:]:
        side = msg.side.lower().strip()
        content = msg.content.strip().replace("\n", " ")
        lines.append(f"[{msg.message_id}][{side}] {content}")
    return "\n".join(lines)


def _build_system_prompt(style_mode: str, pass_no: int) -> str:
    return (
        "You are a strict and fair debate judge. "
        "You must score by rubric dimensions: logic, evidence, rebuttal, clarity. "
        "Output ONLY valid JSON object with keys: "
        "winner, logic_pro, logic_con, evidence_pro, evidence_con, rebuttal_pro, rebuttal_con, "
        "clarity_pro, clarity_con, pro_summary, con_summary, rationale. "
        "Winner must be one of pro|con|draw. "
        f"Style mode: {style_mode}. "
        f"Evaluation pass number: {pass_no}. "
        "Score range is 0..100."
    )


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


async def _call_openai_once(
    *,
    cfg: OpenAiJudgeConfig,
    request: "JudgeDispatchRequest",
    messages: list[DebateMessage],
    retrieved_contexts: list[RetrievedContext],
    style_mode: str,
    pass_no: int,
) -> dict[str, Any]:
    body = {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _build_system_prompt(style_mode, pass_no)},
            {
                "role": "user",
                "content": _build_user_prompt(request, messages, retrieved_contexts),
            },
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
    winner = winner_raw if winner_raw in {"pro", "con", "draw"} else _winner_from_scores(pro_score, con_score)
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
    first_raw = await _call_openai_once(
        cfg=cfg,
        request=request,
        messages=messages,
        retrieved_contexts=retrieved_contexts,
        style_mode=effective_style_mode,
        pass_no=1,
    )
    second_raw = await _call_openai_once(
        cfg=cfg,
        request=request,
        messages=messages,
        retrieved_contexts=retrieved_contexts,
        style_mode=effective_style_mode,
        pass_no=2,
    )

    first = _normalize_eval(first_raw)
    second = _normalize_eval(second_raw)
    merged = _merge_two_pass(first, second)
    stage_summaries = _build_stage_summaries(messages, request.message_window_size)

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
        pro_summary=merged["pro_summary"],
        con_summary=merged["con_summary"],
        rationale=merged["rationale"],
        style_mode=effective_style_mode,
        needs_draw_vote=merged["needs_draw_vote"],
        rejudge_triggered=request.job.rejudge_triggered or merged["rejudge_triggered"],
        payload=payload,
        winner_first=merged["winner_first"],
        winner_second=merged["winner_second"],
        stage_summaries=stage_summaries,
    )
