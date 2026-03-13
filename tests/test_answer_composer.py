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
        self.assertIn("현재 확인된 조문은 다음과 같습니다.", result)
        self.assertIn("쉽게 말하면", result)

    def test_compose_article_answer_for_high_risk_sanction_article(self):
        result = self.composer.compose(
            AnswerCompositionInput(
                user_query="벌칙 조항 설명",
                prompt_payload={"system": "x", "user": "y"},
                law_enrichment={
                    "primary_law": {"law_name": "개인정보 보호법"},
                    "version": {"version_fields": {}},
                    "article": {
                        "found": True,
                        "article_no": "제75조",
                        "article_text": "제75조(벌칙) 다음 각 호의 어느 하나에 해당하는 자는 처벌한다.",
                    },
                },
                risk_level="HIGH",
                fallback_answer="",
            )
        )

        self.assertIn("책임이나 제재 기준", result)
        self.assertIn("사실관계와 요건 충족 여부", result)

    def test_compose_fallback_for_related_law_without_article(self):
        result = self.composer.compose(
            AnswerCompositionInput(
                user_query="개인정보 처리 위법 여부",
                prompt_payload={"system": "x", "user": "y"},
                law_enrichment={
                    "primary_law": {"law_name": "개인정보 보호법"},
                    "version": {"version_fields": {"시행일자": "20251002"}},
                },
                risk_level="HIGH",
                fallback_answer="",
            )
        )

        self.assertIn("질문과 가장 관련된 법령은 개인정보 보호법입니다.", result)
        self.assertIn("현재 확인된 시행일자는 20251002입니다.", result)
        self.assertIn("사실관계와 관련 조문", result)

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
                        "article_text": "제3조(적용범위) 이 법은 공공기관과 사업자에 적용한다.",
                    },
                },
                risk_level="LOW",
                fallback_answer="",
            )
        )

        self.assertIn("적용 범위를 분명하게 하는 조문", result)

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


if __name__ == "__main__":
    unittest.main()
