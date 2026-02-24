from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

LOGIC_KEYWORDS = ("because", "therefore", "if ", "so ", "因此", "所以", "逻辑")
EVIDENCE_KEYWORDS = ("data", "patch", "version", "source", "stats", "证据", "数据", "来源")
REBUTTAL_KEYWORDS = ("but", "however", "counter", "instead", "反驳", "但是", "不过")

SIDE_PRO = "pro"
SIDE_CON = "con"


@dataclass(frozen=True)
class DebateMessage:
    message_id: int
    user_id: int
    side: str
    content: str


@dataclass
class _SideAggregate:
    count: int = 0
    logic: float = 0.0
    evidence: float = 0.0
    rebuttal: float = 0.0
    clarity: float = 0.0


def _clamp_score(score: float) -> int:
    return max(0, min(100, int(round(score))))


def _contains_keyword(content: str, keywords: Iterable[str]) -> bool:
    text = content.lower()
    return any(keyword in text for keyword in keywords)


def _message_component_weights(content: str) -> tuple[float, float, float, float]:
    length_factor = min(len(content.strip()) / 160.0, 1.0)
    logic = 0.6 + (0.4 if _contains_keyword(content, LOGIC_KEYWORDS) else 0.0)
    evidence = 0.55 + (0.45 if _contains_keyword(content, EVIDENCE_KEYWORDS) else 0.0)
    rebuttal = 0.5 + (0.5 if _contains_keyword(content, REBUTTAL_KEYWORDS) else 0.0)
    clarity = 0.5 + 0.5 * length_factor
    return logic, evidence, rebuttal, clarity


def _deterministic_jitter(job_id: int, side: str, pass_no: int) -> int:
    seed = (job_id * 131 + pass_no * 17 + (1 if side == SIDE_PRO else 2) * 19) % 5
    return int(seed) - 2


def _evaluate_components(
    messages: list[DebateMessage], job_id: int, pass_no: int
) -> dict[str, dict[str, int]]:
    stats: dict[str, _SideAggregate] = defaultdict(_SideAggregate)
    for msg in messages:
        side = msg.side.lower().strip()
        if side not in (SIDE_PRO, SIDE_CON):
            continue
        agg = stats[side]
        logic, evidence, rebuttal, clarity = _message_component_weights(msg.content)
        agg.count += 1
        agg.logic += logic
        agg.evidence += evidence
        agg.rebuttal += rebuttal
        agg.clarity += clarity

    out: dict[str, dict[str, int]] = {}
    for side in (SIDE_PRO, SIDE_CON):
        agg = stats[side]
        if agg.count == 0:
            base_logic = base_evidence = base_rebuttal = base_clarity = 40.0
        else:
            count_bonus = min(agg.count, 30) * 1.0
            base_logic = 45 + (agg.logic / agg.count) * 32 + count_bonus
            base_evidence = 45 + (agg.evidence / agg.count) * 32 + count_bonus
            base_rebuttal = 45 + (agg.rebuttal / agg.count) * 32 + count_bonus
            base_clarity = 45 + (agg.clarity / agg.count) * 30 + count_bonus
        jitter = _deterministic_jitter(job_id, side, pass_no)
        out[side] = {
            "logic": _clamp_score(base_logic + jitter),
            "evidence": _clamp_score(base_evidence + jitter),
            "rebuttal": _clamp_score(base_rebuttal + jitter),
            "clarity": _clamp_score(base_clarity + jitter),
        }
    return out


def _final_score(components: dict[str, int]) -> int:
    score = (
        components["logic"] * 0.30
        + components["evidence"] * 0.30
        + components["rebuttal"] * 0.25
        + components["clarity"] * 0.15
    )
    return _clamp_score(score)


def _winner_from_scores(pro_score: int, con_score: int) -> str:
    diff = pro_score - con_score
    if abs(diff) <= 2:
        return "draw"
    return SIDE_PRO if diff > 0 else SIDE_CON


