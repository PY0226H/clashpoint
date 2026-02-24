import unittest

from app.scoring import resolve_effective_style_mode


class ScoringPolicyTests(unittest.TestCase):
    def test_resolve_effective_style_mode_should_use_system_config(self) -> None:
        mode, source = resolve_effective_style_mode("mixed", "rational")
        self.assertEqual(mode, "rational")
        self.assertEqual(source, "system_config")

    def test_resolve_effective_style_mode_should_fallback_when_system_invalid(self) -> None:
        mode, source = resolve_effective_style_mode("mixed", "invalid-mode")
        self.assertEqual(mode, "rational")
        self.assertEqual(source, "system_config_fallback_default")

    def test_resolve_effective_style_mode_should_use_default_when_no_input(self) -> None:
        mode, source = resolve_effective_style_mode("", None)
        self.assertEqual(mode, "rational")
        self.assertEqual(source, "default")


if __name__ == "__main__":
    unittest.main()
