# scripts/ — LEGACY (Phase 0)

> **This directory is no longer the canonical entry point for Pensieve.**
>
> It was the Phase 0 PowerShell prototype that proved the enrichment
> quality before the Python `pensieve` package was built (2026-05-28).
> It is kept here only for historical reference and for anyone who wants
> to read the original implementation.

## Use this instead

```powershell
# one-time setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]

# canonical entry points
pensieve init          # verify config
pensieve sync          # pull, enrich, persist
pensieve status        # inspect the store
pensieve serve         # launch dashboard at http://localhost:8765
```

See `README.md` and `AGENTS.md` at the repo root for the current
architecture.

## What's in here

| File | What it was | Replaced by |
|---|---|---|
| `Enrich-Memories.ps1` | Phase 0 enrichment pipeline against `data/samples.json` | `pensieve sync --source sample_file` |
| `Test-AzureOpenAI.ps1` | Sanity check for the Azure OpenAI auth path | `pensieve init` + first `pensieve sync` |
| `lib/Invoke-AzureOpenAI.ps1` | REST wrapper for Azure OpenAI chat (handles `max_completion_tokens` quirk for gpt-5/o1/o3/o4) | `pensieve/enrichment/llm_client.py::_uses_max_completion_tokens` |
| `lib/Load-DotEnv.ps1` | Tiny `.env` loader (subset of python-dotenv semantics) | `python-dotenv` package via `pydantic-settings` in `pensieve/config.py` |

These files are not maintained. Bug fixes and feature work happen in
the Python package only.
