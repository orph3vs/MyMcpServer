"""Multi-Agent Review pipeline: summary -> parallel analysis -> integration.

Agents:
- MainAgent
- LegalAuditorAgent
- RiskReviewerAgent
- ComplianceAgent

Includes token limit options for each stage and final output.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import time
import uuid
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

    def analyze(self, summary: str) -> AgentResult:
        raise NotImplementedError


class MainAgent(BaseAgent):
    name = "MainAgent"

    def summarize(self, question: str, context: Optional[str] = None) -> str:
        base = f"질문 요약: {question.strip()}"
        if context:
            base += f" | 컨텍스트: {context.strip()}"
        return self._truncate_tokens(base)


class LegalAuditorAgent(BaseAgent):
    name = "LegalAuditorAgent"

    def analyze(self, summary: str) -> AgentResult:
        text = (
            "[법령감사] 요약 문장에서 법령명/조문/시점이 명시되었는지 점검하고, "
            "근거 없는 단정 문장을 제외해야 함. "
            f"대상 요약: {summary}"
        )
        return AgentResult(agent_name=self.name, content=self._truncate_tokens(text))


class RiskReviewerAgent(BaseAgent):
    name = "RiskReviewerAgent"

    def __init__(self, token_limit: int, classifier: Optional[RiskClassifier] = None) -> None:
        super().__init__(token_limit)
        self.classifier = classifier or RiskClassifier()

    def analyze(self, summary: str) -> AgentResult:
        assessment = self.classifier.classify(summary)
        text = (
            f"[리스크검토] risk_level={assessment.risk_level}, total_score={assessment.total_score}. "
            f"근거={assessment.reasons}. 고위험이면 보수적 응답과 추가 확인 항목을 요구."
        )
        return AgentResult(agent_name=self.name, content=self._truncate_tokens(text))


class ComplianceAgent(BaseAgent):
    name = "ComplianceAgent"

    def analyze(self, summary: str) -> AgentResult:
        text = (
            "[컴플라이언스] 개인정보/제재/감독기관/법령충돌 항목의 누락 여부를 점검하고 "
            "환각·추정·일반화 표현을 제거해야 함. "
            f"대상 요약: {summary}"
        )
        return AgentResult(agent_name=self.name, content=self._truncate_tokens(text))


class MultiAgentReviewPipeline:
    """Runs summary -> parallel analysis -> integration with token limits."""

    def __init__(
        self,
        token_options: Optional[TokenLimitOptions] = None,
        max_workers: int = 3,
    ) -> None:
        self.token_options = token_options or TokenLimitOptions()
        self.main_agent = MainAgent(token_limit=self.token_options.summary_max_tokens)
        self.legal_auditor = LegalAuditorAgent(
            token_limit=self.token_options.agent_output_max_tokens
        )
        self.risk_reviewer = RiskReviewerAgent(
            token_limit=self.token_options.agent_output_max_tokens
        )
        self.compliance_agent = ComplianceAgent(
            token_limit=self.token_options.agent_output_max_tokens
        )
        self.max_workers = max_workers

    def _integrate(self, summary: str, agent_results: List[AgentResult]) -> str:
        ordered = sorted(agent_results, key=lambda r: r.agent_name)
        merged = [
            "[통합검토]",
            f"요약: {summary}",
        ]
        for result in ordered:
            merged.append(f"- {result.agent_name}: {result.content}")
        integrated = "\n".join(merged)

        tokens = integrated.split()
        max_tokens = self.token_options.final_output_max_tokens
        if len(tokens) > max_tokens:
            return " ".join(tokens[:max_tokens]).strip()
        return integrated

    def run(self, question: str, context: Optional[str] = None) -> MultiAgentReviewResult:
        # Step 1. summary
        summary = self.main_agent.summarize(question=question, context=context)

        # Step 2. parallel analysis
        agents = [self.legal_auditor, self.risk_reviewer, self.compliance_agent]
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(agent.analyze, summary) for agent in agents]
            results = [future.result() for future in futures]

        # Step 3. integration
        integrated = self._integrate(summary=summary, agent_results=results)

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
    ) -> MultiAgentReviewResult:
        start = time.perf_counter()
        result = self.run(question=question, context=context)
        latency = round((time.perf_counter() - start) * 1000, 3)

        logger = cost_logger or CostLogger()
        rid = request_id or str(uuid.uuid4())

        default_metrics = RequestMetrics(
            risk_level="LOW",
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
