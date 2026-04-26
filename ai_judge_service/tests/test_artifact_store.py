from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from app.applications.artifact_pack import (
    build_artifact_store_healthcheck_payload,
    build_artifact_store_readiness_payload,
    write_case_artifact_pack,
    write_release_readiness_artifact,
    write_trust_audit_artifact_pack,
)
from app.domain.artifacts import ArtifactRef
from app.infra.artifacts import LocalArtifactStore, S3CompatibleArtifactStore
from app.settings import load_settings
from app.wiring import build_artifact_store


class _FakeS3Client:
    def __init__(
        self,
        *,
        fail_on_put: bool = False,
        fail_on_head: bool = False,
        fail_on_get: bool = False,
        corrupt_get: bool = False,
    ) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.metadata: dict[tuple[str, str], dict[str, str]] = {}
        self.fail_on_put = bool(fail_on_put)
        self.fail_on_head = bool(fail_on_head)
        self.fail_on_get = bool(fail_on_get)
        self.corrupt_get = bool(corrupt_get)

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
        Metadata: dict[str, str],
    ) -> None:
        del ContentType
        if self.fail_on_put:
            raise RuntimeError("s3_put_failed")
        self.objects[(Bucket, Key)] = Body
        self.metadata[(Bucket, Key)] = dict(Metadata)

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, BytesIO]:
        if self.fail_on_get:
            raise RuntimeError("s3_get_failed")
        if self.corrupt_get:
            return {
                "Body": BytesIO(
                    b'{"probe":"artifact_store_healthcheck","version":"tampered"}'
                )
            }
        return {"Body": BytesIO(self.objects[(Bucket, Key)])}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        if self.fail_on_head:
            raise RuntimeError("s3_head_failed")
        if (Bucket, Key) not in self.objects:
            raise KeyError(Key)
        return {}


class _ReadinessOnlyStore:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = dict(payload)

    def readiness_payload(self) -> dict[str, object]:
        return dict(self._payload)


class ArtifactStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._root = Path(self._tmpdir.name) / "artifacts" / "ai_judge_service"
        self._store = LocalArtifactStore(root_dir=self._root)

    async def asyncTearDown(self) -> None:
        self._tmpdir.cleanup()

    async def test_local_store_should_put_and_get_redacted_json_ref(self) -> None:
        payload = {
            "version": "transcript-redacted-v1",
            "messageIds": [1, 2],
            "messageDigest": [
                {"messageId": 1, "side": "pro"},
                {"messageId": 2, "side": "con"},
            ],
        }

        ref = await self._store.put_json(
            case_id=9101,
            kind="transcript_snapshot",
            payload=payload,
            dispatch_type="final",
            trace_id="trace-9101",
        )

        self.assertEqual(ref.kind, "transcript_snapshot")
        self.assertEqual(ref.content_type, "application/json")
        self.assertEqual(ref.redaction_level, "redacted")
        self.assertEqual(len(ref.sha256), 64)
        self.assertTrue(ref.uri.startswith("local-artifact://ai_judge_service/"))
        self.assertNotIn(self._tmpdir.name, ref.uri)
        self.assertTrue(await self._store.exists(ref=ref))
        self.assertEqual(await self._store.get_json(ref=ref), payload)

        files = list(self._root.rglob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].resolve().is_relative_to(self._root.resolve()))

    async def test_local_store_should_reject_path_escape_and_uri_namespace_escape(self) -> None:
        with self.assertRaisesRegex(ValueError, "artifact_id_invalid"):
            await self._store.put_json(
                case_id=9102,
                kind="evidence_pack",
                payload={"version": "evidence-v1"},
                artifact_id="../escape",
            )

        ref = await self._store.put_json(
            case_id=9102,
            kind="evidence_pack",
            payload={"version": "evidence-v1"},
        )
        bad_ref = ArtifactRef(
            artifact_id=ref.artifact_id,
            kind=ref.kind,
            uri=ref.uri.replace("ai_judge_service", "other_namespace"),
            sha256=ref.sha256,
        )
        with self.assertRaisesRegex(ValueError, "artifact_uri_namespace_invalid"):
            await self._store.get_json(ref=bad_ref)

    async def test_local_store_should_reject_sensitive_payload_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "artifact_payload_forbidden_keys"):
            await self._store.put_json(
                case_id=9103,
                kind="audit_pack",
                payload={"version": "audit-v1", "rawPrompt": "internal prompt"},
                redaction_level="ops",
            )

    async def test_case_artifact_pack_should_write_refs_and_manifest(self) -> None:
        pack = await write_case_artifact_pack(
            artifact_store=self._store,
            case_id=9104,
            dispatch_type="final",
            trace_id="trace-9104",
            transcript_snapshot={"version": "transcript-v1", "messageIds": [1, 2]},
            evidence_pack={"version": "evidence-v1", "entries": [{"id": "e1"}]},
            replay_snapshot={"version": "replay-v1", "winner": "pro"},
            audit_pack={"version": "audit-v1", "alerts": [{"type": "review_gap"}]},
            metadata={"source": "unit-test"},
        )

        payload = pack.to_payload()
        self.assertEqual(
            [ref["kind"] for ref in payload["refs"]],
            [
                "transcript_snapshot",
                "evidence_pack",
                "replay_snapshot",
                "audit_pack",
            ],
        )
        self.assertEqual(payload["manifest"]["artifactCount"], 4)
        self.assertEqual(payload["manifest"]["metadata"]["source"], "unit-test")
        self.assertEqual(payload["manifest"]["metadata"]["storageMode"], "local_reference")
        self.assertEqual(
            payload["manifest"]["metadata"]["artifactStore"],
            {
                "provider": "local",
                "status": "local_reference",
                "productionReady": False,
                "uriScheme": "local-artifact",
            },
        )
        self.assertEqual(len(payload["manifest"]["manifestHash"]), 64)
        self.assertEqual(
            payload["manifest"]["artifactHashes"]["audit_pack"],
            payload["refs"][3]["sha256"],
        )
        for ref in pack.refs:
            self.assertTrue(await self._store.exists(ref=ref))

    async def test_trust_audit_artifact_pack_should_redact_evidence_ref_payloads(self) -> None:
        pack = await write_trust_audit_artifact_pack(
            artifact_store=self._store,
            case_id=9105,
            dispatch_type="final",
            trace_id="trace-9105",
            request_snapshot={
                "message_start_id": 1,
                "message_end_id": 2,
                "message_count": 2,
                "messages": [{"message_id": 1, "side": "pro", "content": "raw message"}],
            },
            report_payload={
                "winner": "pro",
                "verdictEvidenceRefs": [
                    {
                        "evidenceId": "ev-1",
                        "side": "pro",
                        "type": "agent2_hit",
                        "item": "raw decisive quote",
                        "content": "raw ref content",
                    }
                ],
                "evidenceLedger": {"entries": [{"id": "ev-1", "content": "raw evidence"}]},
            },
            workflow_snapshot={"status": "callback_reported"},
            commitment={"commitmentHash": "case-hash", "version": "v1"},
            verdict_attestation={"registryHash": "verdict-hash", "version": "v1"},
            challenge_review={"registryHash": "challenge-hash", "version": "v1"},
            kernel_version={"registryHash": "kernel-hash", "version": "v1"},
        )

        evidence_ref = next(ref for ref in pack.refs if ref.kind == "evidence_pack")
        evidence_payload = await self._store.get_json(ref=evidence_ref)
        evidence_repr = str(evidence_payload)
        self.assertNotIn("raw decisive quote", evidence_repr)
        self.assertNotIn("raw ref content", evidence_repr)
        self.assertNotIn("raw evidence", evidence_repr)
        self.assertEqual(
            evidence_payload["verdictEvidenceRefs"][0]["itemHash"],
            "eb817ecdd6e8090037d4981b1e46084d977ae54ae80766593e165921cb33dbc2",
        )

    async def test_release_readiness_artifact_should_write_summary_without_storage_paths(
        self,
    ) -> None:
        export = await write_release_readiness_artifact(
            artifact_store=self._store,
            case_id=9106,
            dispatch_type="final",
            trace_id="trace-release-9106",
            release_readiness_evidence={
                "evidenceVersion": "policy-release-readiness-evidence-v1",
                "generatedAt": "2026-04-26T00:00:00Z",
                "policyVersion": "policy-v3-local",
                "decision": "env_blocked",
                "decisionCode": "registry_release_gate_env_blocked",
                "componentStatuses": [
                    {
                        "component": "fairnessBenchmark",
                        "status": "env_blocked",
                        "code": "registry_release_gate_fairness_benchmark_local_reference_only",
                    }
                ],
                "reasonCodes": [
                    "registry_release_gate_fairness_benchmark_local_reference_only"
                ],
                "envBlockedComponents": ["fairnessBenchmark"],
                "artifactRefs": ["internal-release-manifest"],
                "realEnvEvidenceStatus": {
                    "status": "env_blocked",
                    "source": "release_gate",
                    "realEnvEvidenceAvailable": False,
                },
            },
        )

        self.assertEqual(export["artifact"]["version"], "release-readiness-artifact-v1")
        self.assertEqual(export["summary"]["artifactKind"], "release_readiness")
        self.assertEqual(len(export["summary"]["manifestHash"]), 64)
        self.assertEqual(export["summary"]["storageMode"], "local_reference")
        self.assertEqual(export["summary"]["envBlockedComponents"], ["fairnessBenchmark"])
        self.assertFalse(export["summary"]["redactionContract"]["storageUriVisible"])
        summary_text = str(export["summary"])
        self.assertNotIn(self._tmpdir.name, summary_text)
        self.assertNotIn(str(self._root), summary_text)
        self.assertNotIn("local-artifact://", summary_text)
        ref = ArtifactRef.from_payload(export["ref"])
        self.assertTrue(await self._store.exists(ref=ref))

    async def test_release_readiness_artifact_should_reject_storage_metadata_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "artifact_payload_forbidden_keys"):
            await self._store.put_json(
                case_id=9107,
                kind="release_readiness",
                payload={
                    "version": "release-readiness-artifact-v1",
                    "evidenceVersion": "policy-release-readiness-evidence-v1",
                    "decision": "allowed",
                    "componentStatuses": [],
                    "bucket": "must-not-enter-artifact-payload",
                },
            )

    async def test_s3_compatible_store_should_put_and_get_json_ref_without_secret_uri(
        self,
    ) -> None:
        client = _FakeS3Client()
        store = S3CompatibleArtifactStore(
            bucket="judge-artifacts",
            prefix="ai/judge",
            client=client,
            force_path_style=True,
        )
        payload = {"version": "replay-v1", "winner": "draw"}

        ref = await store.put_json(
            case_id=9201,
            kind="replay_snapshot",
            payload=payload,
            dispatch_type="final",
            trace_id="trace-9201",
        )

        self.assertEqual(ref.kind, "replay_snapshot")
        self.assertTrue(ref.uri.startswith("s3://judge-artifacts/ai/judge/"))
        self.assertNotIn("secret", ref.uri.lower())
        self.assertTrue(await store.exists(ref=ref))
        self.assertEqual(await store.get_json(ref=ref), payload)
        manifest = store.build_manifest(
            case_id=9201,
            dispatch_type="final",
            trace_id="trace-9201",
            refs=[ref],
            metadata={"artifactStore": store.readiness_payload(), "storageMode": "production"},
        )
        manifest_payload = manifest.to_payload()
        self.assertEqual(
            manifest_payload["metadata"]["artifactStore"]["provider"],
            "s3_compatible",
        )
        self.assertTrue(manifest_payload["metadata"]["artifactStore"]["productionReady"])
        readiness = manifest_payload["metadata"]["artifactStore"]
        self.assertTrue(readiness["bucketConfigured"])
        self.assertTrue(readiness["prefixConfigured"])
        self.assertFalse(readiness["endpointConfigured"])
        self.assertTrue(readiness["forcePathStyle"])
        self.assertNotIn("judge-artifacts", str(readiness))
        self.assertNotIn("ai/judge", str(readiness))

    async def test_s3_compatible_store_should_reject_wrong_bucket_uri(self) -> None:
        client = _FakeS3Client()
        store = S3CompatibleArtifactStore(
            bucket="judge-artifacts",
            prefix="ai/judge",
            client=client,
        )
        ref = await store.put_json(
            case_id=9202,
            kind="audit_pack",
            payload={"version": "audit-v1"},
        )
        bad_ref = ArtifactRef(
            artifact_id=ref.artifact_id,
            kind=ref.kind,
            uri=ref.uri.replace("judge-artifacts", "other-bucket"),
            sha256=ref.sha256,
        )

        with self.assertRaisesRegex(ValueError, "artifact_uri_bucket_invalid"):
            await store.get_json(ref=bad_ref)

    async def test_case_artifact_pack_should_mark_s3_store_as_production(self) -> None:
        store = S3CompatibleArtifactStore(
            bucket="judge-artifacts",
            prefix="ai/judge",
            client=_FakeS3Client(),
        )
        pack = await write_case_artifact_pack(
            artifact_store=store,
            case_id=9203,
            dispatch_type="final",
            trace_id="trace-9203",
            replay_snapshot={"version": "replay-v1", "winner": "pro"},
        )

        payload = pack.to_payload()
        self.assertEqual(payload["manifest"]["metadata"]["storageMode"], "production")
        self.assertEqual(
            payload["manifest"]["metadata"]["artifactStore"]["provider"],
            "s3_compatible",
        )
        self.assertEqual(
            build_artifact_store_readiness_payload(store)["status"],
            "production_configured",
        )

    async def test_artifact_store_healthcheck_should_keep_local_reference_without_path(
        self,
    ) -> None:
        payload = await build_artifact_store_healthcheck_payload(
            artifact_store=self._store,
            roundtrip_enabled=True,
        )

        self.assertEqual(payload["provider"], "local")
        self.assertEqual(payload["status"], "local_reference")
        self.assertEqual(payload["writeReadRoundtripStatus"], "not_applicable")
        self.assertEqual(payload["lastErrorCode"], "local_provider_not_production")
        self.assertFalse(payload["productionReady"])
        self.assertNotIn(self._tmpdir.name, str(payload))
        self.assertNotIn(str(self._root), str(payload))

    async def test_s3_artifact_store_healthcheck_should_env_block_when_not_enabled(
        self,
    ) -> None:
        client = _FakeS3Client()
        store = S3CompatibleArtifactStore(
            bucket="judge-artifacts",
            prefix="prod/ai-judge",
            client=client,
            endpoint_configured=True,
        )

        payload = await build_artifact_store_healthcheck_payload(
            artifact_store=store,
            roundtrip_enabled=False,
        )

        self.assertEqual(payload["provider"], "s3_compatible")
        self.assertEqual(payload["status"], "env_blocked")
        self.assertEqual(payload["writeReadRoundtripStatus"], "not_enabled")
        self.assertEqual(payload["lastErrorCode"], "artifact_healthcheck_not_enabled")
        self.assertFalse(payload["productionReady"])
        self.assertEqual(client.objects, {})
        self.assertTrue(payload["bucketConfigured"])
        self.assertTrue(payload["prefixConfigured"])
        self.assertTrue(payload["endpointConfigured"])
        self.assertNotIn("judge-artifacts", str(payload))
        self.assertNotIn("prod/ai-judge", str(payload))

    async def test_s3_artifact_store_healthcheck_should_env_block_without_bucket(
        self,
    ) -> None:
        store = _ReadinessOnlyStore(
            {
                "provider": "s3_compatible",
                "uriScheme": "s3",
                "bucketConfigured": False,
                "prefixConfigured": True,
                "endpointConfigured": True,
            }
        )

        payload = await build_artifact_store_healthcheck_payload(
            artifact_store=store,
            roundtrip_enabled=True,
        )

        self.assertEqual(payload["status"], "env_blocked")
        self.assertEqual(payload["writeReadRoundtripStatus"], "configuration_missing")
        self.assertEqual(payload["lastErrorCode"], "artifact_store_bucket_missing")
        self.assertFalse(payload["productionReady"])

    async def test_s3_artifact_store_healthcheck_should_pass_roundtrip_when_enabled(
        self,
    ) -> None:
        store = S3CompatibleArtifactStore(
            bucket="judge-artifacts",
            prefix="prod/ai-judge",
            client=_FakeS3Client(),
            endpoint_configured=True,
        )

        payload = await build_artifact_store_healthcheck_payload(
            artifact_store=store,
            roundtrip_enabled=True,
        )

        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["writeReadRoundtripStatus"], "pass")
        self.assertIsNone(payload["lastErrorCode"])
        self.assertTrue(payload["productionReady"])
        self.assertTrue(payload["bucketConfigured"])
        self.assertTrue(payload["prefixConfigured"])
        self.assertTrue(payload["endpointConfigured"])
        self.assertNotIn("judge-artifacts", str(payload))
        self.assertNotIn("prod/ai-judge", str(payload))
        self.assertNotIn("secret", str(payload).lower())

    async def test_s3_artifact_store_healthcheck_should_report_roundtrip_failures(
        self,
    ) -> None:
        cases = [
            (_FakeS3Client(fail_on_put=True), "put_failed", "s3_put_failed"),
            (
                _FakeS3Client(fail_on_head=True),
                "head_missing",
                "artifact_healthcheck_head_missing",
            ),
            (_FakeS3Client(fail_on_get=True), "get_failed", "s3_get_failed"),
            (
                _FakeS3Client(corrupt_get=True),
                "sha_mismatch",
                "artifact_sha256_mismatch",
            ),
        ]
        for client, roundtrip_status, error_code in cases:
            with self.subTest(roundtrip_status=roundtrip_status):
                store = S3CompatibleArtifactStore(
                    bucket="judge-artifacts",
                    prefix="prod/ai-judge",
                    client=client,
                )

                payload = await build_artifact_store_healthcheck_payload(
                    artifact_store=store,
                    roundtrip_enabled=True,
                )

                self.assertEqual(payload["status"], "blocked")
                self.assertEqual(
                    payload["writeReadRoundtripStatus"],
                    roundtrip_status,
                )
                self.assertEqual(payload["lastErrorCode"], error_code)
                self.assertFalse(payload["productionReady"])
                self.assertNotIn("judge-artifacts", str(payload))
                self.assertNotIn("prod/ai-judge", str(payload))

    def test_wiring_should_build_local_artifact_store_by_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = load_settings()

        store = build_artifact_store(settings=settings)

        self.assertIsInstance(store, LocalArtifactStore)
        self.assertEqual(
            build_artifact_store_readiness_payload(store),
            {
                "provider": "local",
                "status": "local_reference",
                "productionReady": False,
                "uriScheme": "local-artifact",
            },
        )

    def test_wiring_should_build_s3_artifact_store_with_injected_client(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "AI_JUDGE_ARTIFACT_STORE_PROVIDER": "s3_compatible",
                "AI_JUDGE_ARTIFACT_BUCKET": "judge-artifacts",
                "AI_JUDGE_ARTIFACT_PREFIX": "prod/ai-judge",
                "AI_JUDGE_ARTIFACT_ENDPOINT_URL": "http://minio:9000",
            },
            clear=True,
        ):
            settings = load_settings()

        with patch("app.wiring._build_s3_client", return_value=_FakeS3Client()):
            store = build_artifact_store(settings=settings)

        self.assertIsInstance(store, S3CompatibleArtifactStore)
        self.assertEqual(
            build_artifact_store_readiness_payload(store)["provider"],
            "s3_compatible",
        )
        self.assertTrue(build_artifact_store_readiness_payload(store)["endpointConfigured"])
        self.assertNotIn(
            "http://minio:9000",
            str(build_artifact_store_readiness_payload(store)),
        )

    async def test_release_readiness_summary_should_hide_s3_uri_parts(self) -> None:
        store = S3CompatibleArtifactStore(
            bucket="judge-artifacts",
            prefix="prod/ai-judge",
            client=_FakeS3Client(),
            endpoint_configured=True,
        )

        export = await write_release_readiness_artifact(
            artifact_store=store,
            case_id=9204,
            dispatch_type="final",
            trace_id="trace-release-9204",
            release_readiness_evidence={
                "evidenceVersion": "policy-release-readiness-evidence-v1",
                "policyVersion": "policy-v3-prod",
                "decision": "allowed",
                "decisionCode": "registry_release_gate_allowed",
                "componentStatuses": [
                    {"component": "artifactStoreReadiness", "status": "ready"}
                ],
                "realEnvEvidenceStatus": {
                    "status": "ready",
                    "source": "release_gate",
                    "realEnvEvidenceAvailable": True,
                },
            },
        )

        summary_text = str(export["summary"])
        self.assertNotIn("judge-artifacts", summary_text)
        self.assertNotIn("prod/ai-judge", summary_text)
        self.assertNotIn("s3://", summary_text)
        self.assertNotIn("endpoint", summary_text.lower())
        self.assertEqual(export["summary"]["artifactStore"]["provider"], "s3_compatible")
        self.assertTrue(export["summary"]["artifactStore"]["productionReady"])


if __name__ == "__main__":
    unittest.main()
