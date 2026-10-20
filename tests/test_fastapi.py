"""Tests for FastAPI / Starlette middleware (investigator.fastapi)."""

from __future__ import annotations

import importlib
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

import investigator.fastapi as inv_fastapi
from investigator.fastapi import (
    InvestigatorMiddleware,
    RequestContext,
    sanitize_context,
    sanitize_text,
    sanitize_url,
)
from investigator.investigation_result import InvestigationResult
from investigator.knowledge_loader import KnowledgeEntryError


# ---------------------------------------------------------------------------
# Basic Execution & Passthrough
# ---------------------------------------------------------------------------

def test_successful_request_passthrough():
    """Successful requests pass through middleware without interference."""
    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware)

    @app.get("/ok")
    def ok_route():
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/ok")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Default Reraise Behavior (reraise=True)
# ---------------------------------------------------------------------------

def test_unhandled_known_exception_reraise_default(capsys):
    """By default, known exceptions are investigated, formatted to stderr, and re-raised."""
    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware)

    @app.get("/fail")
    def fail_route():
        raise ValueError("invalid value in route")

    client = TestClient(app, raise_server_exceptions=True)
    with pytest.raises(ValueError, match="invalid value in route"):
        client.get("/fail")

    captured = capsys.readouterr()
    assert "Error: ValueError" in captured.err
    assert "Status: KNOWN" in captured.err


def test_unhandled_unknown_exception_reraise_default(capsys):
    """By default, unknown exceptions print UNKNOWN status and re-raise."""
    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware)

    @app.get("/fail-unknown")
    def fail_unknown_route():
        raise RuntimeError("some mysterious internal failure")

    client = TestClient(app, raise_server_exceptions=True)
    with pytest.raises(RuntimeError, match="some mysterious internal failure"):
        client.get("/fail-unknown")

    captured = capsys.readouterr()
    assert "Error: RuntimeError" in captured.err
    assert "Status: UNKNOWN" in captured.err


# ---------------------------------------------------------------------------
# Suppressed Exception Handling (reraise=False) & expose_diagnosis
# ---------------------------------------------------------------------------

def test_reraise_false_default_minimal_json():
    """Default reraise=False returns minimal 500 JSON without exposing internal diagnosis."""
    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False)

    @app.get("/fail")
    def fail_route():
        raise ValueError("bad numeric literal")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/fail")

    assert response.status_code == 500
    assert response.headers["X-Error-Investigated"] == "true"
    assert response.headers["X-Error-Status"] == "known"

    # Minimal payload contract: only error key, no diagnosis leakage
    data = response.json()
    assert data == {"error": "InternalServerError"}


def test_reraise_false_opt_in_expose_diagnosis_known():
    """When expose_diagnosis=True, matched errors return structured 500 JSON with diagnosis."""
    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False, expose_diagnosis=True)

    @app.get("/fail")
    def fail_route():
        raise ValueError("bad numeric literal")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/fail")

    assert response.status_code == 500
    assert response.headers["X-Error-Investigated"] == "true"
    assert response.headers["X-Error-Status"] == "known"

    data = response.json()
    assert data["error"] == "InternalServerError"
    assert data["status"] == "known"
    assert "bad numeric literal" in data["message"]
    assert "investigation" in data
    assert "summary" in data["investigation"]
    assert len(data["investigation"]["fixes"]) > 0


def test_reraise_false_opt_in_expose_diagnosis_unknown():
    """When expose_diagnosis=True, uncataloged errors return honest UNKNOWN status."""
    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False, expose_diagnosis=True)

    @app.get("/fail-unknown")
    def fail_unknown():
        raise RuntimeError("uncataloged problem")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/fail-unknown")

    assert response.status_code == 500
    assert response.headers["X-Error-Investigated"] == "true"
    assert response.headers["X-Error-Status"] == "unknown"

    data = response.json()
    assert data["error"] == "InternalServerError"
    assert data["status"] == "unknown"
    assert data["message"] == "uncataloged problem"
    assert "investigation" not in data


def test_reraise_false_custom_status_code():
    """Custom status code is respected when reraise=False."""
    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False, status_code=503)

    @app.get("/fail")
    def fail_route():
        raise ValueError("unavailable")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/fail")
    assert response.status_code == 503
    assert response.json() == {"error": "InternalServerError"}


