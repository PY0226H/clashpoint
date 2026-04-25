from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from app.app_factory import create_app, create_runtime

from tests.app_factory_test_helpers import (
    AppFactoryRouteTestMixin,
)
from tests.app_factory_test_helpers import (
    build_final_request as _build_final_request,
)
from tests.app_factory_test_helpers import (
    build_phase_request as _build_phase_request,
)
from tests.app_factory_test_helpers import (
    build_settings as _build_settings,
)
from tests.app_factory_test_helpers import (
    unique_case_id as _unique_case_id,
)


class AppFactoryTrustAttestationRouteTests(
    AppFactoryRouteTestMixin,
    unittest.IsolatedAsyncioTestCase,
):
    def _create_app_with_patched_trust_contract(
        self,
        runtime: object,
        contract_name: str,
        message: str,
    ):
        with patch(
            f"app.applications.bootstrap_trust_ops_dependencies.{contract_name}",
            side_effect=ValueError(message),
        ):
            return create_app(runtime)

    async def test_attestation_verify_should_use_auto_dispatch_and_return_verified(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(case_id=8103, idempotency_key="phase:8103")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=8103, idempotency_key="final:8103")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        verify_resp = await self._post(
            app=app,
            path="/internal/judge/cases/8103/attestation/verify?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(verify_resp.status_code, 200)
        verify_payload = verify_resp.json()
        self.assertEqual(verify_payload["dispatchType"], "final")
        self.assertEqual(verify_payload["traceId"], "trace-final-8103")
        self.assertTrue(verify_payload["verified"])
        self.assertEqual(verify_payload["reason"], "ok")
        self.assertEqual(verify_payload["mismatchComponents"], [])

    async def test_attestation_verify_should_detect_tampered_report_payload(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        phase_req = _build_phase_request(case_id=8104, idempotency_key="phase:8104")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=8104, idempotency_key="final:8104")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        fact_receipt = await runtime.workflow_runtime.facts.get_dispatch_receipt(
            dispatch_type="final",
            job_id=8104,
        )
        self.assertIsNotNone(fact_receipt)
        assert fact_receipt is not None
        response_payload = dict(fact_receipt.response or {})
        report_payload = (
            dict(response_payload.get("reportPayload"))
            if isinstance(response_payload.get("reportPayload"), dict)
            else {}
        )
        report_payload["winner"] = "draw" if report_payload.get("winner") != "draw" else "pro"
        response_payload["reportPayload"] = report_payload
        await runtime.workflow_runtime.facts.upsert_dispatch_receipt(
            receipt=replace(fact_receipt, response=response_payload),
        )

        verify_resp = await self._post(
            app=app,
            path="/internal/judge/cases/8104/attestation/verify?dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(verify_resp.status_code, 200)
        verify_payload = verify_resp.json()
        self.assertFalse(verify_payload["verified"])
        self.assertEqual(verify_payload["reason"], "trust_attestation_mismatch")
        self.assertIn("verdictHash", verify_payload["mismatchComponents"])

    async def test_trust_routes_should_return_phasea_registry_bundle(self) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = create_app(runtime)

        case_id = _unique_case_id(8105)
        phase_req = _build_phase_request(case_id=case_id, idempotency_key=f"phase:{case_id}")
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=phase_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)

        final_req = _build_final_request(case_id=case_id, idempotency_key=f"final:{case_id}")
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=final_req.model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        commitment_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/commitment?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(commitment_resp.status_code, 200)
        commitment_payload = commitment_resp.json()
        commitment_item = commitment_payload["item"]
        self.assertEqual(commitment_payload["dispatchType"], "final")
        self.assertEqual(commitment_payload["traceId"], f"trace-final-{case_id}")
        self.assertEqual(commitment_item["version"], "trust-phaseA-case-commitment-v1")
        self.assertIn("commitmentHash", commitment_item)

        attestation_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/verdict-attestation?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(attestation_resp.status_code, 200)
        attestation_item = attestation_resp.json()["item"]
        self.assertEqual(attestation_item["version"], "trust-phaseA-verdict-attestation-v1")
        self.assertTrue(attestation_item["verified"])
        self.assertEqual(attestation_item["reason"], "ok")
        self.assertIn("registryHash", attestation_item)

        challenge_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/challenges?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(challenge_resp.status_code, 200)
        challenge_item = challenge_resp.json()["item"]
        self.assertEqual(challenge_item["version"], "trust-phaseB-challenge-review-v1")
        self.assertEqual(challenge_item["reviewState"], "approved")
        self.assertIn("registryHash", challenge_item)

        kernel_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/kernel-version?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(kernel_resp.status_code, 200)
        kernel_item = kernel_resp.json()["item"]
        self.assertEqual(kernel_item["version"], "trust-phaseA-kernel-version-v1")
        self.assertIn("kernelVector", kernel_item)
        self.assertIn("kernelHash", kernel_item)
        self.assertIn("registryHash", kernel_item)

        anchor_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/audit-anchor?dispatch_type=auto&include_payload=true",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(anchor_resp.status_code, 200)
        anchor_item = anchor_resp.json()["item"]
        self.assertEqual(anchor_item["version"], "trust-phaseA-audit-anchor-v1")
        self.assertIn("anchorHash", anchor_item)
        self.assertIn("payload", anchor_item)
        self.assertEqual(
            anchor_item["componentHashes"]["caseCommitmentHash"],
            commitment_item["commitmentHash"],
        )
        self.assertEqual(
            anchor_item["componentHashes"]["verdictAttestationHash"],
            attestation_item["registryHash"],
        )
        self.assertEqual(
            anchor_item["componentHashes"]["challengeReviewHash"],
            challenge_item["registryHash"],
        )
        self.assertEqual(
            anchor_item["componentHashes"]["kernelVersionHash"],
            kernel_item["registryHash"],
        )

        public_verify_resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/public-verify?dispatch_type=auto",
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(public_verify_resp.status_code, 200)
        public_verify_payload = public_verify_resp.json()
        self.assertEqual(public_verify_payload["dispatchType"], "final")
        self.assertEqual(public_verify_payload["traceId"], f"trace-final-{case_id}")
        self.assertEqual(
            public_verify_payload["verificationVersion"],
            "trust-public-verification-v1",
        )
        self.assertIn(
            f"case:{case_id}:dispatch:final:trace:trace-final-{case_id}",
            public_verify_payload["verificationRequest"]["requestKey"],
        )
        self.assertEqual(public_verify_payload["verificationReadiness"]["status"], "ready")
        self.assertTrue(public_verify_payload["verificationReadiness"]["externalizable"])
        self.assertEqual(public_verify_payload["visibilityContract"]["layer"], "public")
        self.assertEqual(
            public_verify_payload["visibilityContract"]["payloadLayer"],
            "commitment_hashes_only",
        )
        self.assertTrue(public_verify_payload["visibilityContract"]["chatProxyRequired"])
        self.assertFalse(public_verify_payload["visibilityContract"]["directAiServiceAccessAllowed"])
        verify_payload = public_verify_payload["verifyPayload"]
        self.assertEqual(
            verify_payload["caseCommitment"]["commitmentHash"],
            commitment_item["commitmentHash"],
        )
        self.assertEqual(
            verify_payload["verdictAttestation"]["registryHash"],
            attestation_item["registryHash"],
        )
        self.assertEqual(
            verify_payload["challengeReview"]["registryHash"],
            challenge_item["registryHash"],
        )
        self.assertEqual(
            verify_payload["kernelVersion"]["registryHash"],
            kernel_item["registryHash"],
        )
        self.assertEqual(
            verify_payload["auditAnchor"]["anchorHash"],
            anchor_item["anchorHash"],
        )
        self.assertNotIn("attestation", verify_payload["verdictAttestation"])
        self.assertNotIn("challenges", verify_payload["challengeReview"])
        self.assertNotIn("timeline", verify_payload["challengeReview"])
        self.assertNotIn("reviewDecisions", verify_payload["challengeReview"])
        self.assertNotIn("openAlertIds", verify_payload["challengeReview"])
        self.assertNotIn("provider", verify_payload["kernelVersion"]["kernelVector"])
        self.assertNotIn("payload", verify_payload["auditAnchor"])

    async def test_trust_public_verify_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = self._create_app_with_patched_trust_contract(
            runtime,
            "validate_trust_public_verify_contract",
            "trust_public_verify_missing_keys:verifyPayload",
        )
        case_id = _unique_case_id(8106)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/public-verify?dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_public_verify_contract_violation")
        self.assertIn("trust_public_verify_missing_keys:verifyPayload", detail["message"])

    async def test_trust_commitment_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = self._create_app_with_patched_trust_contract(
            runtime,
            "validate_trust_commitment_contract",
            "trust_commitment_missing_keys:item",
        )
        case_id = _unique_case_id(8109)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/commitment?dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_commitment_contract_violation")
        self.assertIn("trust_commitment_missing_keys:item", detail["message"])

    async def test_trust_verdict_attestation_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = self._create_app_with_patched_trust_contract(
            runtime,
            "validate_trust_verdict_attestation_contract",
            "trust_verdict_attestation_missing_keys:item",
        )
        case_id = _unique_case_id(8110)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/verdict-attestation?dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_verdict_attestation_contract_violation")
        self.assertIn("trust_verdict_attestation_missing_keys:item", detail["message"])

    async def test_trust_challenge_review_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = self._create_app_with_patched_trust_contract(
            runtime,
            "validate_trust_challenge_review_contract",
            "trust_challenge_review_missing_keys:item",
        )
        case_id = _unique_case_id(8111)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/challenges?dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_challenge_review_contract_violation")
        self.assertIn("trust_challenge_review_missing_keys:item", detail["message"])

    async def test_trust_kernel_version_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = self._create_app_with_patched_trust_contract(
            runtime,
            "validate_trust_kernel_version_contract",
            "trust_kernel_version_missing_keys:item",
        )
        case_id = _unique_case_id(8107)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/kernel-version?dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_kernel_version_contract_violation")
        self.assertIn("trust_kernel_version_missing_keys:item", detail["message"])

    async def test_trust_audit_anchor_route_should_return_500_when_contract_validation_fails(
        self,
    ) -> None:
        async def noop_callback(*, cfg: object, case_id: int, payload: dict) -> None:
            return None

        runtime = create_runtime(
            settings=_build_settings(),
            callback_phase_report_impl=noop_callback,
            callback_final_report_impl=noop_callback,
            callback_phase_failed_impl=noop_callback,
            callback_final_failed_impl=noop_callback,
        )
        app = self._create_app_with_patched_trust_contract(
            runtime,
            "validate_trust_audit_anchor_contract",
            "trust_audit_anchor_missing_keys:item",
        )
        case_id = _unique_case_id(8108)
        phase_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/phase/dispatch",
            payload=_build_phase_request(
                case_id=case_id,
                idempotency_key=f"phase:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(phase_resp.status_code, 200)
        final_resp = await self._post_json(
            app=app,
            path="/internal/judge/v3/final/dispatch",
            payload=_build_final_request(
                case_id=case_id,
                idempotency_key=f"final:{case_id}",
                judge_policy_version="v3-default",
            ).model_dump(mode="json"),
            internal_key=runtime.settings.ai_internal_key,
        )
        self.assertEqual(final_resp.status_code, 200)

        resp = await self._get(
            app=app,
            path=f"/internal/judge/cases/{case_id}/trust/audit-anchor?dispatch_type=final",
            internal_key=runtime.settings.ai_internal_key,
        )

        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertEqual(detail["code"], "trust_audit_anchor_contract_violation")
        self.assertIn("trust_audit_anchor_missing_keys:item", detail["message"])


if __name__ == "__main__":
    unittest.main()