def _build_side_summary(messages: list[DebateMessage], side: str) -> str:
    chunks = [m.content.strip().replace("\n", " ") for m in messages if m.side.lower().strip() == side]
    if not chunks:
        return "本方可用发言较少，样本不足。"
    head = "; ".join(chunks[:3])
    return head[:500]


def _build_rationale(winner: str, pro_score: int, con_score: int, winner_first: str, winner_second: str) -> str:
    if winner == "draw":
        return (
            f"两次评估结果为 {winner_first}/{winner_second}，存在胜方不一致或分差过小，"
            "触发平局保护策略并建议进入平局流程。"
        )
    return f"综合逻辑、证据、反驳、表达四维评分，最终判定 {winner} 方胜出（pro={pro_score}, con={con_score}）。"


def _build_stage_summaries(messages: list[DebateMessage], window_size: int, job_id: int) -> list[dict]:
    if not messages:
        return []
    chunks = [messages[i : i + window_size] for i in range(0, len(messages), window_size)]
    out: list[dict] = []
    for idx, chunk in enumerate(chunks, start=1):
        components = _evaluate_components(chunk, job_id, pass_no=0)
        pro_score = _final_score(components[SIDE_PRO])
        con_score = _final_score(components[SIDE_CON])
        out.append(
            {
                "stage_no": idx,
                "from_message_id": chunk[0].message_id,
                "to_message_id": chunk[-1].message_id,
                "pro_score": pro_score,
                "con_score": con_score,
                "summary": {
                    "messageCount": len(chunk),
                    "proHighlights": _build_side_summary(chunk, SIDE_PRO),
                    "conHighlights": _build_side_summary(chunk, SIDE_CON),
                },
            }
        )
    return out


def build_report_core(
    *,
    job_id: int,
    style_mode: str,
    rejudge_triggered: bool,
    messages: list[DebateMessage],
    message_window_size: int,
    rubric_version: str,
) -> dict:
    first = _evaluate_components(messages, job_id, pass_no=0)
    second = _evaluate_components(messages, job_id, pass_no=1)

    pro_score_first = _final_score(first[SIDE_PRO])
    con_score_first = _final_score(first[SIDE_CON])
    winner_first = _winner_from_scores(pro_score_first, con_score_first)

    pro_score_second = _final_score(second[SIDE_PRO])
    con_score_second = _final_score(second[SIDE_CON])
    winner_second = _winner_from_scores(pro_score_second, con_score_second)

    winner = winner_first
    needs_draw_vote = winner == "draw"
    final_rejudge_triggered = rejudge_triggered
    if winner_first != winner_second:
        winner = "draw"
        needs_draw_vote = True
        final_rejudge_triggered = True

    pro_score = int(round((pro_score_first + pro_score_second) / 2))
    con_score = int(round((con_score_first + con_score_second) / 2))

    stage_summaries = _build_stage_summaries(
        messages,
        max(1, message_window_size),
        job_id,
    )

    return {
        "winner": winner,
        "pro_score": pro_score,
        "con_score": con_score,
        "logic_pro": first[SIDE_PRO]["logic"],
        "logic_con": first[SIDE_CON]["logic"],
        "evidence_pro": first[SIDE_PRO]["evidence"],
        "evidence_con": first[SIDE_CON]["evidence"],
        "rebuttal_pro": first[SIDE_PRO]["rebuttal"],
        "rebuttal_con": first[SIDE_CON]["rebuttal"],
        "clarity_pro": first[SIDE_PRO]["clarity"],
        "clarity_con": first[SIDE_CON]["clarity"],
        "pro_summary": _build_side_summary(messages, SIDE_PRO),
        "con_summary": _build_side_summary(messages, SIDE_CON),
        "rationale": _build_rationale(winner, pro_score, con_score, winner_first, winner_second),
        "style_mode": style_mode,
        "needs_draw_vote": needs_draw_vote,
        "rejudge_triggered": final_rejudge_triggered,
        "payload": {
            "provider": "ai-judge-service-mock",
            "winnerFirst": winner_first,
            "winnerSecond": winner_second,
            "rubricVersion": rubric_version,
        },
        "winner_first": winner_first,
        "winner_second": winner_second,
        "stage_summaries": stage_summaries,
    }
