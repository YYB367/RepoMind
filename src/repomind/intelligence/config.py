"""Small literal .env reader: no shell evaluation, no interpolation, no secrets in diagnostics."""

import os
import math
import importlib.metadata
from pathlib import Path
import re


def load_env_file(path: str | Path = ".env") -> list[str]:
    path = Path(path)
    if not path.exists():
        return []
    parsed = {}
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"{path}:{number}: expected NAME=value (values are not executed)")
        if key in parsed:
            raise ValueError(f"{path}:{number}: duplicate configuration name {key}")
        if value.startswith(("'", '"')):
            quote = value[0]
            if len(value) < 2 or value[-1] != quote:
                raise ValueError(f"{path}:{number}: unmatched configuration quote")
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        parsed[key] = value
    loaded = []
    for key, value in parsed.items():
        if key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def configuration_status() -> dict:
    """Local status only. No network call and no key prefix, length, or value."""
    load_env_file()
    installed = {}
    for name in ("mem0ai", "qdrant-client", "openai", "langfuse"):
        try:
            installed[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed[name] = None
    return {
        "env_file": str(Path(".env").resolve()),
        "env_file_exists": Path(".env").is_file(),
        "provider": os.getenv("REPOMIND_PROVIDER", "openai"),
        "chat_model": os.getenv("REPOMIND_CHAT_MODEL", ""),
        "embedding_provider": os.getenv("REPOMIND_EMBEDDING_PROVIDER", "openai-compatible"),
        "embedding_model": os.getenv("REPOMIND_EMBEDDING_MODEL", ""),
        "chat_api_key_configured": bool(os.getenv("REPOMIND_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
                                         or os.getenv("OPENAI_API_KEY")),
        "embedding_configured": all(bool(os.getenv(key)) for key in
                                    ("REPOMIND_EMBEDDING_BASE_URL", "REPOMIND_EMBEDDING_API_KEY",
                                     "REPOMIND_EMBEDDING_MODEL")),
        "langfuse_base_url_configured": bool(os.getenv("LANGFUSE_BASE_URL")),
        "langfuse_public_key_configured": bool(os.getenv("LANGFUSE_PUBLIC_KEY")),
        "langfuse_secret_key_configured": bool(os.getenv("LANGFUSE_SECRET_KEY")),
        "installed_versions": installed,
        "network_called": False,
    }


def search_min_cosine(value: float | None = None, *, read_file: bool = True) -> float:
    if value is None:
        if read_file:
            load_env_file()
            value = float(os.getenv("REPOMIND_SEARCH_MIN_COSINE", "0.2"))
        else:
            value = 0.2
    if isinstance(value, bool) or not math.isfinite(value) or not -1 <= value <= 1:
        raise ValueError("search min_cosine must be a finite number between -1 and 1")
    return float(value)
