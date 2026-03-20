from __future__ import annotations

STYLE_RATIONAL = "rational"
STYLE_ENTERTAINING = "entertaining"
STYLE_MIXED = "mixed"
VALID_STYLE_MODES = {STYLE_RATIONAL, STYLE_ENTERTAINING, STYLE_MIXED}


def _normalize_style_mode(mode: str | None) -> str | None:
    if mode is None:
        return None
    value = mode.strip().lower()
    if value in VALID_STYLE_MODES:
        return value
    return None


def resolve_effective_style_mode(
    request_style_mode: str,
    system_style_mode: str | None,
) -> tuple[str, str]:
    normalized_system = _normalize_style_mode(system_style_mode)
    if system_style_mode is not None:
        if normalized_system is not None:
            return normalized_system, "system_config"
        return STYLE_RATIONAL, "system_config_fallback_default"

    normalized_request = _normalize_style_mode(request_style_mode)
    if normalized_request is not None:
        return normalized_request, "job_request"
    return STYLE_RATIONAL, "default"

