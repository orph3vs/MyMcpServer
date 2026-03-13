import unittest

from src.answer_composer import AnswerComposer, AnswerCompositionInput


class AnswerComposerTests(unittest.TestCase):
    def setUp(self):
        self.composer = AnswerComposer()

    def test_compose_article_answer_for_purpose_article(self):
        result = self.composer.compose(
            AnswerCompositionInput(
                user_query="개인정보 보호법 제1조 설명",
                prompt_payload={"system": "x", "user": "y"},
                law_enrichment={
                    "primary_law": {"law_name": "개인정보 보호법"},
                    "version": {"version_fields": {"시행일자": "20251002"}},
                    "article": {
                        "found": True,
                        "article_no": "제1조",
                        "article_text": "제1조(목적) 이 법은 개인정보의 처리 및 보호에 관한 사항을 정한다.",
                    },
                },
                risk_level="LOW",
                fallback_answer="",
            )
        )

        self.assertIn("개인정보 보호법 제1조는 목적에 관한 규정입니다.", result)
        self.assertIn("현재 확인한 조문은 다음과 같습니다.", result)
        self.assertIn("쉽게 말하면 이 조문은 개인정보 보호법이 왜 존재하는지", result)
        self.assertIn("[근거]", result)
        self.assertIn("- 법령: 개인정보 보호법", result)
        self.assertIn("- 조문: 제1조", result)

    def test_compose_article_answer_for_high_risk_sanction_article(self):
        result = self.composer.compose(
            AnswerCompositionInput(
                user_query="벌칙 조항 위법 여부 설명",
                prompt_payload={"system": "x", "user": "y"},
                law_enrichment={
                    "primary_law": {"law_name": "개인정보 보호법"},
                    "version": {"version_fields": {}},
                    "article": {
                        "found": True,
                        "article_no": "제75조",
                        "article_text": "제75조(과태료) 다음 각 호의 어느 하나에 해당하는 자에게 과태료를 부과한다.",
                    },
                },
                risk_level="HIGH",
                fallback_answer="",
            )
        )

        self.assertIn("위법 여부를 판단할 때 참고해야 할 기준", result)
        self.assertIn("제재 기준을 정한 조문", result)
        self.assertIn("[판단 순서]", result)
        self.assertIn("선행 의무조항이나 금지조항 위반이 있는지 먼저 확인", result)
        self.assertIn("사실관계, 주체, 시점, 예외 사유를 함께 확인", result)

    def test_compose_illegality_answer_for_non_sanction_article(self):
        result = self.composer.compose(
            AnswerCompositionInput(
                user_query="개인정보 보호법 제15조가 위법 판단 기준인지 설명해줘",
                prompt_payload={"system": "x", "user": "y"},
                law_enrichment={
                    "primary_law": {"law_name": "개인정보 보호법"},
                    "version": {"version_fields": {}},
                    "article": {
                        "found": True,
                        "article_no": "제15조",
                        "article_text": "제15조(개인정보의 수집ㆍ이용) 개인정보처리자는 다음 각 호의 어느 하나에 해당하는 경우 개인정보를 수집할 수 있다.",
                    },
                    "related_articles": [
                        {
                            "found": True,
                            "article_no": "제17조",
                            "article_text": "제17조(개인정보의 제공) 개인정보처리자는 다음 각 호의 어느 하나에 해당하는 경우 개인정보를 제3자에게 제공할 수 있다.",
                        }
                    ],
                },
                risk_level="HIGH",
                fallback_answer="",
            )
        )

        self.assertIn("[판단 순서]", result)
        self.assertIn("대상과 상황에 해당하는지 먼저 봅니다.", result)
        self.assertIn("[추가 확인 포인트]", result)
        self.assertIn("제17조(개인정보의 제공)", result)

    def test_compose_applicability_answer_adds_scope_checklist(self):
        result = self.composer.compose(
            AnswerCompositionInput(
                user_query="이 경우에도 개인정보 보호법 제3조가 적용되는지 설명해줘",
                prompt_payload={"system": "x", "user": "y"},
                law_enrichment={
                    "primary_law": {"law_name": "개인정보 보호법"},
                    "version": {"version_fields": {}},
                    "article": {
                        "found": True,
                        "article_no": "제3조",
                        "article_text": "제3조(적용범위) 이 법은 공공기관과 사업자에게 적용한다.",
                    },
                    "related_articles": [
                        {
                            "found": True,
                            "article_no": "제58조",
                            "article_text": "제58조(적용의 일부 제외) 이 법의 일부 규정은 다음 각 호의 경우에 적용하지 아니한다.",
                        }
                    ],
                },
                risk_level="LOW",
                fallback_answer="",
            )
        )

        self.assertIn("[적용 판단 포인트]", result)
        self.assertIn("상정하는 주체나 기관에 포함되는지", result)
        self.assertIn("적용 범위를 넓게 정하는지", result)
        self.assertIn("[함께 볼 조문]", result)
        self.assertIn("제58조(적용의 일부 제외)", result)
        self.assertIn("[적용 참고 조문]", result)

    def test_compose_fallback_for_related_law_without_article(self):
        result = self.composer.compose(
            AnswerCompositionInput(
                user_query="개인정보 처리 위법 여부",
                prompt_payload={"system": "x", "user": "y"},
                law_enrichment={
                    "primary_law": {"law_name": "개인정보 보호법"},
                    "version": {"version_fields": {"시행일자": "20251002"}},
                    "used_search_query": "개인정보 보호법",
                },
                risk_level="HIGH",
                fallback_answer="",
            )
        )

        self.assertIn("질문과 가장 관련된 법령은 개인정보 보호법입니다.", result)
        self.assertIn("현재 확인한 시행일자는 20251002입니다.", result)
        self.assertIn("구체적 사실관계와 관련 조문", result)
        self.assertIn("- 검색 기준: 개인정보 보호법", result)

    def test_compose_article_answer_for_scope_article(self):
        result = self.composer.compose(
            AnswerCompositionInput(
                user_query="적용범위 조항 설명",
                prompt_payload={"system": "x", "user": "y"},
                law_enrichment={
                    "primary_law": {"law_name": "가상 법률"},
                    "version": {"version_fields": {}},
                    "article": {
                        "found": True,
                        "article_no": "제3조",
                        "article_text": "제3조(적용범위) 이 법은 국가기관과 공공기관에 적용한다.",
                    },
                },
                risk_level="LOW",
                fallback_answer="",
            )
        )

        self.assertIn("적용되는지 가늠할 때 기준이 되는 조문", result)
        self.assertIn("범위를 정해주는 조문", result)

    def test_compose_high_risk_fallback_without_version_is_cautious(self):
        result = self.composer.compose(
            AnswerCompositionInput(
                user_query="위법 여부 판단",
                prompt_payload={"system": "x", "user": "y"},
                law_enrichment={"primary_law": {"law_name": "가상 법률"}},
                risk_level="HIGH",
                fallback_answer="",
            )
        )

        self.assertIn("시행일자를 특정하지 못했습니다.", result)
        self.assertIn("확정적으로 단정하기보다", result)

    def test_compose_difference_question_adds_related_articles(self):
        result = self.composer.compose(
            AnswerCompositionInput(
                user_query="개인정보 보호법 제1조와 제2조 차이 설명",
                prompt_payload={"system": "x", "user": "y"},
                law_enrichment={
                    "primary_law": {"law_name": "개인정보 보호법"},
                    "version": {"version_fields": {}},
                    "article": {
                        "found": True,
                        "article_no": "제1조",
                        "article_text": "제1조(목적) 이 법의 목적을 정한다.",
                    },
                    "related_articles": [
                        {
                            "found": True,
                            "article_no": "제2조",
                            "article_text": "제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.",
                        }
                    ],
                },
                risk_level="LOW",
                fallback_answer="",
            )
        )

        self.assertIn("다른 조문과 비교할 때 기준점이 되는 조문", result)
        self.assertIn("[비교 요약]", result)
        self.assertIn("제1조가 목적에 초점을 둔다면 제2조는 정의 쪽에 무게가 실려 있습니다.", result)
        self.assertIn("[비교 참고 조문]", result)
        self.assertIn("제2조(정의)", result)
        self.assertIn("비교 대상 조문", result)

    def test_compose_procedure_question_adds_staged_steps(self):
        result = self.composer.compose(
            AnswerCompositionInput(
                user_query="개인정보 보호법 제34조와 제34조의2 절차를 설명해줘",
                prompt_payload={"system": "x", "user": "y"},
                law_enrichment={
                    "primary_law": {"law_name": "개인정보 보호법"},
                    "version": {"version_fields": {}},
                    "article": {
                        "found": True,
                        "article_no": "제34조",
                        "article_text": "제34조(개인정보 유출 통지) 개인정보 유출 시 정보주체에게 통지해야 한다.",
                    },
                    "related_articles": [
                        {
                            "found": True,
                            "article_no": "제34조의2",
                            "article_text": "제34조의2(유출 신고) 개인정보 유출 시 감독기관에 신고해야 한다.",
                        }
                    ],
                },
                risk_level="LOW",
                fallback_answer="",
            )
        )

        self.assertIn("절차나 처리 순서를 이해할 때 먼저 확인할 조문", result)
        self.assertIn("[절차 정리]", result)
        self.assertIn("1. 먼저 제34조의 기본 의무", result)
        self.assertIn("2. 이어서 제34조의2(유출 신고)", result)
        self.assertIn("[연관 조문]", result)
        self.assertIn("단계별로 다시 정리", result)


if __name__ == "__main__":
    unittest.main()
