"""국가법령정보센터(NLIC) API wrapper with in-memory cache.

Implemented features:
- search_law
- get_article
- get_version
- validate_article
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import urlopen


@dataclass(frozen=True)
class CacheEntry:
    value: Dict[str, Any]
    expires_at: float


class NlicApiWrapper:
    """Thin API wrapper for NLIC endpoints with TTL cache support."""

    DEFAULT_BASE_URL = "https://www.law.go.kr/DRF/lawSearch.do"

    def __init__(
        self,
        oc: str = "orph3vs_mcpserver",
        base_url: str = DEFAULT_BASE_URL,
        cache_ttl_seconds: int = 300,
    ) -> None:
        if not oc:
            raise ValueError("oc is required")
        if cache_ttl_seconds <= 0:
            raise ValueError("cache_ttl_seconds must be positive")

        self.oc = oc
        self.base_url = base_url
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], CacheEntry] = {}

    def _cache_key(self, action: str, params: Dict[str, Any]) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
        normalized = tuple(sorted((k, str(v)) for k, v in params.items()))
        return action, normalized

    def _get_cached(self, key: Tuple[str, Tuple[Tuple[str, str], ...]]) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() > entry.expires_at:
            self._cache.pop(key, None)
            return None
        return entry.value

    def _set_cached(self, key: Tuple[str, Tuple[Tuple[str, str], ...]], value: Dict[str, Any]) -> None:
        self._cache[key] = CacheEntry(
            value=value,
            expires_at=time.time() + self.cache_ttl_seconds,
        )

    def _request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = urlencode(params)
        url = f"{self.base_url}?{query}"
        with urlopen(url, timeout=15) as response:  # nosec B310
            payload = response.read().decode("utf-8")
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            # NLIC may return XML/text depending on API options.
            return {"raw": payload}

    def _call(self, action: str, extra_params: Dict[str, Any]) -> Dict[str, Any]:
        params = {"OC": self.oc, "target": action, "type": "JSON"}
        params.update(extra_params)

        key = self._cache_key(action=action, params=params)
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        result = self._request(params)
        self._set_cached(key, result)
        return result

    def search_law(self, query: str) -> Dict[str, Any]:
        if not query.strip():
            raise ValueError("query must not be empty")
        return self._call("law", {"query": query.strip()})

    def get_article(self, law_id: str, article_no: str) -> Dict[str, Any]:
        if not law_id.strip() or not article_no.strip():
            raise ValueError("law_id and article_no are required")
        return self._call(
            "law",
            {
                "ID": law_id.strip(),
                "JO": article_no.strip(),
            },
        )

    def get_version(self, law_id: str) -> Dict[str, Any]:
        if not law_id.strip():
            raise ValueError("law_id is required")
        return self._call("history", {"ID": law_id.strip()})

    def validate_article(self, law_id: str, article_no: str) -> Dict[str, Any]:
        """Validate article existence using get_article result."""
        article_result = self.get_article(law_id=law_id, article_no=article_no)

        # conservative validation: only true when API result clearly has non-empty content.
        text_candidates = [
            article_result.get("조문내용"),
            article_result.get("조문"),
            article_result.get("article"),
            article_result.get("raw"),
        ]
        found = any(bool(v) for v in text_candidates)

        return {
            "law_id": law_id,
            "article_no": article_no,
            "is_valid": found,
            "source": article_result,
        }

    def clear_cache(self) -> None:
        self._cache.clear()
