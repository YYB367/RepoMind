"""Read directory summaries and evidence through the OpenViking HTTP API."""
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from repomind.intelligence.providers import ProviderConfig, _NoRedirect, _json_loads

_SEGMENT = r"[a-z0-9][a-z0-9-]{0,47}"
_ROOT = re.compile(r"viking://resources/(?:{0}/)*{0}".format(_SEGMENT))
_ENDPOINTS = {"L0": "abstract", "L1": "overview", "L2": "read"}
_MAX_RESPONSE = 131072


class OpenVikingReader:
    def __init__(self, base_url: str, root: str, api_key: str | None = None):
        if not _ROOT.fullmatch(root):
            raise ValueError("OpenViking root must be a named viking://resources/ subtree")
        self.config = ProviderConfig(base_url=base_url, api_key=api_key, timeout_seconds=15)
        self.root = root
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def __call__(self, level: str, project: str, group: str, doc: str | None) -> str:
        segments = [project, group] + ([doc] if doc is not None else [])
        if level not in _ENDPOINTS or (level == "L2") != (doc is not None):
            raise ValueError("OpenViking read needs a valid layer and document scope")
        if any(not re.fullmatch(_SEGMENT, segment) for segment in segments):
            raise ValueError("invalid OpenViking project, group, or document ID")
        uri = self.root + "/" + "/".join(segments) + (".md" if doc is not None else "")
        url = self.config.base_url + "/api/v1/content/" + _ENDPOINTS[level] + "?" + urlencode({"uri": uri})
        headers = {"Accept": "application/json"}
        if self.config.api_key is not None:
            headers["Authorization"] = "Bearer " + self.config.api_key.get_secret_value()
        request = Request(url, headers=headers, method="GET")
        try:
            with self._opener.open(request, timeout=self.config.timeout_seconds) as response:
                body = response.read(_MAX_RESPONSE + 1)
        except HTTPError as error:
            raise ValueError(f"OpenViking content request failed with HTTP {error.code} at {level}") from None
        except (URLError, OSError):
            raise ValueError(f"OpenViking content request unavailable at {level}") from None
        if len(body) > _MAX_RESPONSE:
            raise ValueError("OpenViking response exceeds read limit")
        try:
            payload = _json_loads(body)
        except (ValueError, UnicodeError):
            raise ValueError("OpenViking returned invalid JSON") from None
        value = payload.get("result") if isinstance(payload, dict) and payload.get("status") == "ok" else None
        if not isinstance(value, str) or not value.strip() or value.startswith("[Directory overview is not generated"):
            raise ValueError(f"OpenViking did not return text for {level}")
        if value.startswith("[Abstract not generated"):
            raise ValueError("OpenViking did not return text for L0")
        return value
