from __future__ import annotations

import unittest

from app.app_factory import create_app, create_runtime, require_internal_key
from fastapi import HTTPException

from tests.app_factory_test_helpers import build_settings as _build_settings


class AppFactorySmokeTests(unittest.TestCase):
    def test_require_internal_key_should_validate_header(self) -> None:
        settings = _build_settings(ai_internal_key="expected")

        with self.assertRaises(HTTPException) as ctx_missing:
            require_internal_key(settings, None)
        self.assertEqual(ctx_missing.exception.status_code, 401)
        self.assertEqual(ctx_missing.exception.detail, "missing x-ai-internal-key")

        with self.assertRaises(HTTPException) as ctx_invalid:
            require_internal_key(settings, "wrong")
        self.assertEqual(ctx_invalid.exception.status_code, 401)
        self.assertEqual(ctx_invalid.exception.detail, "invalid x-ai-internal-key")

        require_internal_key(settings, " expected ")

    def test_create_app_should_expose_v3_routes_only(self) -> None:
        runtime = create_runtime(settings=_build_settings())
        app = create_app(runtime)
        paths = {getattr(route, "path", "") for route in app.routes}

        self.assertIn("/healthz", paths)
        self.assertIn("/internal/judge/v3/phase/dispatch", paths)
        self.assertIn("/internal/judge/v3/final/dispatch", paths)
        self.assertIn("/internal/judge/cases", paths)
        self.assertIn("/internal/judge/cases/{case_id}", paths)
        self.assertIn("/internal/judge/cases/{case_id}/claim-ledger", paths)
        self.assertIn("/internal/judge/cases/{case_id}/courtroom-read-model", paths)
        self.assertIn("/internal/judge/courtroom/cases", paths)
        self.assertIn("/internal/judge/courtroom/drilldown-bundle", paths)
        self.assertIn("/internal/judge/evidence-claim/ops-queue", paths)
        self.assertIn("/internal/judge/policies", paths)
        self.assertIn("/internal/judge/policies/{policy_version}", paths)
        self.assertIn("/internal/judge/registries/prompts", paths)
        self.assertIn("/internal/judge/registries/prompts/{prompt_version}", paths)
        self.assertIn("/internal/judge/registries/tools", paths)
        self.assertIn("/internal/judge/registries/tools/{toolset_version}", paths)
        self.assertIn("/internal/judge/registries/policy/dependencies/health", paths)
        self.assertIn("/internal/judge/registries/policy/domain-families", paths)
        self.assertIn("/internal/judge/registries/policy/gate-simulation", paths)
        self.assertIn("/internal/judge/registries/governance/overview", paths)
        self.assertIn("/internal/judge/registries/prompt-tool/governance", paths)
        self.assertIn("/internal/judge/registries/{registry_type}/publish", paths)
        self.assertIn(
            "/internal/judge/registries/{registry_type}/{version}/activate",
            paths,
        )
        self.assertIn("/internal/judge/registries/{registry_type}/rollback", paths)
        self.assertIn("/internal/judge/registries/{registry_type}/audits", paths)
        self.assertIn("/internal/judge/registries/{registry_type}/releases", paths)
        self.assertIn(
            "/internal/judge/registries/{registry_type}/releases/{version}",
            paths,
        )
        self.assertIn("/internal/judge/fairness/cases", paths)
        self.assertIn("/internal/judge/fairness/cases/{case_id}", paths)
        self.assertIn("/internal/judge/panels/runtime/profiles", paths)
        self.assertIn("/internal/judge/panels/runtime/readiness", paths)
        self.assertIn("/internal/judge/cases/{case_id}/attestation/verify", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/commitment", paths)
        self.assertIn(
            "/internal/judge/cases/{case_id}/trust/verdict-attestation",
            paths,
        )
        self.assertIn("/internal/judge/cases/{case_id}/trust/challenges", paths)
        self.assertIn("/internal/judge/trust/challenges/ops-queue", paths)
        self.assertIn(
            "/internal/judge/cases/{case_id}/trust/challenges/request",
            paths,
        )
        self.assertIn(
            "/internal/judge/cases/{case_id}/trust/challenges/{challenge_id}/decision",
            paths,
        )
        self.assertIn("/internal/judge/cases/{case_id}/trust/kernel-version", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/audit-anchor", paths)
        self.assertIn("/internal/judge/cases/{case_id}/trust/public-verify", paths)
        self.assertIn("/internal/judge/alerts/ops-view", paths)
        self.assertIn("/internal/judge/fairness/benchmark-runs", paths)
        self.assertIn("/internal/judge/fairness/shadow-runs", paths)
        self.assertIn("/internal/judge/fairness/dashboard", paths)
        self.assertIn("/internal/judge/fairness/calibration-pack", paths)
        self.assertIn("/internal/judge/fairness/policy-calibration-advisor", paths)
        self.assertIn("/internal/judge/ops/read-model/pack", paths)
        self.assertNotIn("/internal/judge/dispatch", paths)
