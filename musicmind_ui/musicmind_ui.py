"""Reflex application and compatibility API wiring."""

import asyncio

import reflex as rx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from musicmind.paths import PROJECT_ROOT
from musicmind_ui.job_definitions import JOB_GROUPS
from musicmind_ui.state import UI
from musicmind_ui.views import (
    admin_page,
    audit_page,
    gaps_page,
    guide_page,
    home,
    logs_page,
    query_page,
    stats_page,
    tests_page,
    update_page,
)


api = FastAPI(title="MusicMind for Plex")
api.mount("/static", StaticFiles(directory=PROJECT_ROOT / "web" / "static"), name="static")


def _dispatch_legacy(method: str, path: str, body: bytes, content_type: str):
    from web.app import app as flask_app

    client = flask_app.test_client()
    result = client.open(path, method=method, data=body, content_type=content_type, buffered=False)
    if result.mimetype == "text/event-stream":
        return result
    response = Response(content=result.get_data(), status_code=result.status_code,
                        media_type=result.mimetype)
    result.close()
    return response


async def legacy_api(request: Request):
    path = request.url.path + ("?" + request.url.query if request.url.query else "")
    response = await asyncio.to_thread(
        _dispatch_legacy, request.method, path, await request.body(),
        request.headers.get("content-type", "application/octet-stream"))
    if isinstance(response, Response):
        return response

    def chunks():
        try:
            yield from response.response
        finally:
            response.close()

    return StreamingResponse(chunks(), status_code=response.status_code,
                             media_type="text/event-stream")


LEGACY_API = [
    ("/preview", ["POST"]), ("/create", ["POST"]),
    ("/onthisday", ["POST"]), ("/based-on", ["POST"]),
    ("/based-on-search", ["GET"]), ("/query", ["POST"]),
    ("/playlists", ["GET"]), ("/genres", ["GET"]),
    ("/countries", ["GET"]), ("/stats/data", ["GET"]),
    ("/export-csv", ["GET"]), ("/scan", ["GET"]),
    ("/playlist-audit-data/{playlist_key}", ["GET"]),
    ("/check-update", ["GET"]),
    ("/admin/error-counts", ["GET"]),
    ("/admin/clear-errors/{source}", ["POST"]),
    ("/admin/other-processes-status", ["GET"]),
    ("/synapse-status", ["GET"]), ("/synapse-errors", ["GET"]),
    ("/synapse-full-log", ["GET"]),
    ("/run/fullsync-tail", ["GET"]), ("/run/synapse-full", ["GET"]),
    ("/run/synapse-count", ["GET"]), ("/run/synapse-estimate", ["GET"]),
    ("/run/synapse-limited", ["GET"]), ("/run/resync", ["GET"]),
    ("/run/gaps", ["GET"]), ("/run/fullsync", ["GET"]),
    ("/run/update", ["GET"]),
    ("/run/assertion/{assertion_id}", ["GET"]),
    ("/run/test/{test_id}", ["GET"]),
    ("/run/{script}", ["GET"]),
]
for route, methods in LEGACY_API:
    api.add_api_route(route, legacy_api, methods=methods, include_in_schema=False)


app = rx.App(
    api_transformer=api,
    stylesheets=["/reflex.css"],
)
for page, route, on_load in [
    (home, "/", UI.home_load),
    (stats_page, "/stats", UI.stats_load),
    (admin_page, "/admin", UI.admin_load),
    (lambda: rx.fragment(), "/synapse", rx.redirect("/admin")),
    (logs_page, "/logs", UI.logs_load),
    (query_page, "/db", None),
    (gaps_page, "/gaps", UI.gaps_load),
    (audit_page, "/playlist-audit", UI.playlists_load),
    (update_page, "/update", UI.update_load),
    (tests_page, "/tests", None),
    (guide_page, "/guide", UI.guide_load),
]:
    app.add_page(page, route=route,
                 on_load=[UI.clear_message, on_load] if on_load else UI.clear_message)
