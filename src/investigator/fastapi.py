"""FastAPI / Starlette middleware for Error Investigator.

Provides InvestigatorMiddleware to intercept unhandled errors in web requests,
run them through the deterministic investigation pipeline, extract sanitized request
context, and route findings to custom sinks or structured JSON responses.
"""

from __future__ import annotations

import inspect
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.types import ASGIApp
except ImportError as err:
    raise ImportError(
        "FastAPI / Starlette is required to use InvestigatorMiddleware. "
        "Install it with: pip install error-investigator[fastapi]"
    ) from err

from investigator.cli_format import format_result
from investigator.investigation_result import InvestigationResult
from investigator.knowledge_loader import KnowledgeEntryError, load_all_entries
from investigator.sdk import investigate_exception

__all__ = [
    "InvestigatorMiddleware",
    "RequestContext",
    "sanitize_context",
    "sanitize_text",
    "sanitize_url",
]

SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "proxy-authorization",
    "x-auth-token",
    "x-csrf-token",
    "x-xsrf-token",
}

SENSITIVE_KEY_SUBSTRINGS = (
    "auth",
    "token",
    "secret",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "credential",
)


@dataclass(frozen=True)
class RequestContext:
    """Immutable request context captured when an error occurs."""

    method: str
    path: str
    url: str
    client: str | None
    headers: dict[str, str]
    query_params: dict[str, str]
    status_code: int


def sanitize_url(url: str) -> str:
    """Sanitize sensitive query parameter values within a URL string."""
    parts = urlsplit(url)
    if not parts.query:
        return url
    qsl = parse_qsl(parts.query, keep_blank_values=True)
    sanitized_qsl: list[tuple[str, str]] = []
    for k, v in qsl:
        k_lower = k.lower()
        if any(sub in k_lower for sub in SENSITIVE_KEY_SUBSTRINGS):
            sanitized_qsl.append((k, "[REDACTED]"))
        else:
            sanitized_qsl.append((k, v))
    new_query = urlencode(sanitized_qsl, safe="[]")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


def sanitize_context(context: RequestContext) -> RequestContext:
    """Return a sanitized copy of the RequestContext."""
    headers: dict[str, str] = {}
    for k, v in context.headers.items():
        k_lower = k.lower()
        if k_lower in SENSITIVE_HEADER_NAMES or any(sub in k_lower for sub in SENSITIVE_KEY_SUBSTRINGS):
            headers[k] = "[REDACTED]"
        else:
            headers[k] = v

    query_params: dict[str, str] = {}
    for k, v in context.query_params.items():
        k_lower = k.lower()
        if any(sub in k_lower for sub in SENSITIVE_KEY_SUBSTRINGS):
            query_params[k] = "[REDACTED]"
        else:
            query_params[k] = v

    sanitized_url = sanitize_url(context.url) if context.url else context.url

    return RequestContext(
        method=context.method,
        path=context.path,
        url=sanitized_url,
        client=context.client,
        headers=headers,
        query_params=query_params,
        status_code=context.status_code,
    )


def sanitize_text(text: str | None) -> str | None:
    """Mask credential patterns in rendered error messages and stack traces."""
    if text is None:
        return None
    # Mask Bearer tokens
    sanitized = re.sub(
        r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/]+=*",
        r"\1[REDACTED]",
        text,
    )
    # Mask key-value credentials (e.g. password=..., token: "...")
    sanitized = re.sub(
        r"(?i)\b(password|passwd|secret|token|api_key|apikey|access_token)\b\s*([:=])\s*([\'\"]?)[^\s,\'\"]+\3",
        r"\1\2\3[REDACTED]\3",
        sanitized,
    )
    return sanitized


async def _dispatch_sink(
    sink: Callable[..., Any],
    result: InvestigationResult,
    context: RequestContext,
) -> None:
    """Dispatch diagnosis and context to sink, handling 1-arg, 2-arg, and async sinks."""
    sig = inspect.signature(sink)
    takes_context = False
    for param in sig.parameters.values():
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            takes_context = True
            break
    if not takes_context:
        pos_params = [
            p
            for p in sig.parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        if len(pos_params) >= 2:
            takes_context = True

    if takes_context:
        res = sink(result, context)
    else:
        res = sink(result)

    if inspect.isawaitable(res):
        await res


class InvestigatorMiddleware(BaseHTTPMiddleware):
    """FastAPI and Starlette middleware for automatic error investigation."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        kb_dir: Path | str | None = None,
        reraise: bool = True,
        sink: Callable[[InvestigationResult, RequestContext], None]
        | Callable[[InvestigationResult], None]
        | None = None,
        sanitize: bool = True,
        status_code: int = 500,
        expose_diagnosis: bool = False,
    ) -> None:
        super().__init__(app)
        if kb_dir is not None:
            load_all_entries(kb_dir)
        self.kb_dir = Path(kb_dir) if isinstance(kb_dir, str) else kb_dir
        self.reraise = reraise
        self.sink = sink
        self.sanitize = sanitize
        self.status_code = status_code
        self.expose_diagnosis = expose_diagnosis

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            result = investigate_exception(exc, kb_dir=self.kb_dir)
            raw_context = RequestContext(
                method=request.method,
                path=request.url.path,
                url=str(request.url),
                client=request.client.host if request.client else None,
                headers=dict(request.headers),
                query_params=dict(request.query_params),
                status_code=self.status_code if not self.reraise else 500,
            )

            context = sanitize_context(raw_context) if self.sanitize else raw_context

            if self.sink is not None:
                await _dispatch_sink(self.sink, result, context)
            else:
                rendered = format_result(result)
                if self.sanitize:
                    rendered = sanitize_text(rendered) or ""
                sys.stderr.write("\n")
                sys.stderr.write(rendered)
                sys.stderr.write("\n")

            if self.reraise:
                raise

            content: dict[str, Any] = {"error": "InternalServerError"}
            if self.expose_diagnosis:
                content["status"] = result.status
                content["message"] = result.parsed_error.get("message") or "An internal error occurred"
                if result.investigation is not None:
                    content["investigation"] = {
                        "summary": result.investigation.summary,
                        "explanation": result.investigation.explanation,
                        "common_causes": result.investigation.common_causes,
                        "fixes": result.investigation.fixes,
                        "docs_url": result.investigation.docs_url,
                        "related_errors": result.investigation.related_errors,
                    }

            headers = {
                "X-Error-Investigated": "true",
                "X-Error-Status": result.status,
            }
            return JSONResponse(
                status_code=self.status_code,
                content=content,
                headers=headers,
            )
