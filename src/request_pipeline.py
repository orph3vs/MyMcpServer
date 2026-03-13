"""End-to-end request pipeline.

Flow:
User -> RiskClassifier -> PromptBuilder -> LawAPI -> AgentEngine
-> Validator -> Scorer -> Logger -> Response
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.confidence_scoring import ConfidenceInput, ConfidenceScoringEngine
from src.cost_logger import CostLogEntry, CostLogger
from src.multi_agent_review import MultiAgentReviewPipeline
from src.nlic_api_wrapper import NlicApiWrapper
from src.prompt_loader import build_request_prompt
from src.risk_classifier import RiskClassifier


@dataclass(frozen=True)
class PipelineRequest:
    user_query: str
    context: Optional[str] = None
    request_id: Optional[str] = None


@dataclass(frozen=True)
class PipelineResponse:
    request_id: str
    risk_level: str
    mode: str
    answer: str
    citations: Dict[str, Any]
    score: float
    latency_ms: float
    error: Optional[Dict[str, str]] = None


class PipelineStageError(RuntimeError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


class RequestPipeline:
    """Coordinates all modules into one deterministic processing flow."""

    def __init__(
        self,
        risk_classifier: Optional[RiskClassifier] = None,
        law_api: Optional[NlicApiWrapper] = None,
        agent_engine: Optional[MultiAgentReviewPipeline] = None,
        scorer: Optional[ConfidenceScoringEngine] = None,
        logger: Optional[CostLogger] = None,
    ) -> None:
        self.risk_classifier = risk_classifier or RiskClassifier()
        self.law_api = law_api or NlicApiWrapper()
        self.agent_engine = agent_engine or MultiAgentReviewPipeline()
        self.scorer = scorer or ConfidenceScoringEngine()
        self.logger = logger or CostLogger()

    def _validate(self, answer: str, citations: Dict[str, Any]) -> None:
        if not answer.strip():
            raise PipelineStageError("Validator", "empty_answer")
        if not citations:
            raise PipelineStageError("Validator", "missing_citations")

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        return round((tokens_in * 0.0000015) + (tokens_out * 0.000002), 6)

    @staticmethod
    def _extract_law_items(law_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(law_data, dict):
            return []

        items = law_data.get("law")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        if isinstance(items, dict):
            return [items]

        nested = law_data.get("LawSearch")
        if isinstance(nested, dict):
            nested_items = nested.get("law")
            if isinstance(nested_items, list):
                return [item for item in nested_items if isinstance(item, dict)]
            if isinstance(nested_items, dict):
                return [nested_items]

        return []

    @staticmethod
    def _pick_primary_law(law_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        items = RequestPipeline._extract_law_items(law_data)
        if not items:
            return None

        primary = items[0]
        law_id = (
            primary.get("법령ID")
            or primary.get("법령 일련번호")
            or primary.get("법령일련번호")
            or primary.get("id")
        )
        law_name = (
            primary.get("법령명한글")
            or primary.get("법령 명한글")
            or primary.get("법령명_한글")
            or primary.get("name")
        )

        return {
            "law_id": str(law_id).strip() if law_id is not None else None,
            "law_name": str(law_name).strip() if law_name is not None else None,
            "raw": primary,
        }

    @staticmethod
    def _extract_article_no(question: str) -> Optional[str]:
        match = re.search(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?", question)
        if not match:
            return None
        main_no = match.group(1)
        sub_no = match.group(2)
        if sub_no:
            return f"제{int(main_no)}조의{int(sub_no)}"
        return f"제{int(main_no)}조"

    @staticmethod
    def _merge_context(base_context: Optional[str], lines: List[str]) -> Optional[str]:
        extra = "\n".join(line for line in lines if line)
        if base_context and extra:
            return f"{base_context.strip()}\n\n[LAW_CONTEXT]\n{extra}"
        if extra:
            return f"[LAW_CONTEXT]\n{extra}"
        return base_context

    def _build_law_enrichment(self, user_query: str, law_data: Dict[str, Any]) -> Dict[str, Any]:
        primary_law = self._pick_primary_law(law_data)
        enrichment: Dict[str, Any] = {
            "search_hit_count": len(self._extract_law_items(law_data)),
            "primary_law": primary_law,
        }
        if not primary_law or not primary_law.get("law_id"):
            return enrichment

        law_id = primary_law["law_id"]
        article_no = self._extract_article_no(user_query)

        if hasattr(self.law_api, "get_version"):
            try:
                enrichment["version"] = self.law_api.get_version(law_id)
            except Exception as exc:  # defensive enrichment only
                enrichment["version_error"] = str(exc)

        if article_no and hasattr(self.law_api, "get_article"):
            try:
                enrichment["article"] = self.law_api.get_article(law_id=law_id, article_no=article_no)
            except Exception as exc:  # defensive enrichment only
                enrichment["article_error"] = str(exc)

        return enrichment

    @staticmethod
    def _law_context_lines(enrichment: Dict[str, Any]) -> List[str]:
        lines: List[str] = []
        primary_law = enrichment.get("primary_law") or {}
        if primary_law.get("law_name"):
            lines.append(f"대표 법령: {primary_law['law_name']}")
        if primary_law.get("law_id"):
            lines.append(f"법령ID: {primary_law['law_id']}")

        version = enrichment.get("version")
        if isinstance(version, dict):
            version_fields = version.get("version_fields") or {}
            enacted = version_fields.get("시행일자")
            promulgated = version_fields.get("공포일자")
            revision_type = version_fields.get("제개정구분명") or version_fields.get("제개정구분")
            if enacted:
                lines.append(f"시행일자: {enacted}")
            if promulgated:
                lines.append(f"공포일자: {promulgated}")
            if revision_type:
                lines.append(f"제개정구분: {revision_type}")

        article = enrichment.get("article")
        if isinstance(article, dict) and article.get("found") and article.get("article_text"):
            lines.append(f"관련 조문: {article['article_no']}")
            lines.append(f"조문 본문: {article['article_text']}")

        return lines

    def process(self, req: PipelineRequest) -> PipelineResponse:
        request_id = req.request_id or str(uuid.uuid4())
        started = time.perf_counter()

        risk_level = "LOW"
        mode = "single_agent"
        tokens_in = len((req.user_query + " " + (req.context or "")).split())
        tokens_out = 0
        score = 0.0

        try:
            # 1) RiskClassifier
            risk = self.risk_classifier.classify(req.user_query)
            risk_level = risk.risk_level
            mode = "multi_agent" if risk_level == "HIGH" else "single_agent"

            # 2) PromptBuilder
            prompt_payload = build_request_prompt(
                user_query=req.user_query,
                context=req.context,
            )
            if not prompt_payload.get("system") or not prompt_payload.get("user"):
                raise PipelineStageError("PromptBuilder", "invalid_prompt_payload")

            # 3) LawAPI
            law_data = self.law_api.search_law(req.user_query)
            if not law_data or not self._extract_law_items(law_data):
                raise PipelineStageError("LawAPI", "empty_law_data")
            law_enrichment = self._build_law_enrichment(req.user_query, law_data)
            enriched_context = self._merge_context(req.context, self._law_context_lines(law_enrichment))

            # 4) AgentEngine
            agent_result = self.agent_engine.run(
                question=req.user_query,
                context=enriched_context,
            )
            answer = agent_result.integrated_review
            tokens_out = len(answer.split())

            # 5) Validator
            citations = {
                "law_search_result": law_data,
                "law_enrichment": law_enrichment,
            }
            self._validate(answer=answer, citations=citations)

            # 6) Scorer
            score_result = self.scorer.calculate(
                ConfidenceInput(
                    evidence_fidelity=0.8 if citations else 0.0,
                    risk_control=1.0 if risk_level == "HIGH" else 0.7,
                    procedural_compliance=1.0,
                    reproducibility=0.9,
                )
            )
            score = score_result.total_score

            latency = round((time.perf_counter() - started) * 1000, 3)
            cost = self._estimate_cost(tokens_in=tokens_in, tokens_out=tokens_out)

            # 7) Logger
            self.logger.log_request(
                CostLogEntry(
                    request_id=request_id,
                    risk_level=risk_level,
                    mode=mode,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost=cost,
                    latency=latency,
                    score=score,
                )
            )

            # 8) Response
            return PipelineResponse(
                request_id=request_id,
                risk_level=risk_level,
                mode=mode,
                answer=answer,
                citations=citations,
                score=score,
                latency_ms=latency,
            )

        except PipelineStageError as exc:
            latency = round((time.perf_counter() - started) * 1000, 3)
            cost = self._estimate_cost(tokens_in=tokens_in, tokens_out=tokens_out)
            self.logger.log_request(
                CostLogEntry(
                    request_id=request_id,
                    risk_level=risk_level,
                    mode=f"error:{exc.stage}",
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost=cost,
                    latency=latency,
                    score=score,
                )
            )
            return PipelineResponse(
                request_id=request_id,
                risk_level=risk_level,
                mode=f"error:{exc.stage}",
                answer="",
                citations={},
                score=score,
                latency_ms=latency,
                error={"stage": exc.stage, "message": exc.message},
            )
        except Exception as exc:  # defensive fallback
            latency = round((time.perf_counter() - started) * 1000, 3)
            cost = self._estimate_cost(tokens_in=tokens_in, tokens_out=tokens_out)
            self.logger.log_request(
                CostLogEntry(
                    request_id=request_id,
                    risk_level=risk_level,
                    mode="error:Unhandled",
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost=cost,
                    latency=latency,
                    score=score,
                )
            )
            return PipelineResponse(
                request_id=request_id,
                risk_level=risk_level,
                mode="error:Unhandled",
                answer="",
                citations={},
                score=score,
                latency_ms=latency,
                error={"stage": "Unhandled", "message": str(exc)},
            )
