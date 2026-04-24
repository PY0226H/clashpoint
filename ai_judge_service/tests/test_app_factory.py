import unittest

from app.app_factory import create_default_app

from tests.app_factory_test_helpers import (
    build_settings as _build_settings,
)


class AppFactoryTests(unittest.IsolatedAsyncioTestCase):

    async def test_create_default_app_should_be_constructible(self) -> None:
        app = create_default_app(load_settings_fn=_build_settings)
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
