"""Prompt loader for MCP request-time prompt composition.

This module separates system and orchestration prompts into versioned config files,
combines them automatically per request, and exposes lightweight prompt-policy
extraction so downstream modules can apply the prompt rules deterministically.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PromptBundle:
    version: str
    system_prompt: str
    orchestration_prompt: str

    def combined(self) -> str:
        return (
            "[SYSTEM PROMPT]\n"
            f"{self.system_prompt.strip()}\n\n"
            "[ORCHESTRATION PROMPT]\n"
            f"{self.orchestration_prompt.strip()}"
        )


class PromptLoader:
    """Loads versioned prompt configs and composes request prompt text."""

    def __init__(
        self,
        manifest_path: str | Path = "config/prompts/manifest.json",
    ) -> None:
        self.manifest_path = Path(manifest_path)
        self._lock = RLock()
        self._bundle_cache: Dict[str, PromptBundle] = {}

    def _read_manifest(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Prompt manifest not found: {self.manifest_path}")

        with self.manifest_path.open("r", encoding="utf-8") as f:
            manifest = json.load(f)

        if "default_version" not in manifest or "versions" not in manifest:
            raise ValueError("Invalid manifest: requires 'default_version' and 'versions'")

        return manifest

    def get_bundle(self, version: Optional[str] = None) -> PromptBundle:
        """Load a specific prompt version or use manifest default."""
        with self._lock:
            manifest = self._read_manifest()
            selected = version or manifest["default_version"]

            if selected in self._bundle_cache:
                return self._bundle_cache[selected]

            versions = manifest["versions"]
            if selected not in versions:
                raise KeyError(f"Prompt version not found: {selected}")

            meta = versions[selected]
            system_path = Path(meta["system_prompt"])
            orchestration_path = Path(meta["orchestration_prompt"])

            system_prompt = system_path.read_text(encoding="utf-8")
            orchestration_prompt = orchestration_path.read_text(encoding="utf-8")

            bundle = PromptBundle(
                version=selected,
                system_prompt=system_prompt,
                orchestration_prompt=orchestration_prompt,
            )
            self._bundle_cache[selected] = bundle
            return bundle

    def build_request_prompt(
        self,
        user_query: str,
        version: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Dict[str, str]:
        """Automatically combine prompts per request.

        Returns a payload that can be sent to an LLM caller.
        """
        bundle = self.get_bundle(version=version)
        combined_prompt = bundle.combined()

        user_part = user_query.strip()
        if context:
            user_part = f"[CONTEXT]\n{context.strip()}\n\n[USER QUERY]\n{user_part}"

        return {
            "prompt_version": bundle.version,
            "system": combined_prompt,
            "user": user_part,
        }


@dataclass(frozen=True)
class PromptPolicy:
    grounded_only: bool
    suppress_unsupported_claims: bool
    avoid_generalization: bool
    require_confirmation_when_unclear: bool
    require_evidence_mapping: bool
    prefer_multi_agent_for_risky_queries: bool

    def as_dict(self) -> Dict[str, bool]:
        return asdict(self)


_default_loader = PromptLoader()


def build_request_prompt(
    user_query: str,
    version: Optional[str] = None,
    context: Optional[str] = None,
) -> Dict[str, str]:
    """Module-level helper for convenient request-time auto composition."""
    return _default_loader.build_request_prompt(
        user_query=user_query,
        version=version,
        context=context,
    )


def extract_prompt_policy(prompt_payload: Dict[str, str]) -> PromptPolicy:
    combined = " ".join(
        part.strip() for part in (prompt_payload.get("system", ""), prompt_payload.get("user", "")) if part
    )
    lowered = combined.lower()
    return PromptPolicy(
        grounded_only=("법령 원문 근거" in combined) or ("grounded" in lowered),
        suppress_unsupported_claims=("근거가 없는 문장" in combined) or ("unsupported" in lowered),
        avoid_generalization=("일반화" in combined) or ("generalization" in lowered),
        require_confirmation_when_unclear=("확인 필요" in combined) or ("불명확" in combined),
        require_evidence_mapping=("근거-주장 매핑" in combined) or ("evidence" in lowered),
        prefer_multi_agent_for_risky_queries=("자동 고위험" in combined) or ("multi-agent" in lowered),
    )
