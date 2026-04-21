from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable


async def build_panel_runtime_profiles_payload(
    *,
    list_judge_case_fairness: Callable[..., Awaitable[dict[str, Any]]],
    build_panel_runtime_profile_item: Callable[..., dict[str, Any]],
    build_panel_runtime_profile_sort_key: Callable[..., Any],
    build_panel_runtime_profile_aggregations: Callable[[list[dict[str, Any]]], dict[str, Any]],
    validate_panel_runtime_profile_contract: Callable[[dict[str, Any]], None],
    panel_judge_ids: tuple[str, ...] | list[str],
    x_ai_internal_key: str | None,
    status: str | None,
    dispatch_type: str | None,
    winner: str | None,
    policy_version: str | None,
    has_open_review: bool | None,
    gate_conclusion: str | None,
    challenge_state: str | None,
    review_required: bool | None,
    panel_high_disagreement: bool | None,
    normalized_judge_id: str | None,
    normalized_profile_source: str | None,
    normalized_profile_id: str | None,
    normalized_model_strategy: str | None,
    normalized_strategy_slot: str | None,
    normalized_domain_slot: str | None,
    normalized_sort_by: str,
    normalized_sort_order: str,
    normalized_status: str | None,
    normalized_dispatch_type: str | None,
    normalized_winner: str | None,
    normalized_policy_version: str | None,
    normalized_gate_conclusion: str | None,
    normalized_challenge_state: str | None,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    fairness_case_items: list[dict[str, Any]] = []
    fairness_offset = 0
    while True:
        fairness_page = await list_judge_case_fairness(
            x_ai_internal_key=x_ai_internal_key,
            status=status,
            dispatch_type=dispatch_type,
            winner=winner,
            policy_version=policy_version,
            has_drift_breach=None,
            has_threshold_breach=None,
            has_shadow_breach=None,
            has_open_review=has_open_review,
            gate_conclusion=gate_conclusion,
            challenge_state=challenge_state,
            sort_by="updated_at",
            sort_order="desc",
            review_required=review_required,
            panel_high_disagreement=panel_high_disagreement,
            offset=fairness_offset,
            limit=200,
        )
        page_items = (
            fairness_page.get("items")
            if isinstance(fairness_page.get("items"), list)
            else []
        )
        if not page_items:
            break
        fairness_case_items.extend(page_items)
        if len(page_items) < 200:
            break
        fairness_offset += 200

    items: list[dict[str, Any]] = []
    for case_item in fairness_case_items:
        panel = (
            case_item.get("panelDisagreement")
            if isinstance(case_item.get("panelDisagreement"), dict)
            else {}
        )
        runtime_profiles = (
            panel.get("runtimeProfiles")
            if isinstance(panel.get("runtimeProfiles"), dict)
            else {}
        )
        for judge in panel_judge_ids:
            runtime_profile = (
                runtime_profiles.get(judge)
                if isinstance(runtime_profiles.get(judge), dict)
                else {}
            )
            item = build_panel_runtime_profile_item(
                case_item=case_item,
                judge_id=judge,
                runtime_profile=runtime_profile,
            )
            if normalized_judge_id is not None and item.get("judgeId") != normalized_judge_id:
                continue
            if (
                normalized_profile_source is not None
                and str(item.get("profileSource") or "").strip().lower()
                != normalized_profile_source
            ):
                continue
            if (
                normalized_profile_id is not None
                and str(item.get("profileId") or "").strip() != normalized_profile_id
            ):
                continue
            if (
                normalized_model_strategy is not None
                and str(item.get("modelStrategy") or "").strip() != normalized_model_strategy
            ):
                continue
            if (
                normalized_strategy_slot is not None
                and str(item.get("strategySlot") or "").strip() != normalized_strategy_slot
            ):
                continue
            if (
                normalized_domain_slot is not None
                and str(item.get("domainSlot") or "").strip() != normalized_domain_slot
            ):
                continue
            items.append(item)

    items.sort(
        key=lambda row: build_panel_runtime_profile_sort_key(
            item=row,
            sort_by=normalized_sort_by,
        ),
        reverse=(normalized_sort_order == "desc"),
    )
    total_count = len(items)
    aggregations = build_panel_runtime_profile_aggregations(items)
    page_items = items[offset : offset + limit]
    payload = {
        "count": total_count,
        "returned": len(page_items),
        "items": page_items,
        "aggregations": aggregations,
        "filters": {
            "status": normalized_status,
            "dispatchType": normalized_dispatch_type,
            "winner": normalized_winner,
            "policyVersion": normalized_policy_version,
            "hasOpenReview": has_open_review,
            "gateConclusion": normalized_gate_conclusion,
            "challengeState": normalized_challenge_state,
            "reviewRequired": review_required,
            "panelHighDisagreement": panel_high_disagreement,
            "judgeId": normalized_judge_id,
            "profileSource": normalized_profile_source,
            "profileId": normalized_profile_id,
            "modelStrategy": normalized_model_strategy,
            "strategySlot": normalized_strategy_slot,
            "domainSlot": normalized_domain_slot,
            "sortBy": normalized_sort_by,
            "sortOrder": normalized_sort_order,
            "offset": offset,
            "limit": limit,
        },
    }
    validate_panel_runtime_profile_contract(payload)
    return payload


async def build_panel_runtime_readiness_payload(
    *,
    list_panel_runtime_profiles: Callable[..., Awaitable[dict[str, Any]]],
    build_panel_runtime_readiness_summary: Callable[..., dict[str, Any]],
    x_ai_internal_key: str | None,
    status: str | None,
    dispatch_type: str | None,
    winner: str | None,
    policy_version: str | None,
    has_open_review: bool | None,
    gate_conclusion: str | None,
    challenge_state: str | None,
    review_required: bool | None,
    panel_high_disagreement: bool | None,
    judge_id: str | None,
    profile_source: str | None,
    profile_id: str | None,
    model_strategy: str | None,
    strategy_slot: str | None,
    domain_slot: str | None,
    normalized_status: str | None,
    normalized_dispatch_type: str | None,
    normalized_winner: str | None,
    normalized_policy_version: str | None,
    normalized_gate_conclusion: str | None,
    normalized_challenge_state: str | None,
    normalized_judge_id: str | None,
    normalized_profile_source: str | None,
    normalized_profile_id: str | None,
    normalized_model_strategy: str | None,
    normalized_strategy_slot: str | None,
    normalized_domain_slot: str | None,
    normalized_scan_limit: int,
    normalized_group_limit: int,
    normalized_attention_limit: int,
) -> dict[str, Any]:
    collected_items: list[dict[str, Any]] = []
    offset = 0
    total_count: int | None = None
    while len(collected_items) < normalized_scan_limit:
        batch_limit = min(200, normalized_scan_limit - len(collected_items))
        page = await list_panel_runtime_profiles(
            x_ai_internal_key=x_ai_internal_key,
            status=status,
            dispatch_type=dispatch_type,
            winner=winner,
            policy_version=policy_version,
            has_open_review=has_open_review,
            gate_conclusion=gate_conclusion,
            challenge_state=challenge_state,
            review_required=review_required,
            panel_high_disagreement=panel_high_disagreement,
            judge_id=judge_id,
            profile_source=profile_source,
            profile_id=profile_id,
            model_strategy=model_strategy,
            strategy_slot=strategy_slot,
            domain_slot=domain_slot,
            sort_by="updated_at",
            sort_order="desc",
            offset=offset,
            limit=batch_limit,
        )
        if total_count is None:
            total_count = int(page.get("count") or 0)
        page_items = page.get("items") if isinstance(page.get("items"), list) else []
        if not page_items:
            break
        collected_items.extend(page_items)
        if len(page_items) < batch_limit:
            break
        offset += batch_limit

    readiness = build_panel_runtime_readiness_summary(
        items=collected_items,
        group_limit=normalized_group_limit,
        attention_limit=normalized_attention_limit,
    )
    overview = readiness.get("overview") if isinstance(readiness.get("overview"), dict) else {}
    total_matched = int(total_count or 0)
    scanned_records = len(collected_items)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "overview": {
            "totalMatched": total_matched,
            "scannedRecords": scanned_records,
            "scanTruncated": scanned_records < total_matched,
            "totalGroups": int(overview.get("totalGroups") or 0),
            "attentionGroupCount": int(overview.get("attentionGroupCount") or 0),
            "readinessCounts": (
                overview.get("readinessCounts")
                if isinstance(overview.get("readinessCounts"), dict)
                else {"ready": 0, "watch": 0, "attention": 0}
            ),
        },
        "groups": (
            readiness.get("groups")
            if isinstance(readiness.get("groups"), list)
            else []
        ),
        "attentionGroups": (
            readiness.get("attentionGroups")
            if isinstance(readiness.get("attentionGroups"), list)
            else []
        ),
        "notes": [
            (
                "simulations are advisory-only readiness suggestions and never "
                "change official winner semantics or auto-switch active policy."
            ),
        ],
        "filters": {
            "status": normalized_status,
            "dispatchType": normalized_dispatch_type,
            "winner": normalized_winner,
            "policyVersion": normalized_policy_version,
            "hasOpenReview": has_open_review,
            "gateConclusion": normalized_gate_conclusion,
            "challengeState": normalized_challenge_state,
            "reviewRequired": review_required,
            "panelHighDisagreement": panel_high_disagreement,
            "judgeId": normalized_judge_id,
            "profileSource": normalized_profile_source,
            "profileId": normalized_profile_id,
            "modelStrategy": normalized_model_strategy,
            "strategySlot": normalized_strategy_slot,
            "domainSlot": normalized_domain_slot,
            "profileScanLimit": normalized_scan_limit,
            "groupLimit": normalized_group_limit,
            "attentionLimit": normalized_attention_limit,
        },
    }
