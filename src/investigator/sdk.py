"""SDK for investigating exceptions programmatically.

Two public entry points:

- ``investigate_exception(exc)`` — turn a caught exception into an
  ``InvestigationResult``. Pure function, no side effects.
- ``capture_exception(...)`` — context manager and decorator that watches a block
  or function, and on exception prints (or sinks) the diagnosis and optionally re-raises.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from traceback import format_exception
from typing import Any, Callable, Iterator

from investigator.cli_format import format_result
from investigator.investigation_result import InvestigationResult
from investigator.investigator import investigate as _investigate
from investigator.knowledge_loader import KnowledgeEntryError

__all__ = ["investigate_exception", "capture_exception", "KnowledgeEntryError"]


def investigate_exception(
    exc: BaseException,
    *,
    kb_dir: Path | str | None = None,
) -> InvestigationResult:
    """Investigate a caught exception and return the structured result.

    Never prints, logs, or re-raises. The caller decides what to do with the
    result. Propagates ``KnowledgeEntryError`` if ``kb_dir`` is invalid.
    """
    raw_error = "".join(format_exception(type(exc), exc, exc.__traceback__))
    return _investigate(raw_error, kb_dir=kb_dir)


@contextmanager
def _capture_context(
    *,
    kb_dir: Path | str | None = None,
    reraise: bool = True,
    sink: Callable[[InvestigationResult], None] | None = None,
) -> Iterator[None]:
    try:
        yield
    except Exception as exc:
        result = investigate_exception(exc, kb_dir=kb_dir)
        if sink is not None:
            sink(result)
        else:
            sys.stderr.write("\n")
            sys.stderr.write(format_result(result))
            sys.stderr.write("\n")
        if reraise:
            raise


def capture_exception(
    func: Callable[..., Any] | None = None,
    *,
    kb_dir: Path | str | None = None,
    reraise: bool = True,
    sink: Callable[[InvestigationResult], None] | None = None,
) -> Any:
    """Watch a block or function; on ``Exception``, investigate and (by default) re-raise.

    Can be used as:
    - Context manager: ``with capture_exception(): ...``
    - Parameterized context manager: ``with capture_exception(reraise=False): ...``
    - Bare decorator: ``@capture_exception``
    - Parameterized decorator: ``@capture_exception(reraise=False)``

    ``KeyboardInterrupt`` and ``SystemExit`` pass through untouched.
    """
    cm = _capture_context(kb_dir=kb_dir, reraise=reraise, sink=sink)
    if func is not None:
        return cm(func)
    return cm