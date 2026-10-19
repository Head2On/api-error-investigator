# Error Investigator

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests: 238 passed](https://img.shields.io/badge/tests-238%20passed-brightgreen.svg)]()
[![Coverage: 100%](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)]()

A fast, deterministic CLI developer tool that investigates Python and API errors by parsing tracebacks, matching them against a curated knowledge base, and returning structured diagnoses with root causes and actionable fixes.

**Status:** Deterministic offline engine — zero external network requests in the shipped tool.

---

## Key Features

- **Deterministic & Instant:** Powered by an offline, indexed knowledge base. Zero latency, zero external network requests, completely reproducible.
-  **Honest by Design:** If an error is unknown, it returns `Status: UNKNOWN`. The tool **never fabricates** a diagnosis.
-  **Dual Interaction Modes:**
  - **Interactive TTY:** Paste multiline tracebacks directly with early directory validation and simple `DONE` submission.
  - **Piped Mode:** Pipe stderr or log files directly (`python app.py 2>&1 | investigate`) with silent, prompt-free execution.
-  **Extensible Knowledge Base:** Bring custom error catalogs via `--kb-dir <path>` with automatic schema validation and collision detection.
-  **100% Tested:** Comprehensive test suite with 100% statement coverage across all modules.

---

## How It Works

```text
               Raw Error String / Traceback
                            │
                            ▼
     ┌──────────────────────────────────────────────┐
     │  parse_error()                               │
     │  • Extracts error_type, message, file, line  │
     └──────────────────────┬───────────────────────┘
                            ▼
                       ParsedError
                            │
                            ▼
     ┌──────────────────────────────────────────────┐
     │  lookup()                                    │
     │  • Matches primary error_type or aliases     │
     │  • Validates custom KB directory upfront     │
     └──────────────────────┬───────────────────────┘
                            ▼
                 KnowledgeEntry | None
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
        [Match Found]               [No Match]
       Status: KNOWN              Status: UNKNOWN
      Structured root causes      Honest fallback
         & proven fixes         (never fabricated)
              │                           │
              └─────────────┬─────────────┘
                            ▼
                     format_result()
                            │
                            ▼
                     Terminal Output
```

---

## Installation

### Prerequisites

- Python 3.10 or higher
- Git

### Install from Source

```bash
git clone https://github.com/Head2On/api-error-investigator.git
cd api-error-investigator

# Create and activate virtual environment
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install in editable mode
pip install -e .
```

Verify the installation:

```bash
investigate --help
```

---

## Quickstart & Usage

### 1. Interactive Mode

Run `investigate` without arguments:

```bash
investigate
```

Paste your traceback, type `DONE` on a new line (case-insensitive), and press **Enter** (or send EOF with `Ctrl+D` / `Ctrl+Z`):

```text
Paste your error below.
(Type 'DONE' on a new blank line and press Enter to submit):

ValueError: invalid literal for int() with base 10: 'abc'
DONE
```

#### Sample Output (Known Error)

```text
Error: ValueError
Status: KNOWN

Summary:
A function received a value of the correct type but with an invalid content.

Explanation:
ValueError means the argument had the right type, but the value itself was not
acceptable to the function. It's not a type error (which would mean the wrong type was
passed) -- it's a content error. Built-in functions, int(), float(), datetime parsing,
and many libraries raise it for malformed input.

Common Causes:
- Calling int("abc") or float("12.3.4") on non-numeric strings.
- Unpacking a sequence with the wrong number of elements.
- Passing a negative number to a function that requires non-negative.
- Parsing a malformed date/time or UUID string.
- Iterating over a closed file or reading from a closed resource.

Fixes:
- Read the error message -- Python's ValueError almost always states what's wrong.
- Wrap the call in try/except and validate input before passing it in.
- If parsing user input, use a parser that returns a result type instead (e.g.
    Pydantic).
- Check the argument at the call site, not deep inside the function.
- For unpacking errors, print or log the value to see how many items it actually has.

Documentation:
https://docs.python.org/3/library/exceptions.html#ValueError

Related Errors:
- TypeError
- KeyError
```

#### Sample Output (Unknown Error)

```text
Error: SomeUnregisteredCustomError
Status: UNKNOWN

The Knowledge Base has no matching entry for this error. No diagnosis was produced.
```

---

### 2. Piped Mode (Scripts, CI, Logs)

In piped mode (when stdin is not a TTY), `investigate` runs silently to EOF without interactive prompts or sentinels:

```bash
# Pipe directly from a failing script
python script.py 2>&1 | investigate

# Pipe from a saved traceback or log file
cat traceback.log | investigate

# Pipe from PowerShell
Get-Content error.log | investigate

# Pipe a single error string directly
echo "KeyError: 'user_id'" | investigate
```

---

### 3. Custom Knowledge Base (`--kb-dir`)

Use your team's custom knowledge base directory instead of the built-in catalog:

```bash
investigate --kb-dir ./custom_kb
```

Piped mode works with custom knowledge bases as well:

```bash
python app.py 2>&1 | investigate --kb-dir ./custom_kb
```

> [!NOTE]
> **Early Validation:** If `--kb-dir` does not exist, is not a directory, contains no YAML files, has malformed YAML, or contains identifier collisions, `investigate` prints an error and exits **before** prompting for input.

---

## CLI Reference

```text
Usage: investigate [OPTIONS]

Error Investigator — a CLI developer tool for investigating Python and API
errors.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --kb-dir        <path>  Path to a custom knowledge base directory.           │
│ --help                  Show this message and exit.                          │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### Exit Codes

| Code | Meaning | Reason |
| :---: | :--- | :--- |
| **`0`** | **Success** | Investigation completed normally (for both `KNOWN` and `UNKNOWN` errors). |
| **`1`** | **Execution Error** | Empty input received, or custom knowledge base failed validation (nonexistent path, empty folder, invalid YAML, or identifier collision). |
| **`2`** | **Invocation Error** | Invalid CLI usage (e.g. unrecognized options or unexpected positional arguments). |

---

## Knowledge Base Schema

Each knowledge base entry is a YAML file placed in the knowledge directory.

### YAML Specification

```yaml
error_type: my_service.errors.UserNotFoundError
aliases:
  - UserNotFoundError
  - AccountNotFound
category: database
subcategory: entity_lookup  # optional (string or null)
summary: Raised when a user record cannot be found in the database.
explanation: >
  Occurs when querying for a user ID that does not exist in the database,
  or when an account has been soft-deleted and filtered out by active tenant rules.
common_causes:
  - The requested user_id does not exist in the users table.
  - The record is marked as deleted (deleted_at is not NULL).
  - The query is scoped to the wrong tenant ID.
fixes:
  - Check if user_id is correct before executing the query.
  - Use get_or_none() or handle UserNotFoundError explicitly.
  - Verify tenant isolation filter context.
docs_url: https://docs.example.com/errors/user-not-found  # optional (string or null)
related_errors:
  - AuthenticationError
```

### Schema Rules & Invariants

1. **Required Fields:**
   - `error_type` *(string)*: Primary fully-qualified error class identifier.
   - `category` *(string)*: High-level domain category (e.g., `database`, `python`, `network`).
   - `summary` *(string)*: High-level summary of the issue.
   - `explanation` *(string)*: Detailed explanation of the error context.
   - `common_causes` *(list of strings)*: Typical root causes.
   - `fixes` *(list of strings)*: Practical, actionable remedies.
   - `aliases` *(list of strings)*: Alternative names (e.g. unqualified class names).
   - `related_errors` *(list of strings)*: Associated error types.
2. **Optional Fields:**
   - `subcategory` *(string or null)*: Granular subcategory.
   - `docs_url` *(string or null)*: Official documentation link.
3. **Collision Invariant:**
   No identifier may appear as the `error_type` or `alias` of more than one entry or more than once within a single entry across the entire knowledge base. Any overlap triggers an upfront `KnowledgeEntryError`.

---

## Built-in Knowledge Base

Out of the box, `investigate` includes curated diagnostics for:

| Error Type | Category | Aliases |
| :--- | :--- | :--- |
| `sqlalchemy.exc.IntegrityError` | `database` | `IntegrityError` |
| `sqlalchemy.exc.OperationalError` | `database` | `OperationalError` |
| `sqlalchemy.exc.DataError` | `database` | `DataError` |
| `ValueError` | `python` | — |
| `KeyError` | `python` | — |

---

## Python SDK & Programmatic API

Error Investigator provides both high-level runtime utilities in `investigator.sdk` and direct parsing functions in `investigator`.

### 1. Investigating Caught Exceptions (`investigate_exception`)

Use `investigate_exception` to inspect an active or caught exception instance directly without manually extracting tracebacks.

- **Pure Function:** Zero side effects — never prints, logs, or re-raises.
- **Traceback-Aware:** Analyzes active exception tracebacks, chained exceptions (`from e`), and unraised exceptions (a never-raised exception is formatted as `TypeName: message` and investigated normally).
- **Custom KB Support:** Supports custom `--kb-dir` catalogs via the `kb_dir` keyword argument.

```python
from investigator.sdk import investigate_exception

try:
    int("invalid")
except ValueError as exc:
    result = investigate_exception(exc)

    if result.status == "known":
        assert result.investigation is not None
        print(f"Error Type: {result.parsed_error['error_type']}")
        print(f"Summary:    {result.investigation.summary}")
        print("Recommended Fixes:")
        for fix in result.investigation.fixes:
            print(f"  • {fix}")
    else:
        print("Uncataloged error. No diagnosis produced.")
```

---

### 2. Automated Exception Capture (`capture_exception`)

`capture_exception` acts as both a **context manager** and a **decorator** to monitor code blocks or functions. When an `Exception` is raised, it automatically investigates the error, outputs formatted diagnosis to `sys.stderr` (or a custom sink), and optionally re-raises.

#### As a Context Manager

```python
from investigator.sdk import capture_exception

# Default: prints formatted diagnosis to stderr and re-raises the original exception
with capture_exception():
    data = load_data()

# Suppress exception after diagnosing (reraise=False)
with capture_exception(reraise=False):
    risky_operation()

# Route diagnoses to a custom sink (e.g. logger, monitoring, or telemetry)
def log_sink(result):
    my_logger.error("Investigated failure: %s", result.parsed_error["error_type"])
    if result.investigation:
        my_logger.info("Summary: %s", result.investigation.summary)

with capture_exception(sink=log_sink):
    process_order()
```

#### As a Function Decorator

Works as either a bare decorator or parameterized with options:

```python
from investigator.sdk import capture_exception

# Bare decorator: diagnoses to stderr and re-raises on exception
@capture_exception
def query_user(user_id: int):
    return db.query(User).filter_by(id=user_id).one()

# Parameterized decorator: custom sink and suppression
@capture_exception(reraise=False, sink=custom_sink)
def background_sync():
    sync_remote_records()

# With custom knowledge base directory
@capture_exception(kb_dir="./custom_kb")
def calculate_metrics():
    compute_heavy_stats()
```

> [!NOTE]
> **Safe for Repeated Calls:** Decorated functions are reentrant and safe for repeated calls across the application lifecycle.

---

### 3. Direct Traceback String Investigation (`investigate`)

For investigating raw traceback strings from external logs, worker queues, or stdin streams:

```python
from investigator import investigate

traceback_text = """
Traceback (most recent call last):
  File "main.py", line 12, in <module>
    user = users[user_id]
KeyError: 'user_id'
"""

result = investigate(traceback_text)

if result.status == "known":
    assert result.investigation is not None
    print(f"Summary: {result.investigation.summary}")
```

---

### 4. Custom Knowledge Base & Error Handling

When providing a custom knowledge base directory (`kb_dir`) to `investigate_exception` or `capture_exception`, the directory is validated upfront (checking path existence, directory type, presence of YAML files, schema integrity, and identifier collisions). If validation fails, `KnowledgeEntryError` is raised immediately.

```python
from pathlib import Path
from investigator.sdk import KnowledgeEntryError, investigate_exception

try:
    result = investigate_exception(exc, kb_dir=Path("./invalid_or_missing_kb"))
except KnowledgeEntryError as err:
    print(f"Custom knowledge base error: {err}")
```

---

### 5. SDK Reference & Invariants

| Component | Signature / Usage | Description |
| :--- | :--- | :--- |
| **`investigate_exception`** | `investigate_exception(exc, *, kb_dir=None) -> InvestigationResult` | Pure function returning structured diagnosis. Propagates `KnowledgeEntryError` on invalid `kb_dir`. |
| **`capture_exception`** | `@capture_exception`<br>`with capture_exception(*, reraise=True, sink=None, kb_dir=None):` | Context manager & decorator. Formats diagnosis to `sys.stderr` by default and preserves traceback on re-raise. |
| **`KnowledgeEntryError`** | `from investigator.sdk import KnowledgeEntryError` | Re-exported exception raised when custom knowledge base fails schema or collision validation. |

#### Product Invariants
- **Non-Interference with System Signals:** `KeyboardInterrupt` and `SystemExit` are **never** caught or intercepted by `capture_exception`; they pass through cleanly.
- **Sink Customization:** Supplying a callable `sink` bypasses `sys.stderr` emission entirely, directing the `InvestigationResult` directly into your logging or telemetry pipeline.

---

## Architecture & Codebase Layout

```text
src/investigator/
├── __init__.py             # Public API exports (investigate, InvestigationResult, etc.)
├── cli.py                  # CLI application and Typer command wiring
├── cli_format.py           # Terminal output presentation (88-col wrap, hanging indents)
├── error_parser.py         # Traceback parser extracting structured ParsedError
├── investigation.py        # Investigation dataclass
├── investigation_result.py # Result envelope and status invariants
├── investigator.py         # Pipeline orchestration: parse → lookup → result
├── io_utils.py             # Multiline stdin capture (interactive TTY & pipe support)
├── knowledge_loader.py     # YAML loader, schema validation, and collision detection
├── knowledge_lookup.py     # In-memory index and lookup engine
├── sdk.py                  # Programmatic Python SDK (investigate_exception, capture_exception)
└── knowledge/              # Built-in curated YAML knowledge entries
```

### Layering Boundary

The codebase enforces strict, unidirectional module layering:
- **CLI Layer:** [`cli.py`](src/investigator/cli.py) handles terminal I/O, invokes the loader for upfront `--kb-dir` validation, and triggers the investigator.
- **SDK Layer:** [`sdk.py`](src/investigator/sdk.py) provides programmatic developer integration (`investigate_exception`, `capture_exception`).
- **Orchestration Layer:** [`investigator.py`](src/investigator/investigator.py) coordinates parsing and lookup.
- **Lookup Layer:** [`knowledge_lookup.py`](src/investigator/knowledge_lookup.py) manages in-memory indexing and query matching.
- **Loader Layer:** [`knowledge_loader.py`](src/investigator/knowledge_loader.py) reads YAML, validates schema constraints, and detects collisions.

---

## Development & Testing

### Running Tests

Run the full pytest suite with coverage analysis:

```bash
pytest --cov=investigator --cov-report=term-missing
```

### Current Status

- **238 passed tests**
- **100% statement coverage** across all source files
- Strict test isolation (cache resets, interactive TTY simulation, edge-case and adversarial checks)

---

## License

This project is licensed under the [MIT License](LICENSE).
