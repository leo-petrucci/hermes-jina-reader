from __future__ import annotations

import sys
from typing import Any, Dict, List, Tuple

from agent.web_search_provider import WebSearchProvider, get_provider_env


def _parse_reader_body(raw: str) -> Tuple[str, str]:
    """Parse Jina Reader text body into (title, content).

    Never raises: falls back to ("", raw.strip()) on unrecognized format.
    """
    try:
        if not raw:
            return "", ""
        lines = raw.split("\n")
        title = ""
        if lines and lines[0].startswith("Title:"):
            title = lines[0][len("Title:"):].strip()
        # Default graceful fallback: whole body stripped.
        content = raw.strip()
        for i, line in enumerate(lines):
            if line.strip() == "Markdown Content:":
                content = "\n".join(lines[i + 1:]).strip()
                break
        return title, content
    except Exception as exc:  # narrow fallback: never raise on bad input
        print(f"[jina-reader] parse fallback: {exc}", file=sys.stderr)
        try:
            return "", (raw or "").strip()
        except Exception:
            return "", ""


class JinaReaderProvider(WebSearchProvider):
    """Extract-only provider backed by a self-hosted Jina Reader instance."""

    @property
    def name(self) -> str:
        return "jina-reader"

    @property
    def display_name(self) -> str:
        return "Jina Reader (self-hosted)"

    def is_available(self) -> bool:
        val = get_provider_env("JINA_READER_URL")
        return bool(val.strip()) if val else False

    def supports_search(self) -> bool:
        return False

    def supports_extract(self) -> bool:
        return True

    def extract(self, urls: List[str], **kwargs: Any) -> List[Dict[str, Any]]:
        import httpx

        base_url = get_provider_env("JINA_READER_URL") or "http://localhost:3001"
        base_url = base_url.rstrip("/")
        results: List[Dict[str, Any]] = []

        for url in urls:
            try:
                resp = httpx.get(f"{base_url}/{url}", timeout=30, follow_redirects=True)
                resp.raise_for_status()
                raw = resp.text
            except httpx.HTTPError as exc:
                print(f"[jina-reader] fetch failed for {url}: {exc}", file=sys.stderr)
                results.append({
                    "url": url,
                    "title": "",
                    "content": "",
                    "raw_content": "",
                    "error": str(exc),
                })
                continue

            try:
                title, content = _parse_reader_body(raw)
            except Exception as exc:  # narrow fallback for parse errors
                print(f"[jina-reader] parse failed for {url}: {exc}", file=sys.stderr)
                results.append({
                    "url": url,
                    "title": "",
                    "content": "",
                    "raw_content": raw if isinstance(raw, str) else "",
                    "error": str(exc),
                })
                continue

            results.append({
                "url": url,
                "title": title,
                "content": content,
                "raw_content": raw,
            })

        return results
