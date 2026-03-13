"""Multi-agent review pipeline for legal Q&A."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.cost_logger import CostLogEntry, CostLogger
from src.risk_classifier import RiskClassifier


@dataclass(frozen=True)
class TokenLimitOptions:
    summary_max_tokens: int = 200
    agent_output_max_tokens: int = 220
    final_output_max_tokens: int = 320


@dataclass(frozen=True)
class AgentResult:
    agent_name: str
    content: str
    signals: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RequestMetrics:
    risk_level: str
    mode: str
    tokens_in: int
    tokens_out: int
    cost: float
    score: float


@dataclass(frozen=True)
class MultiAgentReviewResult:
    summary: str
    analyses: Dict[str, str]
    integrated_review: str
    review_summary: Dict[str, Any]


class BaseAgent:
    name: str = "BaseAgent"

    def __init__(self, token_limit: int) -> None:
        if token_limit <= 0:
            raise ValueError("token_limit must be positive")
        self.token_limit = token_limit

    def _truncate_tokens(self, text: str) -> str:
        tokens = text.split()
        if len(tokens) <= self.token_limit:
            return text.strip()
        return " ".join(tokens[: self.token_limit]).strip()

    def analyze(self, summary: str, law_enrichment: Optional[Dict[str, object]] = None) -> AgentResult:
        raise NotImplementedError


class MainAgent(BaseAgent):
    name = "MainAgent"

    def summarize(self, question: str, context: Optional[str] = None) -> str:
        base = f"질문 요약: {question.strip()}"
        if context:
            base += f" | 컨텍스트: {context.strip()}"
        return self._truncate_tokens(base)


class StatuteReviewAgent(BaseAgent):
    name = "StatuteReviewAgent"

    def analyze(self, summary: str, law_enrichment: Optional[Dict[str, object]] = None) -> AgentResult:
        law_enrichment = law_enrichment or {}
        primary_law = law_enrichment.get("primary_law") or {}
        article = law_enrichment.get("article") or {}
        law_name = primary_law.get("law_name") or "관련 법령"
        article_no = article.get("article_no") or "관련 조문"
        found_article = bool(article.get("found"))

        if found_article:
            text = (
                f"[법령검토] {law_name} {article_no} 본문이 확보되어 있으므로 답변의 중심 근거는 이 조문 문언과 시행 시점을 기준으로 잡아야 합니다. "
                f"요약 대상: {summary}"
            )
        else:
            text = (
                f"[법령검토] {law_name}의 대표 법령은 확인됐지만 직접 대응하는 조문 본문은 아직 부족합니다. "
                f"따라서 확정 표현보다는 법령 구조와 추가 확인 필요사항 중심으로 정리하는 편이 안전합니다. "
                f"요약 대상: {summary}"
            )

        return AgentResult(
            agent_name=self.name,
            content=self._truncate_tokens(text),
            signals={
                "grounded_article": found_article,
                "needs_more_facts": not found_article,
            },
        )


class PrecedentReviewAgent(BaseAgent):
    name = "PrecedentReviewAgent"

    def analyze(self, summary: str, law_enrichment: Optional[Dict[str, object]] = None) -> AgentResult:
        law_enrichment = law_enrichment or {}
        primary_law = law_enrichment.get("primary_law") or {}
        article = law_enrichment.get("article") or {}
        precedent = law_enrichment.get("primary_precedent") or {}
        used_query = str(law_enrichment.get("used_precedent_query", "")).strip()

        law_name = primary_law.get("law_name") or "관련 법령"
        article_no = article.get("article_no") or ""
        case_name = precedent.get("사건명") or precedent.get("판례명") or precedent.get("사건번호")

        if case_name:
            relevance_bits: List[str] = []
            if law_name and law_name in used_query:
                relevance_bits.append(f"{law_name} 관련 검색 결과")
            if article_no and article_no in used_query:
                relevance_bits.append(f"{article_no}와 직접 연결된 검색")

            relevance_note = ", ".join(relevance_bits) if relevance_bits else "질문 주제와 연결된 판례 검색 결과"
            text = (
                f"[판례검토] 참고 판례 {case_name}는 {relevance_note}로 확보됐습니다. "
                "따라서 답변에서는 단순히 판례가 있다는 사실보다, 해당 판례가 조문 해석이나 판단 기준을 어떻게 보완하는지 함께 설명하는 편이 좋습니다. "
                f"요약 대상: {summary}"
            )
            return AgentResult(
                agent_name=self.name,
                content=self._truncate_tokens(text),
                signals={
                    "has_precedent": True,
                    "precedent_relevant": True,
                    "precedent_relevance_note": relevance_note,
                },
            )

        text = (
            "[판례검토] 현재 확보된 직접 판례가 없으므로 판례 취지를 단정적으로 끌어오지 말고, "
            "법령 문언 중심으로 답하되 해석이 애매하면 판례 추가 확인 필요성을 분명히 남겨야 합니다. "
            f"요약 대상: {summary}"
        )
        return AgentResult(
            agent_name=self.name,
            content=self._truncate_tokens(text),
            signals={
                "has_precedent": False,
                "precedent_relevant": False,
                "needs_more_facts": True,
            },
        )


class RiskReviewerAgent(BaseAgent):
    name = "RiskReviewerAgent"

    def __init__(self, token_limit: int, classifier: Optional[RiskClassifier] = None) -> None:
        super().__init__(token_limit)
        self.classifier = classifier or RiskClassifier()

    def analyze(self, summary: str, law_enrichment: Optional[Dict[str, object]] = None) -> AgentResult:
        assessment = self.classifier.classify(summary)
        text = (
            f"[리스크검토] risk_level={assessment.risk_level}, total_score={assessment.total_score}, reasons={assessment.reasons}. "
            "고위험이면 단정 표현을 줄이고 사실관계 확인 항목과 예외 가능성을 함께 제시해야 합니다."
        )
        return AgentResult(
            agent_name=self.name,
            content=self._truncate_tokens(text),
            signals={
                "requires_caution": assessment.risk_level == "HIGH",
                "needs_more_facts": assessment.risk_level == "HIGH",
            },
        )


class ComplianceAgent(BaseAgent):
    name = "ComplianceAgent"

    def analyze(self, summary: str, law_enrichment: Optional[Dict[str, object]] = None) -> AgentResult:
        law_enrichment = law_enrichment or {}
        has_precedent = bool(law_enrichment.get("primary_precedent"))
        text = (
            "[컴플라이언스] 개인정보, 제재, 감독기관, 법령충돌 요소의 누락 여부를 점검하고 "
            "과장·추정·일반화 표현을 제거해야 합니다. "
            f"판례 포함 여부={has_precedent}. 요약 대상: {summary}"
        )
        return AgentResult(
            agent_name=self.name,
            content=self._truncate_tokens(text),
            signals={
                "avoid_overclaim": True,
                "needs_more_facts": False,
            },
        )


class MultiAgentReviewPipeline:
    """Runs summary -> parallel analysis -> integration with token limits."""

    def __init__(self, token_options: Optional[TokenLimitOptions] = None, max_workers: int = 4) -> None:
        self.token_options = token_options or TokenLimitOptions()
        self.main_agent = MainAgent(token_limit=self.token_options.summary_max_tokens)
        self.statute_reviewer = StatuteReviewAgent(token_limit=self.token_options.agent_output_max_tokens)
        self.precedent_reviewer = PrecedentReviewAgent(token_limit=self.token_options.agent_output_max_tokens)
        self.risk_reviewer = RiskReviewerAgent(token_limit=self.token_options.agent_output_max_tokens)
        self.compliance_agent = ComplianceAgent(token_limit=self.token_options.agent_output_max_tokens)
        self.max_workers = max_workers

    @staticmethod
    def _summarize_signals(results: List[AgentResult], risk_level: str) -> Dict[str, Any]:
        merged_signals: Dict[str, Any] = {}
        for result in results:
            merged_signals.update(result.signals)

        requires_caution = bool(merged_signals.get("requires_caution"))
        needs_more_facts = bool(merged_signals.get("needs_more_facts"))
        has_precedent = bool(merged_signals.get("has_precedent"))
        grounded_article = bool(merged_signals.get("grounded_article"))
        has_conflict = risk_level == "HIGH" and (needs_more_facts or (not grounded_article and not has_precedent))

        return {
            "requires_caution": requires_caution or has_conflict,
            "needs_more_facts": needs_more_facts or has_conflict,
            "has_precedent": has_precedent,
            "grounded_article": grounded_article,
            "precedent_relevant": bool(merged_signals.get("precedent_relevant")),
            "precedent_relevance_note": merged_signals.get("precedent_relevance_note"),
            "has_conflict": has_conflict,
        }

    def _integrate(
        self,
        summary: str,
        agent_results: List[AgentResult],
        risk_level: str,
        review_summary: Dict[str, Any],
    ) -> str:
        ordered = sorted(agent_results, key=lambda result: result.agent_name)
        merged = ["[통합검토]", f"risk_level: {risk_level}", f"요약: {summary}"]

        if review_summary.get("has_conflict"):
            merged.append("- integration_note: 법령·판례·리스크 신호가 완전히 정렬되지 않아 보수적으로 정리해야 합니다.")
        elif review_summary.get("requires_caution"):
            merged.append("- integration_note: 고위험 또는 해석상 주의가 필요한 사안으로 보입니다.")

        for result in ordered:
            merged.append(f"- {result.agent_name}: {result.content}")

        integrated = "\n".join(merged)
        tokens = integrated.split()
        if len(tokens) > self.token_options.final_output_max_tokens:
            return " ".join(tokens[: self.token_options.final_output_max_tokens]).strip()
        return integrated

    def run(
        self,
        question: str,
        context: Optional[str] = None,
        risk_level: str = "LOW",
        law_enrichment: Optional[Dict[str, object]] = None,
    ) -> MultiAgentReviewResult:
        summary = self.main_agent.summarize(question=question, context=context)

        agents: List[BaseAgent] = [self.statute_reviewer, self.compliance_agent]
        if risk_level == "HIGH":
            agents.extend([self.precedent_reviewer, self.risk_reviewer])

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(agents))) as executor:
            futures = [executor.submit(agent.analyze, summary, law_enrichment) for agent in agents]
            results = [future.result() for future in futures]

        review_summary = self._summarize_signals(results, risk_level=risk_level)
        integrated = self._integrate(
            summary=summary,
            agent_results=results,
            risk_level=risk_level,
            review_summary=review_summary,
        )
        return MultiAgentReviewResult(
            summary=summary,
            analyses={result.agent_name: result.content for result in results},
            integrated_review=integrated,
            review_summary=review_summary,
        )

    def run_with_logging(
        self,
        question: str,
        context: Optional[str] = None,
        request_id: Optional[str] = None,
        metrics: Optional[RequestMetrics] = None,
        cost_logger: Optional[CostLogger] = None,
        risk_level: str = "LOW",
        law_enrichment: Optional[Dict[str, object]] = None,
    ) -> MultiAgentReviewResult:
        start = time.perf_counter()
        result = self.run(question=question, context=context, risk_level=risk_level, law_enrichment=law_enrichment)
        latency = round((time.perf_counter() - start) * 1000, 3)

        logger = cost_logger or CostLogger()
        rid = request_id or str(uuid.uuid4())
        default_metrics = RequestMetrics(
            risk_level=risk_level,
            mode="multi_agent_review",
            tokens_in=len((question + " " + (context or "")).split()),
            tokens_out=len(result.integrated_review.split()),
            cost=0.0,
            score=0.0,
        )
        m = metrics or default_metrics
        logger.log_request(
            CostLogEntry(
                request_id=rid,
                risk_level=m.risk_level,
                mode=m.mode,
                tokens_in=m.tokens_in,
                tokens_out=m.tokens_out,
                cost=m.cost,
                latency=latency,
                score=m.score,
            )
        )
        return result
