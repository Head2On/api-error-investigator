# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-10-21

Initial release.

### Features

- **CLI** (`investigate`) - deterministic error investigation from
  interactive input or piped stdin, with custom knowledge base support
  via `--kb-dir`.
- **SDK** - `investigate_exception(exc)` for programmatic use, and
  `capture_exception()` as context manager or decorator.
- **FastAPI / Starlette middleware** - `InvestigatorMiddleware` with
  request context extraction, sensitive-data sanitization, and
  configurable failure behavior.
- **Built-in knowledge base** - 20 curated entries covering Python
  builtins, filesystem, network, data serialization, and database errors.

### Quality

- 296 tests, 100% statement coverage across all source modules.
- Deterministic and offline - zero network calls in the shipped tool.
- Honest by design: unrecognized errors return `Status: UNKNOWN`
  rather than fabricating a diagnosis.
