#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.applications.artifact_pack import build_artifact_store_healthcheck_payload  # noqa: E402
from app.settings import load_settings  # noqa: E402
from app.wiring import build_artifact_store  # noqa: E402

ARTIFACT_STORE_HEALTHCHECK_EVIDENCE_VERSION = "artifact-store-healthcheck-evidence-v1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _production_ready_from_healthcheck(healthcheck: dict[str, Any]) -> bool:
    return (
        healthcheck.get("status") == "ready"
        and healthcheck.get("writeReadRoundtripStatus") == "pass"
        and healthcheck.get("productionReady") is True
    )


def _real_env_blocker_code(healthcheck: dict[str, Any]) -> str | None:
    if _production_ready_from_healthcheck(healthcheck):
        return None
    provider = str(healthcheck.get("provider") or "").strip().lower()
    roundtrip_status = str(healthcheck.get("writeReadRoundtripStatus") or "").strip().lower()
    if provider == "local":
        return "production_artifact_store_local_reference"
    if roundtrip_status == "not_enabled":
        return "production_artifact_store_roundtrip_not_enabled"
    if roundtrip_status == "configuration_missing":
        return "production_artifact_store_configuration_missing"
    if healthcheck.get("status") == "blocked":
        return "production_artifact_store_roundtrip_failed"
    return "production_artifact_store_not_ready"


def build_artifact_store_healthcheck_evidence(
    *,
    healthcheck: dict[str, Any],
    roundtrip_enabled: bool,
    roundtrip_source: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    ready = _production_ready_from_healthcheck(healthcheck)
    blocker_code = _real_env_blocker_code(healthcheck)
    return {
        "version": ARTIFACT_STORE_HEALTHCHECK_EVIDENCE_VERSION,
        "generatedAt": _isoformat(generated_at or _utcnow()),
        "provider": str(healthcheck.get("provider") or "unknown"),
        "status": str(healthcheck.get("status") or "unknown"),
        "productionReady": ready,
        "roundtrip": {
            "enabled": bool(roundtrip_enabled),
            "source": str(roundtrip_source or "unknown"),
            "status": str(healthcheck.get("writeReadRoundtripStatus") or "unknown"),
            "lastErrorCode": healthcheck.get("lastErrorCode"),
        },
        "realEnvWindow": {
            "productionArtifactStoreReady": ready,
            "recommendedEnv": {
                "PRODUCTION_ARTIFACT_STORE_READY": "true" if ready else "false",
            },
            "blockerCode": blocker_code,
        },
        "redactionContract": {
            "bucketNameVisible": False,
            "prefixVisible": False,
            "endpointVisible": False,
            "storageUriVisible": False,
            "secretVisible": False,
        },
        "healthcheck": dict(healthcheck),
    }


async def run_healthcheck(
    *,
    roundtrip_enabled: bool | None = None,
) -> dict[str, Any]:
    settings = load_settings()
    effective_roundtrip = (
        settings.artifact_store_healthcheck_enabled
        if roundtrip_enabled is None
        else bool(roundtrip_enabled)
    )
    source = "settings" if roundtrip_enabled is None else "cli_override"
    artifact_store = build_artifact_store(settings=settings)
    healthcheck = await build_artifact_store_healthcheck_payload(
        artifact_store=artifact_store,
        roundtrip_enabled=effective_roundtrip,
    )
    return build_artifact_store_healthcheck_evidence(
        healthcheck=healthcheck,
        roundtrip_enabled=effective_roundtrip,
        roundtrip_source=source,
    )


def _write_json(path: str | None, payload: dict[str, Any]) -> Path | None:
    if not path:
        return None
    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export sanitized AI Judge artifact store healthcheck evidence."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--enable-roundtrip",
        action="store_true",
        help="override settings and run write/head/read roundtrip",
    )
    group.add_argument(
        "--disable-roundtrip",
        action="store_true",
        help="override settings and skip write/head/read roundtrip",
    )
    parser.add_argument(
        "--output",
        default="",
        help="write evidence JSON to this path",
    )
    parser.add_argument(
        "--fail-on-not-ready",
        action="store_true",
        help="exit 1 when production artifact store is not roundtrip-ready",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    roundtrip_override: bool | None = None
    if args.enable_roundtrip:
        roundtrip_override = True
    elif args.disable_roundtrip:
        roundtrip_override = False

    evidence = asyncio.run(run_healthcheck(roundtrip_enabled=roundtrip_override))
    output_path = _write_json(args.output, evidence)
    print(
        "[artifact-store-healthcheck] "
        f"status={evidence['status']} "
        f"roundtrip={evidence['roundtrip']['status']} "
        f"production_ready={str(evidence['productionReady']).lower()}"
    )
    if output_path is not None:
        print(f"[artifact-store-healthcheck] evidence={output_path}")
    if args.fail_on_not_ready and not bool(evidence["productionReady"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
