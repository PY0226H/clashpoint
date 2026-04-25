from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.applications.trust_ops_views import build_public_trust_verify_payload
from app.applications.trust_phasea import build_audit_anchor_export
from app.applications.trust_read_routes import (
    TrustReadRouteError,
    build_trust_attestation_verify_payload,
    build_trust_audit_anchor_route_payload,
    build_trust_item_route_payload,
    build_trust_phasea_bundle_for_case,
    build_trust_public_verify_bundle_payload,
    build_trust_public_verify_route_payload,
    build_trust_registry_snapshot_from_bundle,
    build_trust_report_context_from_receipt,
    build_validated_trust_item_route_payload,
    choose_trust_read_dispatch_receipt,
    choose_trust_read_registry_snapshot,
    normalize_trust_read_dispatch_type,
    resolve_trust_report_context_for_case,
    write_trust_registry_snapshot_for_report,
)
from app.domain.trust import TrustRegistrySnapshot
from app.infra.artifacts import LocalArtifactStore


@dataclass
class _DummyReceipt:
    request: dict[str, Any] | None
    response: dict[str, Any] | None
    trace_id: str | None


@dataclass
class _DummyWorkflowJob:
    status: str


def _build_registry_snapshot(
    *,
    case_id: int,
    dispatch_type: str = "final",
    trace_id: str = "trace-registry",
) -> TrustRegistrySnapshot:
    component_hashes = {
        "caseCommitmentHash": f"commit-{trace_id}",
        "verdictAttestationHash": f"attest-{trace_id}",
        "challengeReviewHash": f"challenge-{trace_id}",
        "kernelVersionHash": f"kernel-{trace_id}",
        "auditAnchorHash": f"anchor-{trace_id}",
    }
    return TrustRegistrySnapshot(
        case_id=case_id,
        dispatch_type=dispatch_type,
        trace_id=trace_id,
        case_commitment={
            "version": "trust-phaseA-case-commitment-v1",
            "caseId": case_id,
            "dispatchType": dispatch_type,
            "traceId": trace_id,
            "requestHash": "request-hash",
            "workflowHash": "workflow-hash",
            "reportHash": "report-hash",
            "attestationCommitmentHash": "att-hash",
            "commitmentHash": component_hashes["caseCommitmentHash"],
        },
        verdict_attestation={
            "version": "trust-phaseA-verdict-attestation-v1",
            "caseId": case_id,
            "dispatchType": dispatch_type,
            "traceId": trace_id,
            "registryHash": component_hashes["verdictAttestationHash"],
            "verified": True,
            "mismatchComponents": [],
        },
        challenge_review={
            "version": "trust-phaseB-challenge-review-v1",
            "caseId": case_id,
            "traceId": trace_id,
            "registryHash": component_hashes["challengeReviewHash"],
            "challengeState": "not_challenged",
            "totalChallenges": 0,
        },
        kernel_version={
            "version": "trust-phaseA-kernel-version-v1",
            "caseId": case_id,
            "traceId": trace_id,
            "registryHash": component_hashes["kernelVersionHash"],
            "kernelHash": "kernel-vector-hash",
        },
        audit_anchor={
            "version": "trust-phaseA-audit-anchor-v1",
            "caseId": case_id,
            "dispatchType": dispatch_type,
            "traceId": trace_id,
            "anchorHash": component_hashes["auditAnchorHash"],
            "componentHashes": component_hashes,
        },
        public_verify={
            "caseId": case_id,
            "dispatchType": dispatch_type,
            "traceId": trace_id,
            "verifyPayload": {
                "caseCommitment": {"commitmentHash": component_hashes["caseCommitmentHash"]},
                "verdictAttestation": {
                    "registryHash": component_hashes["verdictAttestationHash"],
                    "verified": True,
                },
                "challengeReview": {
                    "registryHash": component_hashes["challengeReviewHash"],
                    "challengeState": "not_challenged",
                },
                "kernelVersion": {"registryHash": component_hashes["kernelVersionHash"]},
                "auditAnchor": {"anchorHash": component_hashes["auditAnchorHash"]},
            },
        },
        component_hashes=component_hashes,
    )