# ---------------------------------------------------------------------------
# Custom Sink Routing & RequestContext Contract
# ---------------------------------------------------------------------------

def test_custom_sink_single_argument():
    """1-argument sink receives the InvestigationResult."""
    captured: list[InvestigationResult] = []

    def single_arg_sink(result: InvestigationResult) -> None:
        captured.append(result)

    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False, sink=single_arg_sink)

    @app.get("/fail")
    def fail_route():
        raise KeyError("missing_key")

    client = TestClient(app)
    response = client.get("/fail")
    assert response.status_code == 500
    assert len(captured) == 1
    assert captured[0].parsed_error["error_type"] == "KeyError"


def test_custom_sink_receives_frozen_request_context():
    """2-argument sink receives InvestigationResult and frozen RequestContext."""
    captured: list[tuple[InvestigationResult, RequestContext]] = []

    def two_arg_sink(result: InvestigationResult, context: RequestContext) -> None:
        captured.append((result, context))

    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False, sink=two_arg_sink)

    @app.get("/users/{user_id}")
    def fail_route(user_id: int):
        raise ValueError("invalid user")

    client = TestClient(app)
    client.get("/users/42?ref=nav")

    assert len(captured) == 1
    res, ctx = captured[0]
    assert res.parsed_error["error_type"] == "ValueError"

    # Verify RequestContext attributes
    assert isinstance(ctx, RequestContext)
    assert ctx.method == "GET"
    assert ctx.path == "/users/42"
    assert "/users/42?ref=nav" in ctx.url
    assert ctx.query_params == {"ref": "nav"}
    assert ctx.status_code == 500

    # Verify frozen immutability
    with pytest.raises(FrozenInstanceError):
        ctx.path = "/attempted-mutation"  # type: ignore[misc]


def test_custom_sink_var_positional_args():
    """Sink with *args receives both result and RequestContext."""
    captured: list[tuple] = []

    def varargs_sink(*args) -> None:
        captured.append(args)

    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False, sink=varargs_sink)

    @app.get("/fail")
    def fail_route():
        raise ValueError("varargs test")

    client = TestClient(app)
    client.get("/fail")

    assert len(captured) == 1
    assert len(captured[0]) == 2
    assert isinstance(captured[0][0], InvestigationResult)
    assert isinstance(captured[0][1], RequestContext)


@pytest.mark.anyio
async def test_async_sink_supported():
    """Async sinks are properly awaited with RequestContext."""
    captured: list[tuple[InvestigationResult, RequestContext]] = []

    async def async_sink(result: InvestigationResult, context: RequestContext) -> None:
        captured.append((result, context))

    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False, sink=async_sink)

    @app.get("/fail")
    async def fail_route():
        raise ValueError("async fail")

    client = TestClient(app)
    client.get("/fail")

    assert len(captured) == 1
    assert captured[0][0].parsed_error["error_type"] == "ValueError"
    assert isinstance(captured[0][1], RequestContext)


# ---------------------------------------------------------------------------
# Sanitization & Result Purity (C-007 and C-016 Invariant)
# ---------------------------------------------------------------------------

def test_sanitization_headers_and_query_params():
    """Sensitive headers and query params are redacted in RequestContext."""
    captured_context: list[RequestContext] = []

    def sink(result, context):
        captured_context.append(context)

    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False, sink=sink, sanitize=True)

    @app.get("/secure-endpoint")
    def secure_route():
        raise ValueError("auth failure")

    client = TestClient(app)
    client.get(
        "/secure-endpoint?token=supersecret123&public_id=99&user_password=secret_pass",
        headers={
            "Authorization": "Bearer eyJhbGciOi...",
            "Cookie": "session_id=xyz987",
            "X-Api-Key": "my-secret-key",
            "X-Custom-Header": "harmless-value",
        },
    )

    assert len(captured_context) == 1
    ctx = captured_context[0]

    # Headers redacted
    assert ctx.headers["authorization"] == "[REDACTED]"
    assert ctx.headers["cookie"] == "[REDACTED]"
    assert ctx.headers["x-api-key"] == "[REDACTED]"
    assert ctx.headers["x-custom-header"] == "harmless-value"

    # Query params redacted
    assert ctx.query_params["token"] == "[REDACTED]"
    assert ctx.query_params["user_password"] == "[REDACTED]"
    assert ctx.query_params["public_id"] == "99"

    # URL query string redacted
    assert "supersecret123" not in ctx.url
    assert "secret_pass" not in ctx.url
    assert "public_id=99" in ctx.url


