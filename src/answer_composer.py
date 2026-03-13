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

    _ARTICLE_CATEGORY_KEYWORDS = {
        "purpose": ("목적",),
        "definition": ("정의",),
        "scope": ("적용범위", "적용 대상", "적용례"),
        "duty": ("책무", "의무"),
        "prohibition": ("금지행위", "금지", "제한"),
        "sanction": ("벌칙", "과태료", "과징금"),
    }
    _QUESTION_INTENT_KEYWORDS = {
        "difference": ("차이", "구분", "비교", "어떻게 다른", "무슨 차이"),
        "requirements": ("요건", "조건", "기준", "성립", "충족"),
        "procedure": ("절차", "방법", "순서", "어떻게 해야", "어떻게 하나"),
        "illegality": ("위법", "불법", "가능한지", "문제되는지", "허용되는지", "판단"),
        "explain": ("설명", "해설", "의미", "알려줘", "알려 주세요", "알려줘요", "뭐야", "무엇인가"),
    }

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
        category = AnswerComposer._article_category(article_title)
        if category == "purpose":
            return (
                f"쉽게 말하면, 이 조항은 {law_name}이 왜 존재하는지 밝히는 규정으로 "
                "개인의 권리와 보호 가치가 이 법의 출발점이라는 뜻입니다."
            )
        if category == "definition":
            return (
                f"쉽게 말하면, 이 조항은 {law_name}에서 쓰는 핵심 용어의 뜻을 정해 "
                "뒤에 나오는 규정들을 해석하는 기준을 세우는 역할을 합니다."
            )
        if category == "scope":
            return (
                f"쉽게 말하면, {article_no}는 {law_name}이 누구에게, 어떤 경우에 적용되는지 정해 "
                "법의 적용 범위를 분명하게 하는 조문입니다."
            )
        if category == "duty":
            return (
                f"쉽게 말하면, {article_no}는 {law_name}상 관련 주체가 무엇을 해야 하는지 정한 조문으로 "
                "준수해야 할 기본 책임을 보여줍니다."
            )
        if category == "prohibition":
            return (
                f"쉽게 말하면, {article_no}는 {law_name}상 해서는 안 되는 행위나 제한되는 행위를 정한 조문으로 "
                "허용 범위의 바깥선을 그어주는 역할을 합니다."
            )
        if category == "sanction":
            return (
                f"쉽게 말하면, {article_no}는 {law_name} 위반 시 책임이나 제재 기준을 정한 조문이라 "
                "실제 사실관계와 적용 요건을 함께 따져봐야 합니다."
            )
        return (
            f"쉽게 말하면, {article_no}는 {law_name}에서 해당 주제에 관한 기본 기준이나 방향을 직접 정한 조문입니다."
        )

    @classmethod
    def _question_intent(cls, user_query: str) -> str:
        normalized = cls._clean_text(user_query)
        ordered_intents = ("difference", "illegality", "requirements", "procedure", "explain")
        for intent in ordered_intents:
            keywords = cls._QUESTION_INTENT_KEYWORDS[intent]
            if any(keyword in normalized for keyword in keywords):
                return intent
        return "explain"

    @classmethod
    def _lead_sentence(cls, user_query: str, law_name: str, article_no: str, article_title: Optional[str]) -> str:
        intent = cls._question_intent(user_query)
        label = article_title or "해당 조문"

        if intent == "difference":
            return f"{law_name} {article_no}는 {label}에 관한 규정으로, 비교 질문의 기준점이 되는 조문입니다."
        if intent == "requirements":
            return f"{law_name} {article_no}는 {label}에 관한 규정으로, 적용 요건이나 판단 기준을 이해할 때 출발점이 되는 조문입니다."
        if intent == "procedure":
            return f"{law_name} {article_no}는 {label}에 관한 규정으로, 절차나 처리 순서를 이해하기 위한 기준 조문입니다."
        if intent == "illegality":
            return f"{law_name} {article_no}는 {label}에 관한 규정으로, 위법 여부를 판단할 때 참고해야 할 기준 중 하나입니다."
        return f"{law_name} {article_no}는 {label}에 관한 규정입니다."

    @classmethod
    def _tail_guidance(cls, user_query: str) -> Optional[str]:
        intent = cls._question_intent(user_query)
        if intent == "difference":
            return "필요하시면 비교 대상 조문이나 다른 법률과의 차이까지 이어서 정리해드릴 수 있습니다."
        if intent == "requirements":
            return "필요하시면 이 조문이 실제로 적용되기 위한 요건을 항목별로 나눠 설명해드릴 수 있습니다."
        if intent == "procedure":
            return "필요하시면 이 조문과 연결되는 절차를 단계별로 정리해드릴 수 있습니다."
        if intent == "illegality":
            return "다만 위법 여부는 조문 문구만으로 단정하기 어렵고, 구체적 사실관계와 예외 규정을 함께 확인해야 합니다."
        return None

    @staticmethod
    def _build_risk_notice(risk_level: str, article_title: Optional[str]) -> Optional[str]:
        if risk_level != "HIGH":
            return None
        if AnswerComposer._article_category(article_title) == "sanction":
            return "이 조항은 제재와 직접 연결될 수 있어, 실제 적용 여부는 사실관계와 요건 충족 여부를 개별적으로 검토하는 것이 안전합니다."
        return "이 질문은 해석상 주의가 필요한 편이라, 실제 적용 시에는 관련 조문과 사실관계를 추가로 확인하는 것이 안전합니다."

    @classmethod
    def _article_category(cls, article_title: Optional[str]) -> Optional[str]:
        if not article_title:
            return None
        normalized = cls._clean_text(article_title)
        for category, keywords in cls._ARTICLE_CATEGORY_KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                return category
        return None

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
            lead_sentence = self._lead_sentence(composition_input.user_query, law_name, article_no, article_title)
            default_lead = f"{law_name} {article_no}는 {article_title or '해당 조문'}에 관한 규정입니다."
            if composition_input.user_query and self._question_intent(composition_input.user_query) == "explain":
                lead_sentence = default_lead

            lines = [
                lead_sentence,
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

            tail_guidance = self._tail_guidance(composition_input.user_query)
            if tail_guidance:
                lines.extend(["", tail_guidance])

            return "\n".join(lines).strip()

        if law_name:
            lines = [f"질문과 가장 관련된 법령은 {law_name}입니다."]
            if version_fields.get("시행일자"):
                lines.append(f"현재 확인된 시행일자는 {version_fields['시행일자']}입니다.")
            else:
                lines.append("현재 확보한 정보만으로는 시행일자를 특정하지 못했습니다.")
            lines.append("다만 현재 질문에 대응하는 조문 본문까지는 확인되지 않아, 법령명과 버전 정보를 기준으로 먼저 안내드립니다.")
            if composition_input.risk_level == "HIGH":
                lines.append("질문에 위법성, 조사 대응, 제재 여부 같은 요소가 포함되어 있어 현재 정보만으로 확정적으로 단정하기보다, 구체적 사실관계와 관련 조문을 함께 확인하는 것이 안전합니다.")
            else:
                lines.append("필요하시면 관련 조문이나 정의 조항을 추가로 특정해서 더 구체적으로 설명드릴 수 있습니다.")
            tail_guidance = self._tail_guidance(composition_input.user_query)
            if tail_guidance and tail_guidance not in lines:
                lines.append(tail_guidance)
            return "\n".join(lines).strip()

        if composition_input.prompt_payload.get("system") and composition_input.fallback_answer.strip():
            return self._truncate_text(composition_input.fallback_answer, max_chars=400)
        return "관련 법령 정보를 확인했지만, 현재 답변을 구성할 근거가 부족합니다."
