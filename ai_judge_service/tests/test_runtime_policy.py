import os
import unittest
from unittest.mock import patch

from app.runtime_policy import (
    PROVIDER_MOCK,
    PROVIDER_OPENAI,
    is_production_env,
    normalize_provider,
    parse_env_bool,
    runtime_env_label,
    should_use_openai,
)


class RuntimePolicyTests(unittest.TestCase):
    def test_parse_env_bool_should_respect_defaults_and_literals(self) -> None:
        self.assertTrue(parse_env_bool("true"))
        self.assertTrue(parse_env_bool("1"))
        self.assertFalse(parse_env_bool("false"))
        self.assertFalse(parse_env_bool("0"))
        self.assertTrue(parse_env_bool("unexpected", default=True))
        self.assertFalse(parse_env_bool(None, default=False))

    def test_normalize_provider_should_be_fail_closed(self) -> None:
        self.assertEqual(normalize_provider("openai"), PROVIDER_OPENAI)
        self.assertEqual(normalize_provider("OPENAI"), PROVIDER_OPENAI)
        self.assertEqual(normalize_provider("mock"), PROVIDER_MOCK)
        self.assertEqual(normalize_provider("dev_mock"), PROVIDER_MOCK)
        self.assertEqual(normalize_provider("invalid"), PROVIDER_OPENAI)
        self.assertEqual(normalize_provider(None), PROVIDER_OPENAI)

    def test_should_use_openai_requires_provider_and_api_key(self) -> None:
        self.assertTrue(should_use_openai(PROVIDER_OPENAI, "sk-xx"))
        self.assertFalse(should_use_openai(PROVIDER_OPENAI, ""))
        self.assertFalse(should_use_openai(PROVIDER_MOCK, "sk-xx"))

    def test_runtime_env_label_should_resolve_by_priority(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "staging",
                "ECHOISLE_ENV": "production",
            },
            clear=True,
        ):
            self.assertEqual(runtime_env_label(), "production")

        with patch.dict(os.environ, {"ENV": "dev"}, clear=True):
            self.assertEqual(runtime_env_label(), "dev")

        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(runtime_env_label())

    def test_is_production_env_should_match_prod_literals(self) -> None:
        self.assertTrue(is_production_env("production"))
        self.assertTrue(is_production_env("prod"))
        self.assertFalse(is_production_env("staging"))
        self.assertFalse(is_production_env(None))


if __name__ == "__main__":
    unittest.main()
