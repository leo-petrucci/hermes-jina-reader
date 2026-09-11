from .provider import JinaReaderProvider


def register(ctx) -> None:
    """Plugin entry point — called once at load time."""
    ctx.register_web_search_provider(JinaReaderProvider())