def test_sanitization_disabled():
    """When sanitize=False, raw headers and parameters are preserved."""
    captured_context: list[RequestContext] = []

    def sink(result, context):
        captured_context.append(context)

    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False, sink=sink, sanitize=False)

    @app.get("/unmasked")
    def unmasked_route():
        raise ValueError("raw failure")

    client = TestClient(app)
    client.get(
        "/unmasked?token=raw_token",
        headers={"Authorization": "Bearer raw_bearer"},
    )

    assert len(captured_context) == 1
    ctx = captured_context[0]
    assert ctx.headers["authorization"] == "Bearer raw_bearer"
    assert ctx.query_params["token"] == "raw_token"
    assert "token=raw_token" in ctx.url


def test_stderr_sanitization_and_result_immutability(capsys):
    """Rendered stderr output is sanitized, while InvestigationResult remains untouched."""
    captured_result: list[InvestigationResult] = []

    def sink(result, context):
        captured_result.append(result)

    app = FastAPI()
    # Default stderr emission (sink=None)
    app.add_middleware(InvestigatorMiddleware, reraise=True, sanitize=True)

    @app.get("/leak")
    def leak_route():
        raise ValueError("password='super_secret_password' Bearer tok_12345")

    client = TestClient(app, raise_server_exceptions=True)
    with pytest.raises(ValueError):
        client.get("/leak")

    captured = capsys.readouterr()
    # The rendered stderr string does not leak raw credentials
    assert "super_secret_password" not in captured.err
    assert "tok_12345" not in captured.err

    # Now verify sink receives untouched result object (C-007 invariant preserved)
    app2 = FastAPI()
    app2.add_middleware(InvestigatorMiddleware, reraise=False, sink=sink, sanitize=True)

    @app2.get("/leak2")
    def leak_route2():
        raise ValueError("password='super_secret_password' Bearer tok_12345")

    client2 = TestClient(app2)
    client2.get("/leak2")

    assert len(captured_result) == 1
    res = captured_result[0]
    # The result object's parsed_error is pure and unmutated
    assert res.parsed_error["message"] == "password='super_secret_password' Bearer tok_12345"


def test_sanitization_unit_helpers():
    """Direct unit tests for helper sanitization functions."""
    assert sanitize_text(None) is None
    assert sanitize_text("password='super_secret' Bearer abc_token") == "password='[REDACTED]' Bearer [REDACTED]"
    assert sanitize_url("https://example.com/test") == "https://example.com/test"

    raw_ctx = RequestContext(
        method="POST",
        path="/api/login",
        url="",
        client=None,
        headers={"Authorization": "secret", "X-Custom": "safe"},
        query_params={"token": "123", "page": "1"},
        status_code=500,
    )
    sanitized = sanitize_context(raw_ctx)
    assert sanitized.url == ""
    assert sanitized.headers["Authorization"] == "[REDACTED]"
    assert sanitized.headers["X-Custom"] == "safe"
    assert sanitized.query_params["token"] == "[REDACTED]"
    assert sanitized.query_params["page"] == "1"


# ---------------------------------------------------------------------------
# System Signal Non-Interference
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_system_exit_and_keyboard_interrupt_pass_through():
    """KeyboardInterrupt and SystemExit are never intercepted by the middleware."""
    captured: list[InvestigationResult] = []

    mw = InvestigatorMiddleware(
        app=lambda scope, receive, send: None,
        reraise=False,
        sink=lambda r, c: captured.append(r),
    )

    async def interrupt_endpoint(request):
        raise KeyboardInterrupt()

    async def exit_endpoint(request):
        raise SystemExit(1)

    req = Request({"type": "http", "method": "GET", "path": "/"})

    with pytest.raises(KeyboardInterrupt):
        await mw.dispatch(req, interrupt_endpoint)

    with pytest.raises(SystemExit):
        await mw.dispatch(req, exit_endpoint)

    assert len(captured) == 0


# ---------------------------------------------------------------------------
# Custom Knowledge Base
# ---------------------------------------------------------------------------

class AppOrderError(Exception):
    pass