class TrustReadRoutesTests(unittest.TestCase):
    def test_normalize_trust_read_dispatch_type_should_validate_values(self) -> None:
        self.assertEqual(normalize_trust_read_dispatch_type("auto"), "auto")
        self.assertEqual(normalize_trust_read_dispatch_type(" FINAL "), "final")
        self.assertEqual(normalize_trust_read_dispatch_type("phase"), "phase")
        with self.assertRaises(ValueError) as ctx:
            normalize_trust_read_dispatch_type("unknown")
        self.assertEqual(str(ctx.exception), "invalid_dispatch_type")

    def test_choose_trust_read_dispatch_receipt_should_follow_auto_priority(self) -> None:
        final_receipt = _DummyReceipt(request={}, response={}, trace_id="trace-final")
        phase_receipt = _DummyReceipt(request={}, response={}, trace_id="trace-phase")
        dispatch_type, chosen = choose_trust_read_dispatch_receipt(
            dispatch_type="auto",
            final_receipt=final_receipt,
            phase_receipt=phase_receipt,
        )
        self.assertEqual(dispatch_type, "final")
        self.assertIs(chosen, final_receipt)

        dispatch_type, chosen = choose_trust_read_dispatch_receipt(
            dispatch_type="auto",
            final_receipt=None,
            phase_receipt=phase_receipt,
        )
        self.assertEqual(dispatch_type, "phase")
        self.assertIs(chosen, phase_receipt)

    def test_build_trust_report_context_from_receipt_should_parse_snapshots(self) -> None:
        receipt = _DummyReceipt(
            request={"traceId": "trace-request"},
            response={"reportPayload": {"winner": "pro", "judgeTrace": {"traceId": "trace-judge"}}},
            trace_id="trace-receipt",
        )
        payload = build_trust_report_context_from_receipt(
            dispatch_type="final",
            receipt=receipt,
        )
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["traceId"], "trace-receipt")
        self.assertEqual(payload["requestSnapshot"], {"traceId": "trace-request"})
        self.assertEqual(payload["reportPayload"]["winner"], "pro")
        self.assertIs(payload["receipt"], receipt)

    def test_build_trust_report_context_from_receipt_should_fail_on_missing_report(self) -> None:
        receipt = _DummyReceipt(
            request={"traceId": "trace-request"},
            response={},
            trace_id="trace-receipt",
        )
        with self.assertRaises(ValueError) as ctx:
            build_trust_report_context_from_receipt(
                dispatch_type="phase",
                receipt=receipt,
            )
        self.assertEqual(str(ctx.exception), "trust_report_payload_missing")

    def test_route_payload_builders_should_keep_trust_shape(self) -> None:
        item = {"version": "v1", "traceId": "trace-item"}
        verify_payload = {"commitment": {"hash": "h1"}}
        item_payload = build_trust_item_route_payload(
            case_id=1001,
            dispatch_type="final",
            trace_id="trace-final-1001",
            item=item,
        )
        public_payload = build_trust_public_verify_route_payload(
            case_id=1001,
            dispatch_type="final",
            trace_id="trace-final-1001",
            verify_payload=verify_payload,
        )
        self.assertEqual(item_payload["caseId"], 1001)
        self.assertEqual(item_payload["dispatchType"], "final")
        self.assertEqual(item_payload["traceId"], "trace-final-1001")
        self.assertEqual(item_payload["item"], item)
        self.assertIsNot(item_payload["item"], item)
        self.assertEqual(public_payload["verifyPayload"], verify_payload)
        self.assertIsNot(public_payload["verifyPayload"], verify_payload)
        self.assertEqual(public_payload["verificationVersion"], "trust-public-verification-v1")
        self.assertEqual(
            public_payload["verificationRequest"]["requestKey"],
            "case:1001:dispatch:final:trace:trace-final-1001:registry:trust-registry-v1:verification:trust-public-verification-v1",
        )
        self.assertTrue(public_payload["proxyRequired"])
        self.assertFalse(public_payload["cacheProfile"]["cacheable"])
        self.assertEqual(public_payload["cacheProfile"]["ttlSeconds"], 0)
        self.assertEqual(
            public_payload["cacheProfile"]["cacheKey"],
            public_payload["verificationRequest"]["requestKey"],
        )
        self.assertEqual(
            public_payload["verificationReadiness"]["status"],
            "artifact_manifest_pending",
        )
        self.assertFalse(public_payload["verificationReadiness"]["externalizable"])
        self.assertEqual(public_payload["visibilityContract"]["layer"], "public")
        self.assertEqual(
            public_payload["visibilityContract"]["payloadLayer"],
            "commitment_hashes_only",
        )
        self.assertTrue(public_payload["visibilityContract"]["chatProxyRequired"])
        self.assertFalse(public_payload["visibilityContract"]["directAiServiceAccessAllowed"])

    def test_resolve_trust_report_context_for_case_should_choose_final_on_auto(self) -> None:
        final_receipt = _DummyReceipt(
            request={"traceId": "trace-final-request"},
            response={"reportPayload": {"winner": "pro"}},
            trace_id="trace-final",
        )
        phase_receipt = _DummyReceipt(
            request={"traceId": "trace-phase-request"},
            response={"reportPayload": {"winner": "con"}},
            trace_id="trace-phase",
        )

        async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int) -> Any:
            self.assertEqual(job_id, 2001)
            if dispatch_type == "final":
                return final_receipt
            if dispatch_type == "phase":
                return phase_receipt
            return None

        payload = asyncio.run(
            resolve_trust_report_context_for_case(
                case_id=2001,
                dispatch_type="auto",
                get_dispatch_receipt=_get_dispatch_receipt,
                not_found_detail="trust_receipt_not_found",
                missing_report_detail="trust_report_payload_missing",
            )
        )
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["traceId"], "trace-final")
        self.assertEqual(payload["reportPayload"]["winner"], "pro")

    def test_resolve_trust_report_context_for_case_should_raise_route_error(self) -> None:
        async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int) -> Any:
            del dispatch_type, job_id
            return None

        with self.assertRaises(TrustReadRouteError) as ctx:
            asyncio.run(
                resolve_trust_report_context_for_case(
                    case_id=2002,
                    dispatch_type="invalid",
                    get_dispatch_receipt=_get_dispatch_receipt,
                    not_found_detail="trust_receipt_not_found",
                    missing_report_detail="trust_report_payload_missing",
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "invalid_dispatch_type")

    def test_build_trust_phasea_bundle_for_case_should_return_bundle_shape(self) -> None:
        final_receipt = _DummyReceipt(
            request={"traceId": "trace-final-request"},
            response={
                "reportPayload": {
                    "winner": "pro",
                    "proScore": 55.0,
                    "conScore": 45.0,
                    "trustAttestation": {
                        "commitmentHash": "c1",
                        "verdictHash": "v1",
                        "auditHash": "a1",
                    },
                }
            },
            trace_id="trace-final",
        )

        async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int) -> Any:
            self.assertEqual(job_id, 2003)
            if dispatch_type == "final":
                return final_receipt
            if dispatch_type == "phase":
                return None
            return None

        async def _get_workflow_job(*, job_id: int) -> Any:
            self.assertEqual(job_id, 2003)
            return _DummyWorkflowJob(status="reported")

        async def _list_workflow_events(*, job_id: int) -> list[Any]:
            self.assertEqual(job_id, 2003)
            return []

        async def _list_audit_alerts(*, job_id: int, status: str | None, limit: int) -> list[Any]:
            self.assertEqual(job_id, 2003)
            self.assertIsNone(status)
            self.assertEqual(limit, 200)
            return []

        def _serialize_workflow_job(job: _DummyWorkflowJob) -> dict[str, Any]:
            return {"status": job.status}

        payload = asyncio.run(
            build_trust_phasea_bundle_for_case(
                case_id=2003,
                dispatch_type="auto",
                get_dispatch_receipt=_get_dispatch_receipt,
                get_workflow_job=_get_workflow_job,
                list_workflow_events=_list_workflow_events,
                list_audit_alerts=_list_audit_alerts,
                serialize_workflow_job=_serialize_workflow_job,
                provider="mock",
            )
        )
        self.assertEqual(payload["context"]["dispatchType"], "final")
        self.assertEqual(payload["context"]["traceId"], "trace-final")
        self.assertIn("commitment", payload)
        self.assertIn("verdictAttestation", payload)
        self.assertIn("challengeReview", payload)
        self.assertIn("kernelVersion", payload)

    def test_build_trust_phasea_bundle_for_case_should_prefer_registry_snapshot(self) -> None:
        snapshot = _build_registry_snapshot(
            case_id=2010,
            dispatch_type="final",
            trace_id="trace-registry-2010",
        )
        receipt_calls: list[str] = []

        async def _get_trust_registry_snapshot(*, case_id: int, dispatch_type: str) -> Any:
            self.assertEqual(case_id, 2010)
            if dispatch_type == "final":
                return snapshot
            return None

        async def _get_dispatch_receipt(**kwargs: Any) -> Any:
            receipt_calls.append(str(kwargs.get("dispatch_type")))
            return None

        payload = asyncio.run(
            build_trust_phasea_bundle_for_case(
                case_id=2010,
                dispatch_type="auto",
                get_dispatch_receipt=_get_dispatch_receipt,
                get_workflow_job=lambda **_kwargs: asyncio.sleep(0),
                list_workflow_events=lambda **_kwargs: asyncio.sleep(0, result=[]),
                list_audit_alerts=lambda **_kwargs: asyncio.sleep(0, result=[]),
                serialize_workflow_job=lambda _job: {},
                provider="mock",
                get_trust_registry_snapshot=_get_trust_registry_snapshot,
            )
        )

        self.assertEqual(receipt_calls, [])
        self.assertEqual(payload["context"]["source"], "trust_registry")
        self.assertEqual(payload["context"]["registryVersion"], "trust-registry-v1")
        self.assertEqual(payload["commitment"]["commitmentHash"], "commit-trace-registry-2010")

    def test_choose_trust_read_registry_snapshot_should_follow_auto_priority(self) -> None:
        final_snapshot = _build_registry_snapshot(case_id=2011, trace_id="trace-final")
        phase_snapshot = _build_registry_snapshot(
            case_id=2011,
            dispatch_type="phase",
            trace_id="trace-phase",
        )

        async def _get_trust_registry_snapshot(*, case_id: int, dispatch_type: str) -> Any:
            self.assertEqual(case_id, 2011)
            return final_snapshot if dispatch_type == "final" else phase_snapshot

        dispatch_type, chosen = asyncio.run(
            choose_trust_read_registry_snapshot(
                dispatch_type="auto",
                case_id=2011,
                get_trust_registry_snapshot=_get_trust_registry_snapshot,
            )
        )
        self.assertEqual(dispatch_type, "final")
        self.assertIs(chosen, final_snapshot)

    def test_build_trust_attestation_verify_payload_should_return_verify_bundle(self) -> None:
        final_receipt = _DummyReceipt(
            request={"traceId": "trace-final-request"},
            response={"reportPayload": {"winner": "pro"}},
            trace_id="trace-final-2007",
        )

        async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int) -> Any:
            self.assertEqual(job_id, 2007)
            if dispatch_type == "final":
                return final_receipt
            if dispatch_type == "phase":
                return None
            return None

        def _verify_report_attestation(
            *,
            report_payload: dict[str, Any],
            dispatch_type: str,
        ) -> dict[str, Any]:
            self.assertEqual(dispatch_type, "final")
            self.assertEqual(report_payload["winner"], "pro")
            return {
                "verified": True,
                "reason": "ok",
                "mismatchComponents": [],
            }

        payload = asyncio.run(
            build_trust_attestation_verify_payload(
                case_id=2007,
                dispatch_type="auto",
                get_dispatch_receipt=_get_dispatch_receipt,
                verify_report_attestation=_verify_report_attestation,
            )
        )

        self.assertEqual(payload["caseId"], 2007)
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["traceId"], "trace-final-2007")
        self.assertTrue(payload["verified"])
        self.assertEqual(payload["reason"], "ok")

    def test_build_trust_attestation_verify_payload_should_raise_route_error(self) -> None:
        async def _get_dispatch_receipt(*, dispatch_type: str, job_id: int) -> Any:
            del dispatch_type, job_id
            return None

        with self.assertRaises(TrustReadRouteError) as ctx:
            asyncio.run(
                build_trust_attestation_verify_payload(
                    case_id=2008,
                    dispatch_type="auto",
                    get_dispatch_receipt=_get_dispatch_receipt,
                    verify_report_attestation=lambda **kwargs: kwargs,
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "attestation_receipt_not_found")

    def test_build_validated_trust_item_route_payload_should_raise_route_error(self) -> None:
        bundle = {
            "context": {
                "dispatchType": "final",
                "traceId": "trace-validated",
            },
            "commitment": {"version": "v1"},
        }

        def _validate_contract(_payload: dict[str, Any]) -> None:
            raise ValueError("commitment_missing_keys:item")

        with self.assertRaises(TrustReadRouteError) as ctx:
            build_validated_trust_item_route_payload(
                case_id=2004,
                bundle=bundle,
                item_key="commitment",
                validate_contract=_validate_contract,
                violation_code="trust_commitment_contract_violation",
            )
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(
            ctx.exception.detail["code"],
            "trust_commitment_contract_violation",
        )
        self.assertIn("commitment_missing_keys:item", ctx.exception.detail["message"])

    def test_build_trust_audit_anchor_route_payload_should_return_validated_payload(self) -> None:
        bundle = {
            "context": {"dispatchType": "final", "traceId": "trace-anchor"},
            "commitment": {"version": "v1"},
            "verdictAttestation": {"version": "v1"},
            "challengeReview": {"version": "v1"},
            "kernelVersion": {"version": "v1"},
        }

        def _build_audit_anchor_export(**kwargs: Any) -> dict[str, Any]:
            self.assertEqual(kwargs["case_id"], 2005)
            self.assertEqual(kwargs["dispatch_type"], "final")
            self.assertEqual(kwargs["trace_id"], "trace-anchor")
            self.assertTrue(kwargs["include_payload"])
            return {"anchorHash": "anchor-2005"}

        def _validate_contract(payload: dict[str, Any]) -> None:
            self.assertEqual(payload["item"]["anchorHash"], "anchor-2005")

        payload = build_trust_audit_anchor_route_payload(
            case_id=2005,
            bundle=bundle,
            include_payload=True,
            build_audit_anchor_export=_build_audit_anchor_export,
            validate_contract=_validate_contract,
            violation_code="trust_audit_anchor_contract_violation",
        )
        self.assertEqual(payload["caseId"], 2005)
        self.assertEqual(payload["dispatchType"], "final")
        self.assertEqual(payload["traceId"], "trace-anchor")

    def test_build_trust_public_verify_bundle_payload_should_validate_contract(self) -> None:
        bundle = {
            "context": {"dispatchType": "final", "traceId": "trace-verify"},
            "commitment": {"version": "v1"},
            "verdictAttestation": {"version": "v1"},
            "challengeReview": {"version": "v1"},
            "kernelVersion": {"version": "v1"},
        }

        def _build_audit_anchor_export(**kwargs: Any) -> dict[str, Any]:
            self.assertFalse(kwargs["include_payload"])
            return {"anchorHash": "anchor-2006"}

        def _build_public_verify_payload(**kwargs: Any) -> dict[str, Any]:
            return {
                "caseCommitment": kwargs["commitment"],
                "auditAnchor": kwargs["audit_anchor"],
            }

        def _validate_contract(_payload: dict[str, Any]) -> None:
            raise ValueError("public_verify_missing_keys:verifyPayload")

        with self.assertRaises(TrustReadRouteError) as ctx:
            build_trust_public_verify_bundle_payload(
                case_id=2006,
                bundle=bundle,
                build_audit_anchor_export=_build_audit_anchor_export,
                build_public_verify_payload=_build_public_verify_payload,
                validate_contract=_validate_contract,
                violation_code="trust_public_verify_contract_violation",
            )
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(
            ctx.exception.detail["code"],
            "trust_public_verify_contract_violation",
        )
        self.assertIn("public_verify_missing_keys:verifyPayload", ctx.exception.detail["message"])

    def test_build_trust_registry_snapshot_from_bundle_should_include_public_verify(self) -> None:
        bundle = {
            "context": {"dispatchType": "final", "traceId": "trace-registry"},
            "commitment": {
                "version": "trust-phaseA-case-commitment-v1",
                "caseId": 2012,
                "dispatchType": "final",
                "traceId": "trace-registry",
                "requestHash": "request-hash",
                "workflowHash": "workflow-hash",
                "reportHash": "report-hash",
                "attestationCommitmentHash": "att-hash",
                "commitmentHash": "commit-hash",
            },
            "verdictAttestation": {
                "version": "trust-phaseA-verdict-attestation-v1",
                "caseId": 2012,
                "dispatchType": "final",
                "traceId": "trace-registry",
                "registryHash": "attest-hash",
                "verified": True,
                "mismatchComponents": [],
            },
            "challengeReview": {
                "version": "trust-phaseB-challenge-review-v1",
                "caseId": 2012,
                "traceId": "trace-registry",
                "registryHash": "challenge-hash",
                "challengeState": "not_challenged",
                "totalChallenges": 0,
            },
            "kernelVersion": {
                "version": "trust-phaseA-kernel-version-v1",
                "caseId": 2012,
                "traceId": "trace-registry",
                "registryHash": "kernel-hash",
                "kernelHash": "kernel-vector-hash",
            },
        }

        def _build_audit_anchor_export(**kwargs: Any) -> dict[str, Any]:
            return {
                "caseId": kwargs["case_id"],
                "dispatchType": kwargs["dispatch_type"],
                "traceId": kwargs["trace_id"],
                "anchorHash": "anchor-hash",
                "componentHashes": {
                    "caseCommitmentHash": "commit-hash",
                    "verdictAttestationHash": "attest-hash",
                    "challengeReviewHash": "challenge-hash",
                    "kernelVersionHash": "kernel-hash",
                },
            }

        def _build_public_verify_payload(**kwargs: Any) -> dict[str, Any]:
            return {
                "caseCommitment": kwargs["commitment"],
                "verdictAttestation": kwargs["verdict_attestation"],
                "challengeReview": kwargs["challenge_review"],
                "kernelVersion": kwargs["kernel_version"],
                "auditAnchor": kwargs["audit_anchor"],
            }

        snapshot = build_trust_registry_snapshot_from_bundle(
            case_id=2012,
            bundle=bundle,
            build_audit_anchor_export=_build_audit_anchor_export,
            build_public_verify_payload=_build_public_verify_payload,
        )

        self.assertEqual(snapshot.dispatch_type, "final")
        self.assertEqual(snapshot.public_verify["verifyPayload"]["auditAnchor"]["anchorHash"], "anchor-hash")
        self.assertEqual(snapshot.component_hashes["auditAnchorHash"], "anchor-hash")

    def test_write_trust_registry_snapshot_for_report_should_upsert_snapshot(self) -> None:
        written: list[TrustRegistrySnapshot] = []

        async def _upsert_trust_registry_snapshot(*, snapshot: TrustRegistrySnapshot) -> TrustRegistrySnapshot:
            written.append(snapshot)
            return snapshot

        snapshot = asyncio.run(
            write_trust_registry_snapshot_for_report(
                case_id=2013,
                dispatch_type="final",
                trace_id="trace-write-through",
                request_snapshot={"caseId": 2013},
                report_payload={
                    "winner": "pro",
                    "proScore": 66,
                    "conScore": 60,
                    "reviewRequired": False,
                    "trustAttestation": {"commitmentHash": "att-commit"},
                },
                workflow_snapshot={"status": "callback_reported"},
                workflow_status="callback_reported",
                workflow_events=[],
                alerts=[],
                provider="mock",
                upsert_trust_registry_snapshot=_upsert_trust_registry_snapshot,
                build_audit_anchor_export=lambda **kwargs: {
                    "caseId": kwargs["case_id"],
                    "dispatchType": kwargs["dispatch_type"],
                    "traceId": kwargs["trace_id"],
                    "anchorHash": "anchor-write",
                    "componentHashes": {
                        "caseCommitmentHash": kwargs["case_commitment"]["commitmentHash"],
                        "verdictAttestationHash": kwargs["verdict_attestation"]["registryHash"],
                        "challengeReviewHash": kwargs["challenge_review"]["registryHash"],
                        "kernelVersionHash": kwargs["kernel_version"]["registryHash"],
                    },
                },
                build_public_verify_payload=lambda **kwargs: {
                    "caseCommitment": kwargs["commitment"],
                    "verdictAttestation": kwargs["verdict_attestation"],
                    "challengeReview": kwargs["challenge_review"],
                    "kernelVersion": kwargs["kernel_version"],
                    "auditAnchor": kwargs["audit_anchor"],
                },
            )
        )

        self.assertEqual(len(written), 1)
        self.assertIs(snapshot, written[0])
        self.assertEqual(snapshot.trace_id, "trace-write-through")
        self.assertEqual(snapshot.public_verify["caseId"], 2013)

    def test_write_trust_registry_snapshot_for_report_should_attach_artifact_manifest(
        self,
    ) -> None:
        written: list[TrustRegistrySnapshot] = []

        async def _upsert_trust_registry_snapshot(
            *,
            snapshot: TrustRegistrySnapshot,
        ) -> TrustRegistrySnapshot:
            written.append(snapshot)
            return snapshot

        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_store = LocalArtifactStore(root_dir=Path(tmpdir) / "artifacts")
            snapshot = asyncio.run(
                write_trust_registry_snapshot_for_report(
                    case_id=2014,
                    dispatch_type="final",
                    trace_id="trace-artifact-anchor",
                    request_snapshot={
                        "caseId": 2014,
                        "message_start_id": 1,
                        "message_end_id": 2,
                        "message_count": 2,
                        "messages": [
                            {"message_id": 1, "side": "pro", "content": "hidden pro"},
                            {"message_id": 2, "side": "con", "content": "hidden con"},
                        ],
                    },
                    report_payload={
                        "winner": "pro",
                        "proScore": 66,
                        "conScore": 60,
                        "reviewRequired": False,
                        "trustAttestation": {"commitmentHash": "att-commit"},
                        "evidenceLedger": {"entries": [{"id": "e1", "content": "hidden"}]},
                    },
                    workflow_snapshot={"status": "callback_reported"},
                    workflow_status="callback_reported",
                    workflow_events=[],
                    alerts=[],
                    provider="mock",
                    upsert_trust_registry_snapshot=_upsert_trust_registry_snapshot,
                    build_audit_anchor_export=build_audit_anchor_export,
                    build_public_verify_payload=build_public_trust_verify_payload,
                    artifact_store=artifact_store,
                )
            )

        self.assertEqual(len(written), 1)
        audit_anchor = snapshot.audit_anchor
        self.assertEqual(audit_anchor["anchorStatus"], "artifact_ready")
        self.assertIsNotNone(audit_anchor["anchorHash"])
        self.assertEqual(
            audit_anchor["componentHashes"]["artifactManifestHash"],
            audit_anchor["artifactManifest"]["manifestHash"],
        )
        self.assertEqual(
            snapshot.public_verify["verifyPayload"]["auditAnchor"]["anchorHash"],
            audit_anchor["anchorHash"],
        )
        self.assertIn("artifactManifestHash", snapshot.component_hashes)
        manifest_repr = str(audit_anchor["artifactManifest"])
        self.assertNotIn("hidden pro", manifest_repr)
        self.assertNotIn("hidden con", manifest_repr)
        self.assertNotIn("hidden", manifest_repr)


if __name__ == "__main__":
    unittest.main()
