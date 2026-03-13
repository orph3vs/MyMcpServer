import unittest

from src.risk_classifier import RiskClassifier


class RiskClassifierFocusedCasesTests(unittest.TestCase):
    def setUp(self):
        self.classifier = RiskClassifier(high_threshold=5)

    def test_privacy_pseudonym_outsourcing_thirdparty_mixed_20_cases(self):
        # 개인정보·가명·위탁·제3자 제공 중심, HIGH/LOW 혼합 20개
        cases = [
            ("개인정보 처리 방침에 제3자 제공이 포함되나요", "LOW"),
            ("가명정보 결합 시 재식별 위험이 있나요", "LOW"),
            ("개인정보 위탁 계약서 필수 항목을 알려줘", "LOW"),
            ("제3자 제공 동의서 양식에 필요한 문구", "LOW"),
            ("개인정보 위법 제공 시 과징금 가능성", "HIGH"),
            ("가명정보를 제3자 제공하면 불법인가", "HIGH"),
            ("위탁사 조사 대응과 시정명령 소명 절차", "HIGH"),
            ("개인정보 제3자 제공이 법령 충돌되는지", "HIGH"),
            ("가명정보 처리 위법 여부와 처분 수위", "HIGH"),
            ("수탁자 관리 점검 기준", "LOW"),
            ("제3자 제공 기록 보관 기간", "LOW"),
            ("개인정보 국외 이전과 감독기관 자료제출", "HIGH"),
            ("위탁 업무 중 주민등록번호 처리 위법", "HIGH"),
            ("가명정보 재식별 시 벌칙과 제재", "HIGH"),
            ("제3자 제공 거부권 안내 문구", "LOW"),
            ("개인정보 처리 위탁 중 감독기관 조사 대응", "HIGH"),
            ("가명정보 결합 기준과 일반법 특별법 우선 적용", "HIGH"),
            ("위탁사 변경 시 정보주체 고지 의무", "LOW"),
            ("제3자 제공과 위탁의 구분 기준", "LOW"),
            ("개인정보 제3자 제공 위법 과태료 처분", "HIGH"),
        ]

        high_count = 0
        low_count = 0

        for question, expected in cases:
            with self.subTest(question=question):
                result = self.classifier.classify(question)
                self.assertEqual(result.risk_level, expected)
                if expected == "HIGH":
                    high_count += 1
                else:
                    low_count += 1

        self.assertEqual(len(cases), 20)
        self.assertGreater(high_count, 0)
        self.assertGreater(low_count, 0)


if __name__ == "__main__":
    unittest.main()