def test_custom_kb_dir_support(tmp_path: Path):
    """InvestigatorMiddleware uses custom knowledge catalog when supplied."""
    custom_kb = tmp_path / "fastapi_kb"
    custom_kb.mkdir()
    entry = (
        f"error_type: {AppOrderError.__module__}.AppOrderError\n"
        "aliases:\n"
        "  - AppOrderError\n"
        "category: orders\n"
        "summary: Order processing error.\n"
        "explanation: An issue occurred processing the customer order.\n"
        "common_causes:\n"
        "  - Inventory depleted\n"
        "fixes:\n"
        "  - Restock inventory\n"
        "related_errors: []\n"
    )
    (custom_kb / "order_error.yaml").write_text(entry, encoding="utf-8")

    app = FastAPI()
    # Test passing kb_dir as a string
    app.add_middleware(
        InvestigatorMiddleware,
        reraise=False,
        kb_dir=str(custom_kb),
        expose_diagnosis=True,
    )

    @app.get("/order")
    def order_route():
        raise AppOrderError("Cannot fulfill order 99")

    client = TestClient(app)
    response = client.get("/order")
    assert response.status_code == 500
    assert response.headers["X-Error-Status"] == "known"
    data = response.json()
    assert data["status"] == "known"
    assert data["investigation"]["summary"] == "Order processing error."


def test_invalid_kb_dir_fails_fast_on_init(tmp_path: Path):
    """Invalid kb_dir raises KnowledgeEntryError during middleware initialization."""
    app = FastAPI()
    nonexistent = tmp_path / "does_not_exist"
    app.add_middleware(InvestigatorMiddleware, kb_dir=nonexistent)
    with pytest.raises(KnowledgeEntryError):
        app.build_middleware_stack()


# ---------------------------------------------------------------------------
# Sync & Async Endpoints
# ---------------------------------------------------------------------------

def test_sync_and_async_endpoint_parity():
    """Both sync def and async def routes are properly caught and investigated."""
    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False)

    @app.get("/sync-fail")
    def sync_fail():
        raise ValueError("sync error")

    @app.get("/async-fail")
    async def async_fail():
        raise ValueError("async error")

    client = TestClient(app)

    res_sync = client.get("/sync-fail")
    assert res_sync.status_code == 500
    assert res_sync.headers["X-Error-Status"] == "known"

    res_async = client.get("/async-fail")
    assert res_async.status_code == 500
    assert res_async.headers["X-Error-Status"] == "known"


def test_reraise_true_with_custom_sink():
    """When reraise=True, custom sink is invoked before exception is re-raised."""
    captured: list[tuple[InvestigationResult, RequestContext]] = []

    def sink(result, context):
        captured.append((result, context))

    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=True, sink=sink)

    @app.get("/crash")
    def crash_route():
        raise KeyError("missing_account")

    client = TestClient(app, raise_server_exceptions=True)
    with pytest.raises(KeyError, match="missing_account"):
        client.get("/crash")

    assert len(captured) == 1
    assert captured[0][0].parsed_error["error_type"] == "KeyError"
    assert captured[0][1].path == "/crash"


def test_sequential_requests_and_reentrancy():
    """Middleware cleanly processes sequential requests and varied exceptions."""
    captured: list[str] = []

    def sink(result, context):
        captured.append(result.parsed_error["error_type"])

    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False, sink=sink)

    @app.get("/val")
    def val_route():
        raise ValueError("v")

    @app.get("/key")
    def key_route():
        raise KeyError("k")

    @app.get("/ok")
    def ok_route():
        return {"status": "ok"}

    client = TestClient(app)
    res1 = client.get("/val")
    res2 = client.get("/ok")
    res3 = client.get("/key")

    assert res1.status_code == 500
    assert res2.status_code == 200
    assert res3.status_code == 500
    assert captured == ["ValueError", "KeyError"]


# ---------------------------------------------------------------------------
# Module & Import Error Handling (Run Last)
# ---------------------------------------------------------------------------

def test_import_error_when_starlette_missing(monkeypatch):
    """Importing investigator.fastapi raises friendly ImportError if starlette is missing."""
    monkeypatch.setitem(sys.modules, "starlette", None)
    monkeypatch.setitem(sys.modules, "starlette.middleware.base", None)

    with pytest.raises(ImportError, match="FastAPI / Starlette is required"):
        importlib.reload(inv_fastapi)

    # Restore module
    monkeypatch.undo()
    importlib.reload(inv_fastapi)
