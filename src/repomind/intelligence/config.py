"""Small literal .env reader: no shell evaluation, no interpolation, no secrets in diagnostics."""

import os
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
        "network_called": False,
    }
