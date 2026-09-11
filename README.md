# hermes-jina-reader

A [Hermes Agent](https://hermes-agent.nousresearch.com/docs) web provider plugin that
routes `web_extract` through a **self-hosted [Jina Reader](https://github.com/jina-ai/reader)**
instance instead of a cloud extraction API. No per-page bills, no rate limits —
it works great alongside the self-hosted Docker setup below, including on a
Raspberry Pi.

## How it works

Hermes resolves `web.extract_backend: jina-reader` to `JinaReaderProvider`
(`provider.py`), which calls your local Reader at `GET <JINA_READER_URL>/<url>`
and returns the markdown (`Title:` / `Markdown Content:` headers parsed,
graceful fallback to the raw body if the format ever changes). It is an
extract-only provider (`supports_search()` is `False`), so pair it with any
search backend (e.g. Brave).

## Prerequisites

- Hermes Agent with the `web` toolset enabled
- A running Jina Reader — self-hosted Docker (recommended) or any compatible endpoint
- Python deps used by the plugin: `httpx` (tests are stdlib-only)

## Self-hosted Jina Reader (Docker)

Upstream repo: <https://github.com/jina-ai/reader> (prebuilt image
`ghcr.io/jina-ai/reader:oss`, bundles headless Chrome + LibreOffice).

Minimal start:

```bash
docker run -d --name jina-reader --restart unless-stopped -p 3001:8081 ghcr.io/jina-ai/reader:oss
curl -s http://localhost:3001/https://example.com | head -20
```

With optional MinIO cache (full compose):

```yaml
services:
  reader:
    image: ghcr.io/jina-ai/reader:oss
    ports:
      - "3000:8080"   # h2c (HTTP/2)
      - "3001:8081"   # HTTP/1.1 (curl-friendly)
    environment:
      GCP_STORAGE_ENDPOINT: http://minio:9000
      GCP_STORAGE_BUCKET: reader-cache
      GCP_STORAGE_ACCESS_KEY: minio
      GCP_STORAGE_SECRET_KEY: minio123
    depends_on:
      minio:
        condition: service_healthy
    restart: unless-stopped
  minio:
    image: minio/minio
    ports: ["9001:9001", "9000:9000"]
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio123
    volumes: [minio-data:/data/minio]
    command: server /data/minio --console-address ":9001"
    restart: unless-stopped
volumes:
  minio-data:
```

> Note: if the container ever stops responding after a host reboot, check
> `docker ps` — `restart: unless-stopped` does not always bring it back on its
> own; `docker start <reader> <minio>` fixes it.

## Install the plugin

```bash
# 1. Copy into your Hermes user plugins
mkdir -p ~/.hermes/plugins/web
cp -r /path/to/hermes-jina-reader ~/.hermes/plugins/web/jina_reader

# 2. Enable it
hermes plugins enable web/jina_reader

# 3. Point Hermes at it
hermes config set web.extract_backend jina-reader
```

Set the endpoint in `~/.hermes/.env`:

```
JINA_READER_URL=http://localhost:3001
```

Then restart whatever runs your agent so the new code loads (the gateway
*and* any WebUI/server process that imports the agent in-process — a gateway
restart alone is not enough for the latter).

## Verify

```bash
# Reader is up
curl -s http://localhost:3001/https://example.com | head -5

# Plugin resolves + extracts (from the hermes-agent checkout)
python3 -m unittest discover -v          # 4 tests, stdlib only
```

In a Hermes session, `web_extract` on any URL (e.g. `https://example.com`)
should return `{"results": [{"url", "title", "content", ...}]}` with no error.

## The contract gotcha

Hermes' provider ABC (`agent/web_search_provider.py`) requires `extract()` to
return a **list** of per-URL dicts — not `{"success": True, "data": [...]}`.
Returning the dict wrapper breaks dispatch with
`Error extracting content: 'str' object has no attribute 'get'` (it iterates
the dict's string keys and calls `.get()` on them). This repo returns the list
directly; don't "fix" it back.

## Layout

| File | What |
|------|------|
| `provider.py` | `JinaReaderProvider` + `_parse_reader_body()` helper |
| `__init__.py` | `register(ctx)` entry point |
| `plugin.yaml` | Manifest (`web-jina-reader` v1.1.0, provides `jina-reader`) |
| `test_provider.py` | 4 stdlib `unittest` tests (shape, parsing, error isolation, fallback) |
| `CHANGELOG.md` | Release notes |

## Changelog

See [CHANGELOG.md](CHANGELOG.md) — v1.1.0 adopts the shared
`get_provider_env`, scopes fetch errors to `httpx.HTTPError` with per-URL
error items, and adds the never-raise parse fallback + tests.

## License

MIT — see [LICENSE](LICENSE).
