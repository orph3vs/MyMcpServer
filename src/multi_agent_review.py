"""Multi-agent review pipeline for legal Q&A."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional

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
        text = (
            f"[법령검토] {law_name} {article_no} 기준으로 질문을 읽고, 조문 문언과 시행시점을 먼저 확인해야 함. "
            f"조문이 없으면 대표 법령의 적용 구조만 보수적으로 안내. 대상 요약: {summary}"
        )
        return AgentResult(agent_name=self.name, content=self._truncate_tokens(text))


class PrecedentReviewAgent(BaseAgent):
    name = "PrecedentReviewAgent"

    def analyze(self, summary: str, law_enrichment: Optional[Dict[str, object]] = None) -> AgentResult:
        law_enrichment = law_enrichment or {}
        primary_precedent = law_enrichment.get("primary_precedent") or {}
        case_name = primary_precedent.get("사건명") or primary_precedent.get("사건번호")
        if case_name:
            text = (
                f"[판례검토] 참고 판례 {case_name}가 있으므로 법령 문언만이 아니라 판례가 보여주는 해석 방향도 함께 반영해야 함. "
                f"대상 요약: {summary}"
            )
        else:
            text = (
                f"[판례검토] 현재 확보된 대표 판례는 없으므로 법령 중심으로 답하되, 해석이 애매하면 판례 추가 확인 필요성을 남겨야 함. "
                f"대상 요약: {summary}"
            )
        return AgentResult(agent_name=self.name, content=self._truncate_tokens(text))


class RiskReviewerAgent(BaseAgent):
    name = "RiskReviewerAgent"

    def __init__(self, token_limit: int, classifier: Optional[RiskClassifier] = None) -> None:
        super().__init__(token_limit)
        self.classifier = classifier or RiskClassifier()

    def analyze(self, summary: str, law_enrichment: Optional[Dict[str, object]] = None) -> AgentResult:
        assessment = self.classifier.classify(summary)
        text = (
            f"[리스크검토] risk_level={assessment.risk_level}, total_score={assessment.total_score}, reasons={assessment.reasons}. "
            "고위험이면 단정 표현을 줄이고 사실관계 확인 항목을 함께 제시해야 함."
        )
        return AgentResult(agent_name=self.name, content=self._truncate_tokens(text))


class ComplianceAgent(BaseAgent):
    name = "ComplianceAgent"

    def analyze(self, summary: str, law_enrichment: Optional[Dict[str, object]] = None) -> AgentResult:
        law_enrichment = law_enrichment or {}
        primary_precedent = law_enrichment.get("primary_precedent") or {}
        has_precedent = bool(primary_precedent)
        text = (
            "[컴플라이언스] 개인정보, 제재, 감독기관, 법령충돌 요소의 누락 여부를 점검하고 "
            "환각·추정·일반화 표현을 제거해야 함. "
            f"판례 확보 여부={has_precedent}. 대상 요약: {summary}"
        )
        return AgentResult(agent_name=self.name, content=self._truncate_tokens(text))


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

    def _integrate(self, summary: str, agent_results: List[AgentResult], risk_level: str) -> str:
        ordered = sorted(agent_results, key=lambda result: result.agent_name)
        merged = ["[통합검토]", f"risk_level: {risk_level}", f"요약: {summary}"]
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

        integrated = self._integrate(summary=summary, agent_results=results, risk_level=risk_level)
        return MultiAgentReviewResult(
            summary=summary,
            analyses={result.agent_name: result.content for result in results},
            integrated_review=integrated,
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
