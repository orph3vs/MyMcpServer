"""Context builder for real-world request ingestion.

Builds normalized context text from optional fields instead of requiring users to type context manually.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_context(
    explicit_context: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    history: Optional[List[str]] = None,
) -> Optional[str]:
    parts: List[str] = []

    if explicit_context and explicit_context.strip():
        parts.append(f"[EXPLICIT_CONTEXT]\n{explicit_context.strip()}")

    if metadata:
        normalized = {k: v for k, v in metadata.items() if v is not None and str(v).strip()}
        if normalized:
            meta_lines = [f"- {k}: {v}" for k, v in normalized.items()]
            parts.append("[METADATA]\n" + "\n".join(meta_lines))

    if history:
        cleaned = [h.strip() for h in history if isinstance(h, str) and h.strip()]
        if cleaned:
            hist_lines = [f"{i+1}. {line}" for i, line in enumerate(cleaned[-5:])]
            parts.append("[RECENT_HISTORY]\n" + "\n".join(hist_lines))

    if not parts:
        return None
    return "\n\n".join(parts)
