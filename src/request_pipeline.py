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

from src.answer_composer import AnswerComposer, AnswerCompositionInput
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
        self.answer_composer = AnswerComposer()
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
    def _truncate_text(text: str, max_chars: int = 140) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= max_chars:
            return compact
        return compact[: max_chars - 3].rstrip() + "..."

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

    @staticmethod
    def _law_search_queries(user_query: str) -> List[str]:
        normalized = re.sub(r"\s+", " ", user_query).strip()
        if not normalized:
            return []

        queries: List[str] = []

        law_name_match = re.search(
            r"([가-힣A-Za-z0-9 ]+?(?:법 시행규칙|법 시행령|법|시행령|시행규칙))",
            normalized,
        )
        if law_name_match:
            queries.append(re.sub(r"\s+", " ", law_name_match.group(1)).strip())

        simplified = re.sub(r"제\s*\d+\s*조(?:\s*의\s*\d+)?", "", normalized)
        simplified = re.sub(r"\b(설명|해설|알려줘|알려 주세요|알려줘요|보여줘|요약|의미|뭐야|무엇인가)\b", "", simplified)
        simplified = re.sub(r"\s+", " ", simplified).strip(" ,")
        if simplified:
            queries.append(simplified)

        queries.append(normalized)

        deduped: List[str] = []
        seen = set()
        for query in queries:
            if query and query not in seen:
                seen.add(query)
                deduped.append(query)
        return deduped

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
            lines.append(f"조문 요약: {RequestPipeline._truncate_text(article['article_text'])}")

        return lines

    @staticmethod
    def _summarize_search_results(law_data: Dict[str, Any], used_search_query: Optional[str]) -> Dict[str, Any]:
        items = RequestPipeline._extract_law_items(law_data)
        results = []
        for item in items[:5]:
            results.append(
                {
                    "law_id": item.get("법령ID") or item.get("id"),
                    "law_name": item.get("법령명한글") or item.get("법령 명한글") or item.get("법령명_한글"),
                    "law_type": item.get("법령구분명"),
                    "effective_date": item.get("시행일자"),
                    "promulgation_date": item.get("공포일자"),
                }
            )

        return {
            "used_search_query": used_search_query,
            "search_hit_count": len(items),
            "results": results,
        }

    @staticmethod
    def _summarize_law_enrichment(enrichment: Dict[str, Any]) -> Dict[str, Any]:
        primary_law = enrichment.get("primary_law") or {}
        version = enrichment.get("version") or {}
        version_fields = version.get("version_fields") or {}
        article = enrichment.get("article") or {}

        article_summary = None
        if isinstance(article, dict) and article.get("found"):
            article_summary = {
                "article_no": article.get("article_no"),
                "found": True,
                "matched_via": article.get("matched_via"),
                "article_text_excerpt": RequestPipeline._truncate_text(str(article.get("article_text", "")), 180),
            }

        return {
            "search_queries": enrichment.get("search_queries", []),
            "used_search_query": enrichment.get("used_search_query"),
            "primary_law": {
                "law_id": primary_law.get("law_id"),
                "law_name": primary_law.get("law_name"),
            }
            if primary_law
            else None,
            "version": {
                "source_target": version.get("source_target"),
                "effective_date": version_fields.get("시행일자"),
                "promulgation_date": version_fields.get("공포일자"),
                "revision_type": version_fields.get("제개정구분명") or version_fields.get("제개정구분"),
            }
            if version
            else None,
            "article": article_summary,
        }

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
            search_queries = self._law_search_queries(req.user_query)
            law_data: Dict[str, Any] = {}
            used_search_query: Optional[str] = None
            for search_query in search_queries:
                law_data = self.law_api.search_law(search_query)
                if law_data and self._extract_law_items(law_data):
                    used_search_query = search_query
                    break

            if not law_data or not self._extract_law_items(law_data):
                raise PipelineStageError("LawAPI", "empty_law_data")
            law_enrichment = self._build_law_enrichment(req.user_query, law_data)
            law_enrichment["search_queries"] = search_queries
            law_enrichment["used_search_query"] = used_search_query
            enriched_context = self._merge_context(req.context, self._law_context_lines(law_enrichment))

            # 4) AgentEngine
            agent_result = self.agent_engine.run(
                question=req.user_query,
                context=enriched_context,
            )
            answer = self.answer_composer.compose(
                AnswerCompositionInput(
                    user_query=req.user_query,
                    prompt_payload=prompt_payload,
                    law_enrichment=law_enrichment,
                    risk_level=risk_level,
                    fallback_answer=agent_result.integrated_review,
                )
            )
            tokens_out = len(answer.split())

            # 5) Validator
            citations = {
                "law_search": self._summarize_search_results(law_data, used_search_query),
                "law_context": self._summarize_law_enrichment(law_enrichment),
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
