"""Grounded answer composition for legal Q&A responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


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
        "duty": ("책무", "의무", "준수사항", "안전조치"),
        "right": ("권리", "청구권", "열람", "정정", "삭제", "요구권"),
        "report": ("신고", "통지", "보고", "제출"),
        "permit": ("허가", "인가", "승인", "등록"),
        "delegation": ("위임", "위탁", "위임사항", "위탁업무"),
        "exception": ("예외", "특례", "적용 제외", "적용배제"),
        "prohibition": ("금지행위", "금지", "제한"),
        "sanction": ("벌칙", "과태료", "과징금", "시정명령"),
    }
    _QUESTION_INTENT_KEYWORDS = {
        "difference": ("차이", "구분", "비교", "다른 점", "무슨 차이"),
        "requirements": ("요건", "조건", "기준", "성립", "충족", "해당"),
        "procedure": ("절차", "방법", "순서", "어떻게 해야", "어떻게 하나", "진행"),
        "illegality": ("위법", "불법", "가능한지", "문제되는지", "허용되는지", "판단"),
        "applicability": ("적용", "대상", "해당하는지", "포함되는지", "제외되는지"),
        "explain": ("설명", "해설", "알려줘", "풀어줘", "무슨 뜻", "뭐야"),
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

    @classmethod
    def _article_category(cls, article_title: Optional[str]) -> Optional[str]:
        if not article_title:
            return None
        normalized = cls._clean_text(article_title)
        for category, keywords in cls._ARTICLE_CATEGORY_KEYWORDS.items():
            if any(keyword in normalized for keyword in keywords):
                return category
        return None

    @classmethod
    def _question_intent(cls, user_query: str) -> str:
        normalized = cls._clean_text(user_query)
        ordered_intents = ("difference", "illegality", "requirements", "procedure", "applicability", "explain")
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
            return f"{law_name} {article_no}는 {label}에 관한 규정으로, 다른 조문과 비교할 때 기준점이 되는 조문입니다."
        if intent == "requirements":
            return f"{law_name} {article_no}는 {label}에 관한 규정으로, 적용 요건이나 판단 기준을 읽을 때 출발점이 되는 조문입니다."
        if intent == "procedure":
            return f"{law_name} {article_no}는 {label}에 관한 규정으로, 절차나 처리 순서를 이해할 때 먼저 확인할 조문입니다."
        if intent == "illegality":
            return f"{law_name} {article_no}는 {label}에 관한 규정으로, 위법 여부를 판단할 때 참고해야 할 기준 중 하나입니다."
        if intent == "applicability":
            return f"{law_name} {article_no}는 {label}에 관한 규정으로, 어떤 대상이나 상황에 적용되는지 가늠할 때 기준이 되는 조문입니다."
        return f"{law_name} {article_no}는 {label}에 관한 규정입니다."

    @classmethod
    def _build_plain_explanation(cls, article_title: Optional[str], law_name: str, article_no: str) -> str:
        category = cls._article_category(article_title)
        if category == "purpose":
            return f"쉽게 말하면 이 조문은 {law_name}이 왜 존재하는지와 어떤 가치를 보호하려는지 밝히는 목적 조항입니다."
        if category == "definition":
            return f"쉽게 말하면 이 조문은 {law_name}에서 반복해서 쓰이는 핵심 용어의 뜻을 정해 뒤 조항 해석의 기준을 세우는 정의 조항입니다."
        if category == "scope":
            return f"쉽게 말하면 {article_no}는 {law_name}이 누구에게, 어떤 경우에 적용되는지 범위를 정해주는 조문입니다."
        if category == "duty":
            return f"쉽게 말하면 {article_no}는 {law_name}상 관련 주체가 무엇을 해야 하는지를 정한 의무 조항입니다."
        if category == "right":
            return f"쉽게 말하면 {article_no}는 당사자나 정보주체가 행사할 수 있는 권리와 그 범위를 보여주는 조문입니다."
        if category == "report":
            return f"쉽게 말하면 {article_no}는 신고, 보고, 통지처럼 대외적으로 알려야 하는 절차를 정한 조문입니다."
        if category == "permit":
            return f"쉽게 말하면 {article_no}는 허가나 승인처럼 사전에 갖춰야 할 절차와 기준을 정한 조문입니다."
        if category == "delegation":
            return f"쉽게 말하면 {article_no}는 세부 사항을 다른 기관이나 하위 규정에 맡기는 위임 성격의 조문입니다."
        if category == "exception":
            return f"쉽게 말하면 {article_no}는 일반 원칙의 예외나 특례가 언제 인정되는지를 정한 조문입니다."
        if category == "prohibition":
            return f"쉽게 말하면 {article_no}는 해서는 안 되는 행위나 제한되는 범위를 정해 위험한 행위를 막는 조문입니다."
        if category == "sanction":
            return f"쉽게 말하면 {article_no}는 위반 시 책임이나 제재 기준을 정한 조문이라 사실관계와 적용 요건을 엄격하게 봐야 합니다."
        return f"쉽게 말하면 {article_no}는 {law_name}에서 해당 주제에 관한 기본 기준이나 방향을 직접 정한 조문입니다."

    @classmethod
    def _tail_guidance(cls, user_query: str) -> Optional[str]:
        intent = cls._question_intent(user_query)
        if intent == "difference":
            return "필요하시면 비교 대상 조문이나 다른 법률과의 차이까지 이어서 정리해드릴 수 있습니다."
        if intent == "requirements":
            return "필요하시면 이 조문이 실제로 적용되기 위한 요건을 항목별로 나눠서 설명해드릴 수 있습니다."
        if intent == "procedure":
            return "필요하시면 이 조문과 연결되는 절차를 단계별로 다시 정리해드릴 수 있습니다."
        if intent == "illegality":
            return "다만 위법 여부는 조문 문구만으로 단정하기보다 구체적 사실관계와 예외 규정을 함께 확인하는 편이 안전합니다."
        if intent == "applicability":
            return "필요하시면 어떤 대상이 포함되고 제외되는지 사례형으로 풀어서 설명해드릴 수 있습니다."
        return None

    @staticmethod
    def _build_risk_notice(risk_level: str, article_title: Optional[str]) -> Optional[str]:
        if risk_level != "HIGH":
            return None
        if AnswerComposer._article_category(article_title) == "sanction":
            return "이 조문은 제재와 직접 연결될 수 있어 실제 적용 여부는 사실관계, 주체, 시점, 예외 사유를 함께 확인하는 것이 안전합니다."
        return "이 질문은 해석상 주의가 필요한 편이므로 실제 적용 시에는 관련 조문과 사실관계를 추가로 확인하는 편이 안전합니다."

    @classmethod
    def _comparison_summary(
        cls,
        base_article_no: str,
        base_article_title: Optional[str],
        related_articles: List[Dict[str, Any]],
    ) -> Optional[str]:
        valid_articles = [
            article
            for article in related_articles
            if isinstance(article, dict) and article.get("found") and article.get("article_no") and article.get("article_text")
        ]
        if not valid_articles:
            return None

        base_label = base_article_title or "기준 주제"
        comparisons: List[str] = []
        for article in valid_articles[:2]:
            related_title = cls._extract_article_title(str(article.get("article_text", ""))) or "다른 주제"
            if related_title == base_label:
                comparisons.append(
                    f"{article['article_no']}도 비슷한 주제를 다루지만 세부 내용이나 적용 범위는 직접 조문 문구로 비교해야 합니다."
                )
            else:
                comparisons.append(
                    f"{base_article_no}가 {base_label}에 초점을 둔다면 {article['article_no']}는 {related_title} 쪽에 무게가 실려 있습니다."
                )
        if not comparisons:
            return None

        lines = ["[비교 요약]"]
        lines.extend(comparisons)
        return "\n".join(lines)

    @classmethod
    def _illegality_summary(
        cls,
        article_no: str,
        article_title: Optional[str],
        related_articles: List[Dict[str, Any]],
    ) -> str:
        category = cls._article_category(article_title)
        lines = ["[판단 순서]"]
        if category == "sanction":
            lines.append("1. 먼저 어떤 행위가 문제 되는지 사실관계를 특정합니다.")
            lines.append(f"2. {article_no} 자체만 보지 말고, 선행 의무조항이나 금지조항 위반이 있는지 먼저 확인합니다.")
            lines.append(f"3. 그 위반이 {article_no}의 제재 기준에 연결되는지, 그리고 예외 사유가 없는지 순서대로 확인합니다.")
        else:
            lines.append(f"1. 질문 속 행위가 {article_no}가 전제하는 대상과 상황에 해당하는지 먼저 봅니다.")
            lines.append("2. 조문이 요구하는 요건을 사실관계에 하나씩 대입해 충족 여부를 확인합니다.")
            lines.append("3. 예외 조항이나 다른 정당화 사유가 없는지 함께 확인한 뒤 위법 여부를 판단합니다.")

        found_related = [article for article in related_articles if article.get("found") and article.get("article_no")]
        if found_related:
            lines.append("")
            lines.append("[추가 확인 포인트]")
            for article in found_related[:2]:
                title = cls._extract_article_title(str(article.get("article_text", ""))) or "관련 조문"
                lines.append(f"- {article['article_no']}({title})도 같이 보면 위반 요건이나 예외 사유를 더 분명히 판단하는 데 도움이 됩니다.")
        return "\n".join(lines)

    @classmethod
    def _applicability_summary(
        cls,
        article_no: str,
        article_title: Optional[str],
        related_articles: List[Dict[str, Any]],
    ) -> str:
        category = cls._article_category(article_title)
        lines = ["[적용 판단 포인트]"]
        lines.append(f"1. 질문 속 대상이 {article_no}가 상정하는 주체나 기관에 포함되는지 먼저 봅니다.")
        if category == "scope":
            lines.append("2. 이 조문이 적용 범위를 넓게 정하는지, 특정 영역만 한정하는지 문언을 확인합니다.")
        elif category == "exception":
            lines.append("2. 일반 원칙보다 예외나 특례를 다루는 조문인지 확인해 포함과 제외를 구분합니다.")
        else:
            lines.append("2. 조문이 요구하는 상황이나 행위 유형에 해당하는지 요건을 맞춰봅니다.")
        lines.append("3. 적용 제외, 특례, 별도 법령 우선 같은 예외 구조가 있는지 함께 확인합니다.")

        found_related = [article for article in related_articles if article.get("found") and article.get("article_no")]
        if found_related:
            lines.append("")
            lines.append("[함께 볼 조문]")
            for article in found_related[:2]:
                title = cls._extract_article_title(str(article.get("article_text", ""))) or "관련 조문"
                lines.append(f"- {article['article_no']}({title})를 같이 보면 포함 대상과 제외 대상의 경계를 더 분명히 볼 수 있습니다.")
        return "\n".join(lines)

    @classmethod
    def _procedure_summary(cls, article_no: str, related_articles: List[Dict[str, Any]]) -> str:
        lines = ["[절차 정리]"]
        lines.append(f"1. 먼저 {article_no}의 기본 의무나 출발 절차를 확인합니다.")

        found_related = [article for article in related_articles if article.get("found") and article.get("article_no")]
        if found_related:
            for index, article in enumerate(found_related[:2], start=2):
                title = cls._extract_article_title(str(article.get("article_text", ""))) or "관련 절차"
                lines.append(f"{index}. 이어서 {article['article_no']}({title})에서 후속 절차나 추가 조치를 확인합니다.")
            lines.append(f"{min(len(found_related) + 2, 4)}. 단계별 의무의 시점과 상대방이 서로 다른지 마지막으로 점검합니다.")
        else:
            lines.append("2. 후속 통지, 신고, 제출 같은 연결 절차가 있는지 관련 조문을 추가로 확인합니다.")
            lines.append("3. 각 단계의 시점과 상대방이 서로 다른지 마지막으로 점검합니다.")
        return "\n".join(lines)

    @classmethod
    def _related_articles_block(cls, related_articles: List[Dict[str, Any]], intent: str) -> Optional[str]:
        valid_articles = [
            article
            for article in related_articles
            if isinstance(article, dict) and article.get("found") and article.get("article_no") and article.get("article_text")
        ]
        if not valid_articles:
            return None

        lines: List[str] = []
        if intent == "difference":
            lines.append("[비교 참고 조문]")
            lines.append("비교 질문이라 함께 보면 좋은 조문은 아래와 같습니다.")
        elif intent == "procedure":
            lines.append("[연관 조문]")
            lines.append("절차 질문이라 흐름을 이해할 때 같이 보면 좋은 조문은 아래와 같습니다.")
        elif intent == "applicability":
            lines.append("[적용 참고 조문]")
            lines.append("적용 여부를 볼 때 경계선을 함께 확인하면 좋은 조문은 아래와 같습니다.")
        else:
            lines.append("[관련 조문]")

        for article in valid_articles[:3]:
            title = cls._extract_article_title(str(article.get("article_text", "")))
            label = article["article_no"]
            if title:
                label = f"{label}({title})"
            excerpt = cls._truncate_text(str(article.get("article_text", "")), 120)
            lines.append(f"- {label}: {excerpt}")
        return "\n".join(lines)

    @classmethod
    def _evidence_block(
        cls,
        law_name: str,
        article_no: str,
        version_fields: Dict[str, Any],
        used_search_query: Optional[str],
        related_articles: List[Dict[str, Any]],
    ) -> str:
        lines = ["[근거]"]
        if law_name:
            lines.append(f"- 법령: {law_name}")
        if article_no:
            lines.append(f"- 조문: {article_no}")
        if version_fields.get("시행일자"):
            lines.append(f"- 시행일자: {version_fields['시행일자']}")
        if used_search_query:
            lines.append(f"- 검색 기준: {used_search_query}")
        related_numbers = [str(article.get("article_no")).strip() for article in related_articles if article.get("found")]
        if related_numbers:
            lines.append(f"- 함께 확인한 조문: {', '.join(related_numbers[:3])}")
        return "\n".join(lines)

    def compose(self, composition_input: AnswerCompositionInput) -> str:
        law_enrichment = composition_input.law_enrichment
        primary_law = law_enrichment.get("primary_law") or {}
        version = law_enrichment.get("version") or {}
        version_fields = version.get("version_fields") or {}
        article = law_enrichment.get("article") or {}
        related_articles = law_enrichment.get("related_articles") or []
        used_search_query = self._clean_text(str(law_enrichment.get("used_search_query", ""))) or None

        law_name = self._clean_text(str(primary_law.get("law_name", "")))
        article_text = self._clean_text(str(article.get("article_text", "")))
        article_no = self._clean_text(str(article.get("article_no", "")))
        article_title = self._extract_article_title(article_text) if article_text else None
        intent = self._question_intent(composition_input.user_query)

        if law_name and article.get("found") and article_text and article_no:
            lead_sentence = self._lead_sentence(composition_input.user_query, law_name, article_no, article_title)
            if intent == "explain":
                lead_sentence = f"{law_name} {article_no}는 {article_title or '해당 조문'}에 관한 규정입니다."

            lines = [
                lead_sentence,
                "",
                "현재 확인한 조문은 다음과 같습니다.",
                article_text,
                "",
                self._build_plain_explanation(article_title, law_name, article_no),
            ]

            if intent == "difference":
                comparison_summary = self._comparison_summary(article_no, article_title, related_articles)
                if comparison_summary:
                    lines.extend(["", comparison_summary])

            if intent == "illegality":
                lines.extend(["", self._illegality_summary(article_no, article_title, related_articles)])

            if intent == "applicability":
                lines.extend(["", self._applicability_summary(article_no, article_title, related_articles)])

            if intent == "procedure":
                lines.extend(["", self._procedure_summary(article_no, related_articles)])

            related_block = self._related_articles_block(related_articles, intent)
            if related_block:
                lines.extend(["", related_block])

            if version_fields.get("시행일자"):
                lines.extend(["", f"기준 정보: 현재 확인한 시행일자는 {version_fields['시행일자']}입니다."])

            risk_notice = self._build_risk_notice(composition_input.risk_level, article_title)
            if risk_notice:
                lines.extend(["", risk_notice])

            tail_guidance = self._tail_guidance(composition_input.user_query)
            if tail_guidance:
                lines.extend(["", tail_guidance])

            lines.extend(
                [
                    "",
                    self._evidence_block(law_name, article_no, version_fields, used_search_query, related_articles),
                ]
            )
            return "\n".join(lines).strip()

        if law_name:
            lines = [f"질문과 가장 관련된 법령은 {law_name}입니다."]
            if version_fields.get("시행일자"):
                lines.append(f"현재 확인한 시행일자는 {version_fields['시행일자']}입니다.")
            else:
                lines.append("현재 확보한 정보만으로는 시행일자를 특정하지 못했습니다.")
            lines.append("다만 현재 질문에 대응하는 조문 본문까지는 확보되지 않아, 우선 법령명과 버전 정보를 기준으로 안내드립니다.")
            if composition_input.risk_level == "HIGH":
                lines.append("질문에 위법 여부나 제재 판단 요소가 포함되어 있어 현재 정보만으로 확정적으로 단정하기보다 구체적 사실관계와 관련 조문을 함께 확인하는 편이 안전합니다.")
            else:
                lines.append("필요하시면 관련 조문이나 정의 조항을 추가로 특정해서 더 구체적으로 설명드릴 수 있습니다.")

            related_block = self._related_articles_block(related_articles, intent)
            if related_block:
                lines.extend(["", related_block])

            tail_guidance = self._tail_guidance(composition_input.user_query)
            if tail_guidance and tail_guidance not in lines:
                lines.append(tail_guidance)
            lines.extend(
                [
                    "",
                    self._evidence_block(law_name, "", version_fields, used_search_query, related_articles),
                ]
            )
            return "\n".join(lines).strip()

        if composition_input.prompt_payload.get("system") and composition_input.fallback_answer.strip():
            return self._truncate_text(composition_input.fallback_answer, max_chars=400)
        return "관련 법령 정보를 확인했지만 현재 답변을 구성할 만큼 근거가 충분하지 않습니다."
