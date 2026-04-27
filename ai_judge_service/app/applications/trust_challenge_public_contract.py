from __future__ import annotations

from typing import Any

TRUST_CHALLENGE_PUBLIC_STATUS_VERSION = "trust-challenge-public-status-v1"
TRUST_CHALLENGE_PUBLIC_VISIBILITY_VERSION = "trust-challenge-public-visibility-v1"

TRUST_CHALLENGE_PUBLIC_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "version",
    "caseId",
    "dispatchType",
    "traceId",
    "eligibility",
    "challengeState",
    "reviewState",
    "allowedActions",
    "blockers",
    "policy",
    "challenge",
    "review",
    "visibilityContract",
    "cacheProfile",
)

TRUST_CHALLENGE_PUBLIC_ELIGIBILITY_KEYS: tuple[str, ...] = (
    "status",
    "eligible",
    "requestable",
    "reasonCode",
    "blockers",
)

TRUST_CHALLENGE_PUBLIC_CHALLENGE_KEYS: tuple[str, ...] = (
    "state",
    "activeChallengeId",
    "latestChallengeId",
    "latestDecision",
    "latestReasonCode",
    "totalChallenges",
)

TRUST_CHALLENGE_PUBLIC_REVIEW_KEYS: tuple[str, ...] = (
    "state",
    "required",
    "workflowStatus",
)

TRUST_CHALLENGE_PUBLIC_POLICY_KEYS: tuple[str, ...] = (
    "version",
    "policyStatus",
    "policyVersion",
    "kernelHash",
    "challengeWindow",
    "maxOpenChallenges",
)

TRUST_CHALLENGE_PUBLIC_VISIBILITY_KEYS: tuple[str, ...] = (
    "version",
    "layer",
    "payloadLayer",
    "allowedSections",
    "forbiddenFieldFamilies",
    "chatProxyRequired",
    "directAiServiceAccessAllowed",
    "internalRouteHintsAllowed",
)

TRUST_CHALLENGE_PUBLIC_CACHE_KEYS: tuple[str, ...] = (
    "cacheable",
    "ttlSeconds",
    "staleIfErrorSeconds",
    "cacheKey",
    "varyBy",
)

TRUST_CHALLENGE_PUBLIC_ELIGIBILITY_STATUSES: frozenset[str] = frozenset(
    {
        "eligible",
        "not_eligible",
        "already_open",
        "under_review",
        "closed",
        "case_absent",
        "env_blocked",
    }
)

TRUST_CHALLENGE_PUBLIC_BLOCKERS: frozenset[str] = frozenset(
    {
        "challenge_case_absent",
        "challenge_report_not_final",
        "challenge_policy_disabled",
        "challenge_window_closed",
        "challenge_duplicate_open",
        "challenge_review_already_closed",
        "challenge_permission_required",
        "challenge_env_blocked",
    }
)

TRUST_CHALLENGE_PUBLIC_CHALLENGE_STATES: frozenset[str] = frozenset(
    {
        "not_challenged",
        "challenge_requested",
        "challenge_accepted",
        "under_internal_review",
        "verdict_upheld",
        "verdict_overturned",
        "draw_after_review",
        "review_retained",
        "challenge_closed",
        "case_absent",
    }
)

TRUST_CHALLENGE_PUBLIC_REVIEW_STATES: frozenset[str] = frozenset(
    {
        "not_required",
        "pending_review",
        "approved",
        "rejected",
        "not_available",
    }
)

TRUST_CHALLENGE_PUBLIC_ALLOWED_ACTIONS: frozenset[str] = frozenset(
    {
        "challenge.view",
        "challenge.request",
        "review.view",
    }
)

TRUST_CHALLENGE_PUBLIC_OPEN_STATES: frozenset[str] = frozenset(
    {
        "challenge_requested",
        "challenge_accepted",
        "under_internal_review",
    }
)

TRUST_CHALLENGE_PUBLIC_ALLOWED_SECTIONS: tuple[str, ...] = (
    "eligibility",
    "challenge_status",
    "review_status",
    "policy_summary",
    "cache_profile",
)

