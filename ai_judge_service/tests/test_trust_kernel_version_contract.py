from __future__ import annotations

import unittest

from app.applications.trust_kernel_version_contract import (
    TRUST_KERNEL_VERSION_ITEM_KEYS,
    TRUST_KERNEL_VERSION_TOP_LEVEL_KEYS,
    TRUST_KERNEL_VERSION_VECTOR_KEYS,
    validate_trust_kernel_version_contract,
)


class TrustKernelVersionContractTests(unittest.TestCase):
    def _build_payload(self) -> dict:
        return {
            "caseId": 9401,
            "dispatchType": "final",
            "traceId": "trace-final-9401",
            "item": {
                "version": "trust-phaseA-kernel-version-v1",
                "caseId": 9401,
                "traceId": "trace-final-9401",
                "kernelVector": {
                    "dispatchType": "final",
                    "provider": "mock",
                    "judgeCoreVersion": "judge-core-v3",
                    "pipelineVersion": "pipeline-v3",
                    "policyVersion": "v3-default",
                    "promptVersion": "prompt-v3",
                    "toolsetVersion": "toolset-v3",
                    "agentRuntimeVersion": "agent-runtime-v3",
                },
                "kernelHash": "kernel_hash",
                "registryHash": "registry_hash",
            },
        }

    def test_validate_trust_kernel_version_contract_should_pass_for_stable_payload(self) -> None:
        payload = self._build_payload()
        self.assertEqual(set(payload.keys()), set(TRUST_KERNEL_VERSION_TOP_LEVEL_KEYS))
        self.assertEqual(set(payload["item"].keys()), set(TRUST_KERNEL_VERSION_ITEM_KEYS))
        self.assertEqual(
            set(payload["item"]["kernelVector"].keys()),
            set(TRUST_KERNEL_VERSION_VECTOR_KEYS),
        )
        validate_trust_kernel_version_contract(payload)

    def test_validate_trust_kernel_version_contract_should_fail_on_missing_item_key(self) -> None:
        payload = self._build_payload()
        payload["item"].pop("kernelHash")

        with self.assertRaises(ValueError) as ctx:
            validate_trust_kernel_version_contract(payload)
        self.assertIn("trust_kernel_version_item_missing_keys:kernelHash", str(ctx.exception))

    def test_validate_trust_kernel_version_contract_should_fail_on_trace_id_mismatch(self) -> None:
        payload = self._build_payload()
        payload["item"]["traceId"] = "trace-final-other"

        with self.assertRaises(ValueError) as ctx:
            validate_trust_kernel_version_contract(payload)
        self.assertIn("trust_kernel_version_item_trace_id_mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
