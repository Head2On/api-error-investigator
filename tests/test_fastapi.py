"""Tests for FastAPI / Starlette middleware (investigator.fastapi and investigator.middleware)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

import investigator.fastapi as inv_fastapi
import investigator.middleware as inv_middleware
from investigator.fastapi import (
    InvestigatorMiddleware,
    sanitize_context,
    sanitize_result,
    sanitize_text,
    sanitize_url,
)
from investigator.investigation_result import InvestigationResult
from investigator.knowledge_loader import KnowledgeEntryError


# ---------------------------------------------------------------------------
# Module & Import Tests
# ---------------------------------------------------------------------------

def test_middleware_alias_exports():
    """investigator.middleware re-exports all public symbols from investigator.fastapi."""
    assert inv_middleware.InvestigatorMiddleware is InvestigatorMiddleware
    assert inv_middleware.sanitize_context is sanitize_context
    assert inv_middleware.sanitize_result is sanitize_result
    assert inv_middleware.sanitize_text is sanitize_text
    assert inv_middleware.sanitize_url is sanitize_url


def test_import_error_when_starlette_missing(monkeypatch):
    """Importing investigator.fastapi raises friendly ImportError if starlette is missing."""
    monkeypatch.setitem(sys.modules, "starlette", None)
    monkeypatch.setitem(sys.modules, "starlette.middleware.base", None)

    with pytest.raises(ImportError, match="FastAPI / Starlette is required"):
        importlib.reload(inv_fastapi)

    # Restore the module
    monkeypatch.undo()
    importlib.reload(inv_fastapi)


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
# Suppressed Exception Handling (reraise=False)
# ---------------------------------------------------------------------------

def test_reraise_false_known_error_returns_500_json():
    """When reraise=False, matched errors return structured 500 JSON with diagnosis."""
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

    data = response.json()
    assert data["error"] == "ValueError"
    assert data["status"] == "known"
    assert "bad numeric literal" in data["message"]
    assert "investigation" in data
    assert "summary" in data["investigation"]
    assert len(data["investigation"]["fixes"]) > 0


def test_reraise_false_unknown_error_returns_500_json():
    """When reraise=False, uncataloged errors return 500 JSON with honest UNKNOWN status."""
    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False)

    @app.get("/fail-unknown")
    def fail_unknown():
        raise RuntimeError("uncataloged problem")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/fail-unknown")

    assert response.status_code == 500
    assert response.headers["X-Error-Investigated"] == "true"
    assert response.headers["X-Error-Status"] == "unknown"

    data = response.json()
    assert data["error"] == "RuntimeError"
    assert data["status"] == "unknown"
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


# ---------------------------------------------------------------------------
# Custom Sink Routing & Signature Detection
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


def test_custom_sink_two_arguments_receives_context():
    """2-argument sink receives both InvestigationResult and context dict."""
    captured: list[tuple[InvestigationResult, dict]] = []

    def two_arg_sink(result: InvestigationResult, context: dict) -> None:
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
    assert ctx["method"] == "GET"
    assert ctx["path"] == "/users/42"
    assert "/users/42?ref=nav" in ctx["url"]
    assert ctx["query_params"] == {"ref": "nav"}
    assert ctx["status_code"] == 500


def test_custom_sink_var_positional_args():
    """Sink with *args receives both result and context."""
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
    assert isinstance(captured[0][1], dict)


@pytest.mark.anyio
async def test_async_sink_supported():
    """Async sinks are properly awaited."""
    captured: list[tuple[InvestigationResult, dict]] = []

    async def async_sink(result: InvestigationResult, context: dict) -> None:
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


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

def test_sanitization_headers_and_query_params():
    """Sensitive headers and query params are redacted by default."""
    captured_context: list[dict] = []

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
    assert ctx["headers"]["authorization"] == "[REDACTED]"
    assert ctx["headers"]["cookie"] == "[REDACTED]"
    assert ctx["headers"]["x-api-key"] == "[REDACTED]"
    assert ctx["headers"]["x-custom-header"] == "harmless-value"

    # Query params redacted
    assert ctx["query_params"]["token"] == "[REDACTED]"
    assert ctx["query_params"]["user_password"] == "[REDACTED]"
    assert ctx["query_params"]["public_id"] == "99"

    # URL query string redacted
    assert "supersecret123" not in ctx["url"]
    assert "secret_pass" not in ctx["url"]
    assert "public_id=99" in ctx["url"]


def test_sanitization_disabled():
    """When sanitize=False, raw headers and parameters are preserved."""
    captured_context: list[dict] = []

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
    assert ctx["headers"]["authorization"] == "Bearer raw_bearer"
    assert ctx["query_params"]["token"] == "raw_token"
    assert "token=raw_token" in ctx["url"]


def test_sanitization_traceback_message():
    """Credentials in traceback message and stack trace are sanitized."""
    captured_result: list[InvestigationResult] = []

    def sink(result, context):
        captured_result.append(result)

    app = FastAPI()
    app.add_middleware(InvestigatorMiddleware, reraise=False, sink=sink, sanitize=True)

    @app.get("/leak")
    def leak_route():
        raise ValueError("Failed login with password='super_secret_password' and Bearer tok_12345")

    client = TestClient(app)
    client.get("/leak")

    assert len(captured_result) == 1
    res = captured_result[0]
    msg = res.parsed_error["message"]
    assert "super_secret_password" not in msg
    assert "tok_12345" not in msg
    assert "password='[REDACTED]'" in msg
    assert "Bearer [REDACTED]" in msg


def test_sanitization_unit_helpers():
    """Direct unit tests for helper sanitization functions."""
    assert sanitize_text(None) is None
    assert sanitize_url("https://example.com/test") == "https://example.com/test"
    assert sanitize_context({"url": ""})["url"] == ""

    # Unknown result sanitization
    unknown_res = InvestigationResult.unknown({
        "error_type": "UnknownError",
        "message": "secret=123",
        "file": None,
        "line": None,
        "function": None,
        "stack_trace": "stack token: xyz",
    })
    sanitized_unknown = sanitize_result(unknown_res)
    assert sanitized_unknown.status == "unknown"
    assert "123" not in sanitized_unknown.parsed_error["message"]
    assert "xyz" not in sanitized_unknown.parsed_error["stack_trace"]


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
    app.add_middleware(InvestigatorMiddleware, reraise=False, kb_dir=str(custom_kb))

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


def test_reraise_true_with_custom_sink():
    """When reraise=True, custom sink is invoked before exception is re-raised."""
    captured: list[tuple[InvestigationResult, dict]] = []

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
    assert captured[0][1]["path"] == "/crash"


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
    assert res_sync.json()["status"] == "known"

    res_async = client.get("/async-fail")
    assert res_async.status_code == 500
    assert res_async.json()["status"] == "known"
