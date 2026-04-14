import unittest
from types import SimpleNamespace

from app.applications.registry_runtime import (
    build_prompt_registry_runtime,
    build_tool_registry_runtime,
)


def _build_settings(**overrides: object):
    base = {
        "prompt_registry_default_version": "promptset-v3-default",
        "prompt_registry_json": "",
        "tool_registry_default_version": "toolset-v3-default",
        "tool_registry_json": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class RegistryRuntimeTests(unittest.TestCase):
    def test_build_prompt_registry_runtime_should_return_builtin_profile(self) -> None:
        runtime = build_prompt_registry_runtime(settings=_build_settings())
        self.assertEqual(runtime.default_version, "promptset-v3-default")
        profile = runtime.get_profile("promptset-v3-default")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(
            profile.prompt_versions["claimGraphVersion"],
            "v1-claim-graph-bootstrap",
        )

    def test_build_prompt_registry_runtime_should_parse_custom_json(self) -> None:
        runtime = build_prompt_registry_runtime(
            settings=_build_settings(
                prompt_registry_json=(
                    '{"defaultVersion":"promptset-v4","profiles":[{"version":"promptset-v4",'
                    '"promptVersions":{"claimGraphVersion":"v2"},"metadata":{"status":"active"}}]}'
                )
            )
        )
        self.assertEqual(runtime.default_version, "promptset-v4")
        profile = runtime.get_profile("promptset-v4")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.prompt_versions["claimGraphVersion"], "v2")

    def test_build_tool_registry_runtime_should_return_builtin_profile(self) -> None:
        runtime = build_tool_registry_runtime(settings=_build_settings())
        self.assertEqual(runtime.default_version, "toolset-v3-default")
        profile = runtime.get_profile("toolset-v3-default")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertIn("claim_graph_builder", profile.tool_ids)

    def test_build_tool_registry_runtime_should_parse_custom_json(self) -> None:
        runtime = build_tool_registry_runtime(
            settings=_build_settings(
                tool_registry_json=(
                    '{"defaultVersion":"toolset-v4","profiles":[{"version":"toolset-v4",'
                    '"toolIds":["transcript_reader","replay_loader"],"metadata":{"status":"active"}}]}'
                )
            )
        )
        self.assertEqual(runtime.default_version, "toolset-v4")
        profile = runtime.get_profile("toolset-v4")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.tool_ids, ("transcript_reader", "replay_loader"))


if __name__ == "__main__":
    unittest.main()
