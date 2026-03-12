from __future__ import annotations

import os

PROVIDER_MOCK = "mock"
PROVIDER_OPENAI = "openai"

VALID_PROVIDERS = {
    PROVIDER_MOCK,
    PROVIDER_OPENAI,
}


def parse_env_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def normalize_provider(provider: str | None) -> str:
    if provider is None:
        return PROVIDER_OPENAI
    normalized = provider.strip().lower()
    if normalized in {PROVIDER_MOCK, "dev_mock"}:
        return PROVIDER_MOCK
    if normalized in VALID_PROVIDERS:
        return normalized
    return PROVIDER_OPENAI


def should_use_openai(provider: str, openai_api_key: str | None) -> bool:
    if provider != PROVIDER_OPENAI:
        return False
    return bool(openai_api_key and openai_api_key.strip())


def runtime_env_label() -> str | None:
    for key in ("ECHOISLE_ENV", "APP_ENV", "PYTHON_ENV", "RUST_ENV", "ENV"):
        value = os.getenv(key)
        if value is None:
            continue
        normalized = value.strip()
        if normalized:
            return normalized.lower()
    return None


def is_production_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"prod", "production"}
