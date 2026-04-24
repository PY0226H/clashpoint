from __future__ import annotations

import unittest

from app.applications.route_group_health import register_health_routes
from fastapi import FastAPI


class RouteGroupHealthTests(unittest.TestCase):
    def test_register_health_routes_should_expose_healthz_handle(self) -> None:
        app = FastAPI()

        handles = register_health_routes(app=app)

        paths = {route.path for route in app.routes}
        self.assertIn("/healthz", paths)
        self.assertEqual(handles.healthz.__name__, "healthz")
