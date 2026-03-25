"""AI provider factory — reads AI_PROVIDER env var and resolves with fallback chain."""

import logging
import os

from src.ai.base import AIProvider
from src.ai.local import LocalProvider

logger = logging.getLogger(__name__)

_PROVIDERS = {
    "claude":      ("src.ai.claude",           "ClaudeProvider",      "ANTHROPIC_API_KEY"),
    "openai":      ("src.ai.openai_provider",  "OpenAIProvider",      "OPENAI_API_KEY"),
    "perplexity":  ("src.ai.perplexity",       "PerplexityProvider",  "PERPLEXITY_API_KEY"),
    "local":       (None,                       None,                  None),
}


def get_provider() -> AIProvider:
    """Return the configured AI provider, falling back to LocalProvider on any error."""
    name = os.getenv("AI_PROVIDER", "local").lower()
    entry = _PROVIDERS.get(name)

    if entry is None:
        logger.warning("Unknown AI_PROVIDER '%s' — falling back to local", name)
        return LocalProvider()

    module_path, class_name, key_env = entry

    if module_path is None:
        return LocalProvider()

    if key_env and not os.getenv(key_env):
        logger.warning("%s selected but %s not set — falling back to local", name, key_env)
        return LocalProvider()

    try:
        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls()
    except Exception as exc:
        logger.warning("Failed to init %s (%s) — falling back to local", name, exc)
        return LocalProvider()
