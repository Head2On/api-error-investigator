# AI API Error Investigator

A CLI developer tool that investigates API and database errors by parsing
tracebacks, matching them against a curated knowledge base, and returning a
structured, deterministic diagnosis.

**Status:** Early development (Chunk A complete). Deterministic engine works
end-to-end. AI-assisted investigation is planned for a later chunk.

## Why

When an AI-powered API fails in production, the developer is stuck with a
raw traceback and no fast path to a fix. Generic LLM wrappers produce vague
answers. This tool takes a different approach:

- **Deterministic first.** A curated knowledge base handles known errors
  instantly, offline, with zero cost.
- **AI second.** AI is only invoked when the knowledge base has no answer —
  and only when the user opts in.
- **Honest by design.** Unknown errors return "I don't know." The tool never
  fabricates a diagnosis.

## How it works

```
raw error
    ↓
parse_error()          — extract structured fields from the traceback
    ↓
ParsedError
    ↓
lookup()               — match against the knowledge base
    ↓
KnowledgeEntry  |  None
```

## Installation

```bash
git clone https://github.com/<your-username>/ai-api-error-investigator.git
cd ai-api-error-investigator
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e .
```

## Usage

```bash
ai-investigate --help
ai-investigate investigate
```

Paste your traceback when prompted, type `DONE` on a new line, and press Enter.

## Project structure

```
src/investigator/
├── cli.py                 # CLI commands (Typer)
├── io_utils.py            # input capture + display helpers
├── error_parser.py        # traceback → structured ParsedError
├── knowledge_loader.py    # load + validate YAML KB entries
├── knowledge_lookup.py    # lookup(parsed_error) → entry | None
└── knowledge/             # knowledge base (one YAML file per error)
    ├── sqlalchemy_integrity_error.yaml
    ├── sqlalchemy_operational_error.yaml
    ├── sqlalchemy_data_error.yaml
    ├── python_value_error.yaml
    └── python_key_error.yaml

tests/                     # pytest suite (24 tests, all passing)
```

## Development

```bash
pytest tests/ -v
```

## Roadmap

- **Chunk A** — Core deterministic investigator ✅
- **Chunk B** — AI investigation engine (opt-in escalation)
- **Chunk C** — SDK + FastAPI middleware
- **Chunk D–G** — Backend, infrastructure, production hardening, release

## License

MIT