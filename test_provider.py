"""Unit tests for JinaReaderProvider (stdlib unittest only)."""
from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

# Ensure `agent.web_search_provider` is importable: stub if the real
# package is not on sys.path when running `python3 -m unittest discover`.
try:
    import agent.web_search_provider  # noqa: F401
except Exception:
    agent_mod = types.ModuleType("agent")
    wsp_mod = types.ModuleType("agent.web_search_provider")

    class WebSearchProvider:  # minimal stub matching contract
        pass

    def get_provider_env(name: str) -> str:
        return (os.getenv(name, "") or "").strip()

    wsp_mod.WebSearchProvider = WebSearchProvider
    wsp_mod.get_provider_env = get_provider_env
    agent_mod.web_search_provider = wsp_mod
    sys.modules["agent"] = agent_mod
    sys.modules["agent.web_search_provider"] = wsp_mod

# Ensure `httpx` is importable so provider.extract can catch httpx.HTTPError.
try:
    import httpx  # noqa: F401
    _HAS_HTTPX = True
except Exception:
    _HAS_HTTPX = False
    fake_httpx = types.ModuleType("httpx")

    class HTTPError(Exception):
        pass

    fake_httpx.HTTPError = HTTPError

    def _missing_get(*args, **kwargs):
        raise HTTPError("httpx stub: no transport")

    fake_httpx.get = _missing_get
    sys.modules["httpx"] = fake_httpx

import httpx as _httpx_mod  # real or stubbed above
import provider as provider_mod
from provider import JinaReaderProvider


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


def _make_http_error(msg: str) -> Exception:
    try:
        return _httpx_mod.HTTPError(msg)
    except Exception:
        return Exception(msg)


class TestJinaReaderProvider(unittest.TestCase):
    def test_extract_returns_one_dict_per_url(self):
        urls = ["https://a.example/", "https://b.example/"]
        bodies = {
            urls[0]: "Title: A\nMarkdown Content:\nContent A",
            urls[1]: "plain fallback body",
        }

        def fake_get(full_url, **kwargs):
            for u in urls:
                if full_url.endswith(u):
                    return FakeResponse(bodies[u])
            return FakeResponse("")

        with mock.patch.object(provider_mod, "get_provider_env", return_value="http://test.local"), \
                mock.patch.object(_httpx_mod, "get", side_effect=fake_get):
            prov = JinaReaderProvider()
            out = prov.extract(urls)

        self.assertIsInstance(out, list)
        self.assertEqual(len(out), 2)
        for item, u in zip(out, urls):
            self.assertEqual(item["url"], u)
            self.assertIn("title", item)
            self.assertIn("content", item)
            self.assertIn("raw_content", item)

    def test_parsing_title_and_markdown_marker(self):
        raw = "Title: Hello\nSome header noise\nMarkdown Content:\nHello world body"
        with mock.patch.object(provider_mod, "get_provider_env", return_value="http://test.local"), \
                mock.patch.object(_httpx_mod, "get", return_value=FakeResponse(raw)):
            out = JinaReaderProvider().extract(["https://example.com"])

        self.assertEqual(len(out), 1)
        item = out[0]
        self.assertEqual(item["title"], "Hello")
        self.assertEqual(item["content"], "Hello world body")
        self.assertNotIn("error", item)

    def test_one_failing_url_yields_error_while_other_succeeds(self):
        good = "https://good.example/"
        bad = "https://bad.example/"
        err = _make_http_error("boom")

        def fake_get(full_url, **kwargs):
            if full_url.endswith(good):
                return FakeResponse("Title: Good\nMarkdown Content:\nGood body")
            raise err

        with mock.patch.object(provider_mod, "get_provider_env", return_value="http://test.local"), \
                mock.patch.object(_httpx_mod, "get", side_effect=fake_get):
            out = JinaReaderProvider().extract([good, bad])

        self.assertEqual(len(out), 2)
        by_url = {d["url"]: d for d in out}
        # Good URL still succeeds with no error key.
        self.assertNotIn("error", by_url[good])
        self.assertEqual(by_url[good]["title"], "Good")
        # Failing URL preserves url and carries error key.
        self.assertIn("error", by_url[bad])
        self.assertEqual(by_url[bad]["url"], bad)
        self.assertTrue(by_url[bad]["error"])

    def test_parse_fallback_never_raises(self):
        title, content = provider_mod._parse_reader_body("just some text without headers")
        self.assertEqual(title, "")
        self.assertEqual(content, "just some text without headers")


if __name__ == "__main__":
    unittest.main()
