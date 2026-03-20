# Couple Date Planner

Python-first Streamlit app for saving editable couple context and generating thoughtful date ideas using an LLM.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- OpenAI-compatible API key (`OPENAI_API_KEY`)

## Setup (uv only)

```bash
uv sync
```

## Run

```bash
uv run streamlit run src/couple_date_planner/app.py
```

## Test

```bash
uv run pytest
```

## Environment

Set environment variables in shell, or use `.streamlit/secrets.toml`.

### Option A: shell env

```bash
export OPENAI_API_KEY="your_key"
export OPENAI_MODEL="gpt-4o-mini"  # optional
export OPENAI_BASE_URL="https://api.openai.com/v1"  # optional
```

### Option B: `.streamlit/secrets.toml`

```toml
OPENAI_API_KEY = "your_key"
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_BASE_URL = "https://api.openai.com/v1"
```

The app reads from environment variables; Streamlit secrets are exposed as env vars at runtime.

## Privacy controls

- Each text section has:
  - **Include when generating** toggle.
  - **Never send to model** toggle (always wins).
- Only selected text is sent to the LLM.

## Guardrails

- Max profile text sent to model is capped (`MAX_CONTEXT_CHARS` in `generate.py`).
- Ideas per request are capped in UI and model settings.
- Defaults use a cost-efficient model (`gpt-4o-mini`) unless overridden.
- Recent idea fingerprints are tracked to reduce immediate repeats.

## Manual QA checklist

- Save profile text, restart app, confirm persistence.
- Mark a section as never-send and verify generation still works without that section.
- Change comfort/cost/drinking settings and confirm output style shifts.
- Trigger an error scenario (invalid key, timeout) and confirm clear retry messaging.
