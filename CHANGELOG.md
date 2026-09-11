# Changelog

## 1.1.0
- Adopt shared `get_provider_env` from `agent.web_search_provider`; removed custom `_get_env` helper and unused `import os`.
- Scoped error handling: catch `httpx.HTTPError` as the primary per-URL failure path with `print(..., file=sys.stderr)` logging; kept one narrow fallback `except` for parse errors that also yields a per-URL `{url, title:'', content:'', raw_content:'', error:str}` item and never raises.
- Added `_parse_reader_body(raw)` helper with header-format fallback: extracts `Title:` from first line, content after a stripped `Markdown Content:` marker line, else `raw.strip()`; never raises on unrecognized format.
- Added `test_provider.py` (stdlib `unittest` only, runnable via `python3 -m unittest discover -v`) covering per-URL result count, title/marker parsing, and mixed success/failure handling.
