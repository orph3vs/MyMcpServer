"""Grounded answer composition for legal Q&A responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AnswerCompositionInput:
    user_query: str
    prompt_payload: Dict[str, str]
    law_enrichment: Dict[str, Any]
    risk_level: str
    fallback_answer: str


class AnswerComposer:
    """Compose user-facing legal answers from grounded law enrichment data."""

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    @staticmethod
    def _extract_article_title(article_text: str) -> Optional[str]:
        match = re.search(r"제\s*\d+\s*조(?:의\s*\d+)?\(([^)]+)\)", article_text)
        if match:
            return AnswerComposer._clean_text(match.group(1))
        return None

    @staticmethod
    def _truncate_text(text: str, max_chars: int = 180) -> str:
        compact = AnswerComposer._clean_text(text)
        if len(compact) <= max_chars:
            return compact
        return compact[: max_chars - 3].rstrip() + "..."

    @staticmethod
    def _build_plain_explanation(article_title: Optional[str], law_name: str, article_no: str) -> str:
        if article_title == "목적":
            return (
                f"쉽게 말하면, 이 조항은 {law_name}이 왜 존재하는지 밝히는 규정으로 "
                "개인의 권리와 보호 가치가 이 법의 출발점이라는 뜻입니다."
            )
        if article_title == "정의":
            return (
                f"쉽게 말하면, 이 조항은 {law_name}에서 쓰는 핵심 용어의 뜻을 정해 "
                "뒤에 나오는 규정들을 해석하는 기준을 세우는 역할을 합니다."
            )
        if article_title and any(keyword in article_title for keyword in ("벌칙", "과태료", "과징금")):
            return (
                f"쉽게 말하면, {article_no}는 {law_name} 위반 시 책임이나 제재 기준을 정한 조문이라 "
                "실제 사실관계와 적용 요건을 함께 따져봐야 합니다."
            )
        return (
            f"쉽게 말하면, {article_no}는 {law_name}에서 해당 주제에 관한 기본 기준이나 방향을 직접 정한 조문입니다."
        )

    @staticmethod
    def _build_risk_notice(risk_level: str, article_title: Optional[str]) -> Optional[str]:
        if risk_level != "HIGH":
            return None
        if article_title and any(keyword in article_title for keyword in ("벌칙", "과태료", "과징금")):
            return "이 조항은 제재와 직접 연결될 수 있어, 실제 적용 여부는 사실관계와 요건 충족 여부를 개별적으로 검토하는 것이 안전합니다."
        return "이 질문은 해석상 주의가 필요한 편이라, 실제 적용 시에는 관련 조문과 사실관계를 추가로 확인하는 것이 안전합니다."

    def compose(self, composition_input: AnswerCompositionInput) -> str:
        law_enrichment = composition_input.law_enrichment
        primary_law = law_enrichment.get("primary_law") or {}
        version = law_enrichment.get("version") or {}
        version_fields = version.get("version_fields") or {}
        article = law_enrichment.get("article") or {}

        law_name = self._clean_text(str(primary_law.get("law_name", "")))
        article_text = self._clean_text(str(article.get("article_text", "")))
        article_no = self._clean_text(str(article.get("article_no", "")))
        article_title = self._extract_article_title(article_text) if article_text else None

        if law_name and article.get("found") and article_text and article_no:
            lines = [
                f"{law_name} {article_no}는 {article_title or '해당 조문'}에 관한 규정입니다.",
                "",
                "현재 확인된 조문은 다음과 같습니다.",
                article_text,
                "",
                self._build_plain_explanation(article_title, law_name, article_no),
            ]

            if version_fields.get("시행일자"):
                lines.extend(["", f"기준 정보: 현재 확인된 시행일자는 {version_fields['시행일자']}입니다."])

            risk_notice = self._build_risk_notice(composition_input.risk_level, article_title)
            if risk_notice:
                lines.extend(["", risk_notice])

            return "\n".join(lines).strip()

        if law_name:
            lines = [f"질문과 가장 관련된 법령은 {law_name}입니다."]
            if version_fields.get("시행일자"):
                lines.append(f"현재 확인된 시행일자는 {version_fields['시행일자']}입니다.")
            lines.append("다만 현재 질문에 대응하는 조문 본문까지는 확인되지 않아, 법령명과 버전 정보를 기준으로 먼저 안내드립니다.")
            if composition_input.risk_level == "HIGH":
                lines.append("질문에 위법성, 조사 대응, 제재 여부 같은 요소가 포함되어 있어 실제 판단에는 구체적 사실관계와 관련 조문을 함께 확인하는 것이 안전합니다.")
            else:
                lines.append("필요하시면 관련 조문이나 정의 조항을 추가로 특정해서 더 구체적으로 설명드릴 수 있습니다.")
            return "\n".join(lines).strip()

        if composition_input.prompt_payload.get("system") and composition_input.fallback_answer.strip():
            return self._truncate_text(composition_input.fallback_answer, max_chars=400)
        return "관련 법령 정보를 확인했지만, 현재 답변을 구성할 근거가 부족합니다."
