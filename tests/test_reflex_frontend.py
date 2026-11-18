"""Checks that the Reflex app keeps API traffic responsive."""

import asyncio
import json
import time
import unittest
from unittest.mock import patch

import httpx
from fastapi.responses import Response
from reflex.state import MutableProxy

from musicmind_ui.musicmind_ui import _legacy, api, app


class ReflexFrontendTests(unittest.IsolatedAsyncioTestCase):
    def test_legacy_request_serializes_reflex_state_values(self):
        payload = {"buckets": MutableProxy(["Jazz"], object(), "buckets")}
        with patch("web.app.app.test_client") as client_factory:
            client = client_factory.return_value.__enter__.return_value
            client.open.return_value.status_code = 200
            client.open.return_value.get_json.return_value = {}
            self.assertEqual(_legacy("POST", "/preview", payload), {})
            request_payload = client.open.call_args.kwargs["json"]
            self.assertEqual(json.dumps(request_payload), '{"buckets": ["Jazz"]}')
            self.assertIs(type(request_payload["buckets"]), list)

    async def test_all_page_routes_are_registered(self):
        expected = {"/", "/stats", "/admin", "/synapse", "/logs", "/db",
                    "/gaps", "/playlist-audit", "/update", "/tests", "/guide"}
        routes = {"/" if route == "index" else "/" + route for route in app._unevaluated_pages}
        self.assertTrue(expected.issubset(routes))

    async def test_slow_legacy_call_does_not_block_another_request(self):
        def fake_dispatch(method, path, body, content_type):
            if path == "/genres":
                time.sleep(0.3)
            return Response(content="{}", media_type="application/json")

        transport = httpx.ASGITransport(app=api)
        with patch("musicmind_ui.musicmind_ui._dispatch_legacy", side_effect=fake_dispatch):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                slow = asyncio.create_task(client.get("/genres"))
                await asyncio.sleep(0.03)
                started = time.monotonic()
                quick = await client.get("/countries")
                elapsed = time.monotonic() - started
                self.assertEqual(quick.status_code, 200)
                self.assertLess(elapsed, 0.2)
                self.assertEqual((await slow).status_code, 200)


if __name__ == "__main__":
    unittest.main()