TRUST_CHALLENGE_PUBLIC_FORBIDDEN_FIELD_FAMILIES: tuple[str, ...] = (
    "raw_prompt",
    "raw_trace",
    "private_audit",
    "object_storage_locator",
    "internal_route",
    "provider_runtime",
)

TRUST_CHALLENGE_PUBLIC_CACHE_VARY_BY: tuple[str, ...] = (
    "caseId",
    "dispatchType",
    "traceId",
    "statusVersion",
)

TRUST_CHALLENGE_PUBLIC_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "bucket",
        "endpoint",
        "internalkey",
        "objectkey",
        "objectpath",
        "objectstorelocator",
        "objectstorepath",
        "path",
        "privateaudit",
        "prompt",
        "prompttext",
        "provider",
        "rawprompt",
        "rawtrace",
        "secret",
        "secretkey",
        "signedurl",
        "url",
    }
)


def _required_keys_missing(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [key for key in keys if key not in payload]


def _assert_required_keys(
    *,
    section: str,
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> None:
    missing = _required_keys_missing(payload, keys)
    if missing:
        raise ValueError(f"{section}_missing_keys:{','.join(sorted(missing))}")


def _assert_only_keys(
    *,
    section: str,
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> None:
    allowed = set(keys)
    extra = sorted(str(key) for key in payload.keys() if str(key) not in allowed)
    if extra:
        raise ValueError(f"{section}_unexpected_keys:{','.join(extra)}")


def _assert_non_empty_string(section: str, value: Any) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{section}_empty")


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().replace("_", "").replace("-", "").lower()


def _token(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _non_negative_int(value: Any, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _normalize_dispatch_type(value: Any) -> str:
    token = str(value or "auto").strip().lower()
    return token if token in {"auto", "phase", "final"} else "auto"


def _challenge_items(challenge_review: dict[str, Any]) -> list[dict[str, Any]]:
    challenges = challenge_review.get("challenges")
    if not isinstance(challenges, list):
        return []
    return [dict(item) for item in challenges if isinstance(item, dict)]


def _find_active_challenge(challenges: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in challenges:
        state = str(item.get("currentState") or "").strip().lower()
        if state in TRUST_CHALLENGE_PUBLIC_OPEN_STATES:
            return item
    return None


def _latest_challenge(challenges: list[dict[str, Any]]) -> dict[str, Any] | None:
    return challenges[0] if challenges else None


def _build_visibility_contract() -> dict[str, Any]:
    return {
        "version": TRUST_CHALLENGE_PUBLIC_VISIBILITY_VERSION,
        "layer": "public",
        "payloadLayer": "challenge_status_only",
        "allowedSections": list(TRUST_CHALLENGE_PUBLIC_ALLOWED_SECTIONS),
        "forbiddenFieldFamilies": list(
            TRUST_CHALLENGE_PUBLIC_FORBIDDEN_FIELD_FAMILIES
        ),
        "chatProxyRequired": True,
        "directAiServiceAccessAllowed": False,
        "internalRouteHintsAllowed": False,
    }


def _build_cache_profile(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str | None,
    eligibility_status: str,
) -> dict[str, Any]:
    cacheable = eligibility_status == "closed"
    return {
        "cacheable": cacheable,
        "ttlSeconds": 300 if cacheable else 0,
        "staleIfErrorSeconds": 0,
        "cacheKey": (
            f"case:{int(case_id)}"
            f":dispatch:{dispatch_type}"
            f":trace:{trace_id or 'none'}"
            f":status:{TRUST_CHALLENGE_PUBLIC_STATUS_VERSION}"
        ),
        "varyBy": list(TRUST_CHALLENGE_PUBLIC_CACHE_VARY_BY),
    }


def find_trust_challenge_public_forbidden_keys(payload: Any) -> set[str]:
    violations: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if _normalize_key(key) in TRUST_CHALLENGE_PUBLIC_FORBIDDEN_KEYS:
                    violations.add(str(key))
                _walk(child)
        elif isinstance(value, list):
            for child in value:
                _walk(child)

    _walk(payload)
    return violations


def build_trust_challenge_public_status(
    *,
    case_id: int,
    dispatch_type: str,
    trace_id: str | None,
    challenge_review: dict[str, Any] | None,
    workflow_status: str | None,
    kernel_version: dict[str, Any] | None = None,
    policy_enabled: bool = True,
    challenge_window_open: bool = True,
    permission_required: bool = False,
    env_blocked: bool = False,
    case_absent: bool = False,
) -> dict[str, Any]:
    normalized_dispatch_type = _normalize_dispatch_type(dispatch_type)
    trace_token = _token(trace_id)
    review_payload = _dict_or_empty(challenge_review)
    kernel_payload = _dict_or_empty(kernel_version)
    kernel_vector = _dict_or_empty(kernel_payload.get("kernelVector"))
    challenges = _challenge_items(review_payload)
    active_challenge = _find_active_challenge(challenges)
    latest = active_challenge or _latest_challenge(challenges)

    if case_absent:
        challenge_state = "case_absent"
        review_state = "not_available"
    else:
        challenge_state = (
            str(
                review_payload.get("challengeState")
                or review_payload.get("state")
                or ""
            )
            .strip()
            .lower()
        )
        if not challenge_state:
            challenge_state = "not_challenged"
        review_state = (
            str(review_payload.get("reviewState") or "not_required").strip().lower()
        )

    review_required = bool(review_payload.get("reviewRequired"))
    total_challenges = _non_negative_int(
        review_payload.get("totalChallenges"),
        default=len(challenges),
    )
    active_challenge_id = _token(review_payload.get("activeChallengeId"))
    if active_challenge is not None and active_challenge_id is None:
        active_challenge_id = _token(active_challenge.get("challengeId"))
    latest_challenge_id = _token(latest.get("challengeId")) if latest else None
    latest_decision = _token(latest.get("decision")) if latest else None
    latest_reason_code = _token(latest.get("reasonCode")) if latest else None

    blockers: list[str] = []
    if case_absent:
        blockers.append("challenge_case_absent")
    elif env_blocked:
        blockers.append("challenge_env_blocked")
    elif not policy_enabled:
        blockers.append("challenge_policy_disabled")
    elif normalized_dispatch_type != "final":
        blockers.append("challenge_report_not_final")
    elif not challenge_window_open:
        blockers.append("challenge_window_closed")
    elif active_challenge is not None:
        blockers.append("challenge_duplicate_open")
    elif total_challenges > 0 or challenge_state == "challenge_closed":
        blockers.append("challenge_review_already_closed")
    elif permission_required:
        blockers.append("challenge_permission_required")

    if case_absent:
        eligibility_status = "case_absent"
    elif env_blocked:
        eligibility_status = "env_blocked"
    elif active_challenge is not None and challenge_state == "under_internal_review":
        eligibility_status = "under_review"
    elif active_challenge is not None:
        eligibility_status = "already_open"
    elif blockers and blockers[0] == "challenge_review_already_closed":
        eligibility_status = "closed"
    elif blockers:
        eligibility_status = "not_eligible"
    else:
        eligibility_status = "eligible"

    requestable = eligibility_status == "eligible"
    allowed_actions: list[str] = []
    if not case_absent and not env_blocked:
        allowed_actions.append("challenge.view")
        if requestable:
            allowed_actions.append("challenge.request")
        if review_required or total_challenges > 0 or active_challenge is not None:
            allowed_actions.append("review.view")

    policy_status = "env_blocked" if env_blocked else "enabled"
    if not policy_enabled:
        policy_status = "disabled"
    challenge_window = "open" if challenge_window_open else "closed"
    if normalized_dispatch_type != "final" and not case_absent:
        challenge_window = "not_final"

    payload = {
        "version": TRUST_CHALLENGE_PUBLIC_STATUS_VERSION,
        "caseId": int(case_id),
        "dispatchType": normalized_dispatch_type,
        "traceId": trace_token,
        "eligibility": {
            "status": eligibility_status,
            "eligible": requestable,
            "requestable": requestable,
            "reasonCode": blockers[0] if blockers else None,
            "blockers": blockers,
        },
        "challengeState": challenge_state,
        "reviewState": review_state,
        "allowedActions": allowed_actions,
        "blockers": blockers,
        "policy": {
            "version": "trust-challenge-policy-v1",
            "policyStatus": policy_status,
            "policyVersion": _token(kernel_vector.get("policyVersion")),
            "kernelHash": _token(
                kernel_payload.get("kernelHash") or kernel_payload.get("registryHash")
            ),
            "challengeWindow": challenge_window,
            "maxOpenChallenges": 1,
        },
        "challenge": {
            "state": challenge_state,
            "activeChallengeId": active_challenge_id,
            "latestChallengeId": latest_challenge_id,
            "latestDecision": latest_decision,
            "latestReasonCode": latest_reason_code,
            "totalChallenges": total_challenges,
        },
        "review": {
            "state": review_state,
            "required": review_required,
            "workflowStatus": _token(workflow_status),
        },
        "visibilityContract": _build_visibility_contract(),
        "cacheProfile": _build_cache_profile(
            case_id=int(case_id),
            dispatch_type=normalized_dispatch_type,
            trace_id=trace_token,
            eligibility_status=eligibility_status,
        ),
    }
    validate_trust_challenge_public_contract(payload)
    return payload


def _assert_no_forbidden_fields(payload: dict[str, Any]) -> None:
    forbidden_keys = sorted(find_trust_challenge_public_forbidden_keys(payload))
    if forbidden_keys:
        raise ValueError(
            "trust_challenge_public_forbidden_fields:" + ",".join(forbidden_keys)
        )


def _validate_eligibility(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_challenge_public_eligibility",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_ELIGIBILITY_KEYS,
    )
    _assert_only_keys(
        section="trust_challenge_public_eligibility",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_ELIGIBILITY_KEYS,
    )
    status = str(payload.get("status") or "").strip().lower()
    if status not in TRUST_CHALLENGE_PUBLIC_ELIGIBILITY_STATUSES:
        raise ValueError("trust_challenge_public_eligibility_status_invalid")
    if not isinstance(payload.get("eligible"), bool):
        raise ValueError("trust_challenge_public_eligibility_eligible_not_bool")
    if not isinstance(payload.get("requestable"), bool):
        raise ValueError("trust_challenge_public_eligibility_requestable_not_bool")
    blockers = payload.get("blockers")
    if not isinstance(blockers, list):
        raise ValueError("trust_challenge_public_eligibility_blockers_not_list")
    invalid_blockers = [
        str(item)
        for item in blockers
        if str(item or "").strip().lower() not in TRUST_CHALLENGE_PUBLIC_BLOCKERS
    ]
    if invalid_blockers:
        raise ValueError("trust_challenge_public_eligibility_blockers_invalid")
    reason_code = payload.get("reasonCode")
    if blockers and reason_code != blockers[0]:
        raise ValueError("trust_challenge_public_eligibility_reason_code_mismatch")
    if not blockers and reason_code is not None:
        raise ValueError("trust_challenge_public_eligibility_reason_code_unexpected")
    requestable = bool(payload.get("requestable"))
    if status == "eligible":
        if payload.get("eligible") is not True or requestable is not True or blockers:
            raise ValueError("trust_challenge_public_eligibility_ready_invalid")
    elif payload.get("eligible") is not False or requestable is not False:
        raise ValueError("trust_challenge_public_eligibility_blocked_invalid")


def _validate_policy(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_challenge_public_policy",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_POLICY_KEYS,
    )
    _assert_only_keys(
        section="trust_challenge_public_policy",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_POLICY_KEYS,
    )
    if payload.get("version") != "trust-challenge-policy-v1":
        raise ValueError("trust_challenge_public_policy_version_invalid")
    if payload.get("policyStatus") not in {"enabled", "disabled", "env_blocked"}:
        raise ValueError("trust_challenge_public_policy_status_invalid")
    if payload.get("challengeWindow") not in {"open", "closed", "not_final"}:
        raise ValueError("trust_challenge_public_policy_window_invalid")
    if _non_negative_int(payload.get("maxOpenChallenges"), default=-1) != 1:
        raise ValueError("trust_challenge_public_policy_max_open_invalid")


def _validate_challenge(payload: dict[str, Any], *, parent: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_challenge_public_challenge",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_CHALLENGE_KEYS,
    )
    _assert_only_keys(
        section="trust_challenge_public_challenge",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_CHALLENGE_KEYS,
    )
    if payload.get("state") != parent.get("challengeState"):
        raise ValueError("trust_challenge_public_challenge_state_mismatch")
    total = _non_negative_int(payload.get("totalChallenges"), default=-1)
    if total < 0:
        raise ValueError("trust_challenge_public_challenge_total_invalid")
    state = str(payload.get("state") or "").strip().lower()
    active_id = _token(payload.get("activeChallengeId"))
    if state in TRUST_CHALLENGE_PUBLIC_OPEN_STATES and not active_id:
        raise ValueError("trust_challenge_public_challenge_active_id_required")
    if state not in TRUST_CHALLENGE_PUBLIC_OPEN_STATES and active_id:
        raise ValueError("trust_challenge_public_challenge_active_id_unexpected")


def _validate_review(payload: dict[str, Any], *, parent: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_challenge_public_review",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_REVIEW_KEYS,
    )
    _assert_only_keys(
        section="trust_challenge_public_review",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_REVIEW_KEYS,
    )
    if payload.get("state") != parent.get("reviewState"):
        raise ValueError("trust_challenge_public_review_state_mismatch")
    if not isinstance(payload.get("required"), bool):
        raise ValueError("trust_challenge_public_review_required_not_bool")


def _validate_visibility(payload: dict[str, Any]) -> None:
    _assert_required_keys(
        section="trust_challenge_public_visibility",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_VISIBILITY_KEYS,
    )
    _assert_only_keys(
        section="trust_challenge_public_visibility",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_VISIBILITY_KEYS,
    )
    if payload.get("version") != TRUST_CHALLENGE_PUBLIC_VISIBILITY_VERSION:
        raise ValueError("trust_challenge_public_visibility_version_invalid")
    if payload.get("layer") != "public":
        raise ValueError("trust_challenge_public_visibility_layer_invalid")
    if payload.get("payloadLayer") != "challenge_status_only":
        raise ValueError("trust_challenge_public_visibility_payload_layer_invalid")
    if set(payload.get("allowedSections") or []) != set(
        TRUST_CHALLENGE_PUBLIC_ALLOWED_SECTIONS
    ):
        raise ValueError("trust_challenge_public_visibility_allowed_sections_invalid")
    if set(payload.get("forbiddenFieldFamilies") or []) != set(
        TRUST_CHALLENGE_PUBLIC_FORBIDDEN_FIELD_FAMILIES
    ):
        raise ValueError("trust_challenge_public_visibility_forbidden_fields_invalid")
    if payload.get("chatProxyRequired") is not True:
        raise ValueError("trust_challenge_public_visibility_chat_proxy_invalid")
    if payload.get("directAiServiceAccessAllowed") is not False:
        raise ValueError("trust_challenge_public_visibility_direct_access_invalid")
    if payload.get("internalRouteHintsAllowed") is not False:
        raise ValueError("trust_challenge_public_visibility_route_hints_invalid")


def _validate_cache(payload: dict[str, Any], *, eligibility_status: str) -> None:
    _assert_required_keys(
        section="trust_challenge_public_cache",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_CACHE_KEYS,
    )
    _assert_only_keys(
        section="trust_challenge_public_cache",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_CACHE_KEYS,
    )
    if not isinstance(payload.get("cacheable"), bool):
        raise ValueError("trust_challenge_public_cache_cacheable_not_bool")
    ttl_seconds = _non_negative_int(payload.get("ttlSeconds"), default=-1)
    if ttl_seconds < 0:
        raise ValueError("trust_challenge_public_cache_ttl_invalid")
    if payload.get("cacheable") is True and eligibility_status != "closed":
        raise ValueError("trust_challenge_public_cache_cacheable_status_invalid")
    if payload.get("cacheable") is True and ttl_seconds <= 0:
        raise ValueError("trust_challenge_public_cache_ready_ttl_invalid")
    if payload.get("cacheable") is False and ttl_seconds != 0:
        raise ValueError("trust_challenge_public_cache_blocked_ttl_invalid")
    _assert_non_empty_string("trust_challenge_public_cache_key", payload.get("cacheKey"))
    if payload.get("varyBy") != list(TRUST_CHALLENGE_PUBLIC_CACHE_VARY_BY):
        raise ValueError("trust_challenge_public_cache_vary_by_invalid")


def validate_trust_challenge_public_contract(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("trust_challenge_public_payload_not_dict")
    _assert_no_forbidden_fields(payload)
    _assert_required_keys(
        section="trust_challenge_public",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_TOP_LEVEL_KEYS,
    )
    _assert_only_keys(
        section="trust_challenge_public",
        payload=payload,
        keys=TRUST_CHALLENGE_PUBLIC_TOP_LEVEL_KEYS,
    )
    if payload.get("version") != TRUST_CHALLENGE_PUBLIC_STATUS_VERSION:
        raise ValueError("trust_challenge_public_version_invalid")
    case_id = _non_negative_int(payload.get("caseId"), default=0)
    if case_id <= 0:
        raise ValueError("trust_challenge_public_case_id_invalid")
    dispatch_type = str(payload.get("dispatchType") or "").strip().lower()
    if dispatch_type not in {"auto", "phase", "final"}:
        raise ValueError("trust_challenge_public_dispatch_type_invalid")

    eligibility = payload.get("eligibility")
    if not isinstance(eligibility, dict):
        raise ValueError("trust_challenge_public_eligibility_not_dict")
    _validate_eligibility(eligibility)
    eligibility_status = str(eligibility.get("status") or "").strip().lower()
    if eligibility_status != "case_absent":
        _assert_non_empty_string("trust_challenge_public_trace_id", payload.get("traceId"))
    elif payload.get("traceId") is not None:
        raise ValueError("trust_challenge_public_case_absent_trace_unexpected")

    challenge_state = str(payload.get("challengeState") or "").strip().lower()
    if challenge_state not in TRUST_CHALLENGE_PUBLIC_CHALLENGE_STATES:
        raise ValueError("trust_challenge_public_challenge_state_invalid")
    review_state = str(payload.get("reviewState") or "").strip().lower()
    if review_state not in TRUST_CHALLENGE_PUBLIC_REVIEW_STATES:
        raise ValueError("trust_challenge_public_review_state_invalid")

    allowed_actions = payload.get("allowedActions")
    if not isinstance(allowed_actions, list):
        raise ValueError("trust_challenge_public_allowed_actions_not_list")
    if set(allowed_actions) - set(TRUST_CHALLENGE_PUBLIC_ALLOWED_ACTIONS):
        raise ValueError("trust_challenge_public_allowed_actions_invalid")
    if eligibility_status == "eligible" and "challenge.request" not in allowed_actions:
        raise ValueError("trust_challenge_public_request_action_required")
    if eligibility_status != "eligible" and "challenge.request" in allowed_actions:
        raise ValueError("trust_challenge_public_request_action_forbidden")

    blockers = payload.get("blockers")
    if blockers != eligibility.get("blockers"):
        raise ValueError("trust_challenge_public_blockers_mismatch")
    if eligibility_status == "case_absent" and blockers != ["challenge_case_absent"]:
        raise ValueError("trust_challenge_public_case_absent_blockers_invalid")

    policy = payload.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("trust_challenge_public_policy_not_dict")
    _validate_policy(policy)
    if dispatch_type != "final" and eligibility_status == "eligible":
        raise ValueError("trust_challenge_public_non_final_eligible_invalid")

    challenge = payload.get("challenge")
    if not isinstance(challenge, dict):
        raise ValueError("trust_challenge_public_challenge_not_dict")
    _validate_challenge(challenge, parent=payload)

    review = payload.get("review")
    if not isinstance(review, dict):
        raise ValueError("trust_challenge_public_review_not_dict")
    _validate_review(review, parent=payload)

    visibility = payload.get("visibilityContract")
    if not isinstance(visibility, dict):
        raise ValueError("trust_challenge_public_visibility_not_dict")
    _validate_visibility(visibility)

    cache = payload.get("cacheProfile")
    if not isinstance(cache, dict):
        raise ValueError("trust_challenge_public_cache_not_dict")
    _validate_cache(cache, eligibility_status=eligibility_status)
