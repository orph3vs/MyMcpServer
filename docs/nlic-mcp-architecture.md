# 국가법령정보센터 API 기반 MCP 서버 설계

> 상태: 초안(v1)  
> 관리 원칙: 단계별 프롬프트 지시에 따라 본 문서를 분할/수정한다.

## 1) 목표(요구사항 고정)
이 서버는 다음 5개 목표를 **동시에** 만족해야 한다.

1. 법령 원문 기반 답변
2. 자동 고위험 판단
3. 조건부 멀티에이전트 실행
4. 신뢰도 스코어링
5. 비용 로그 수집

추가 정책:
- 환각 금지
- 추정 금지
- 일반화 금지

---

## 2) 시스템 최상위 아키텍처

```text
[Client / MCP Host]
        |
        v
[MCP Server API Layer]
  - Tool Router
  - Request Validator
  - Auth/Quota
        |
        v
[Orchestrator]
  - Query Normalizer
  - Risk Classifier (자동 고위험 판단)
  - Plan Builder (조건부 멀티에이전트 분기)
  - Confidence Scorer
  - Guardrail Enforcer (환각/추정/일반화 차단)
        |
        +-------------------------------+
        |                               |
        v                               v
[Retriever Agent]                 [Policy/Reasoning Agent]
  - 국가법령정보센터 API 호출            - 쟁점 정리(원문 근거 필수)
  - 원문 조문/부칙/별표 수집            - 답변 구조화
  - 버전/시점 메타데이터 추출           - 고위험 시 보수적 출력
        |                               |
        +---------------+---------------+
                        v
                [Evidence Merger]
                - 조문 근거 단위 정렬
                - 출처/버전/조문번호 정규화
                        v
                [Answer Composer]
                - 인용 우선 템플릿
                - 비근거 문장 차단
                        v
                [Response + Confidence + Cost Log]
```

핵심 원칙:
- 모든 최종 진술 문장은 근거 조문(원문/조문번호/법령명/시점)에 역추적 가능해야 한다.
- 근거가 없는 문장은 출력하지 않는다.

---

## 3) 컴포넌트 상세 설계

### A. MCP Server API Layer
- `tool.search_law_text`: 질의 기반 조문 검색
- `tool.answer_with_citations`: 근거 포함 답변 생성
- `tool.get_risk_assessment`: 고위험 판단 결과 조회
- `tool.get_cost_report`: 호출/토큰/시간/실패율 비용 리포트

입력 검증:
- 필수 필드(질문, 관할, 기준시점)
- 금지 요청(근거 없는 해석 강제 등) 차단

### B. Query Normalizer
- 사용자 질문에서 법령명 후보, 쟁점 키워드, 시점(시행일/질의기준일) 추출
- 추출 실패 시 즉시 불확실성 플래그 + 추가정보 요청

### C. Retriever Agent (법령 원문 수집)
- 국가법령정보센터 API 어댑터를 통해 다음 단위 수집:
  - 법령 기본정보
  - 조문 본문
  - 부칙
  - 별표/서식(해당 시)
- 수집 결과를 `Evidence` 스키마로 정규화

### D. Risk Classifier (자동 고위험 판단)
고위험 규칙(예시, 정책으로 관리):
- 형사/행정처분/과징금/벌칙/조세불복/자격상실 관련 질의
- 시점 민감(법 개정 경계일 인접)
- 근거 조문 상충 또는 다중 해석 가능
- 사용자 요청이 확정적 법률자문 형태

출력:
- `risk_level`: low | medium | high
- `risk_reasons`: 규칙 ID 목록
- `required_flow`: single_agent | multi_agent | refuse

### E. 조건부 멀티에이전트 오케스트레이션
분기 규칙:
- `low`: 단일 에이전트(검색+답변)
- `medium`: 2-에이전트(검색/검증 분리)
- `high`: 3-에이전트(검색/검증/안전검토) + 보수 출력

권장 에이전트 구성:
1. Retrieval Agent: 원문/메타데이터 확보
2. Verification Agent: 조문-주장 정합성 검증
3. Safety Agent(고위험 시): 표현 수위 조정, 단정 차단, 추가 확인 요구

### F. Guardrail Enforcer (환각·추정·일반화 차단)
- 문장 단위 검사:
  - `has_evidence_span == false` 문장 제거
  - “통상/보통/일반적으로” 같은 일반화 표현 금지
  - “~일 가능성” 등 추정 표현 금지(근거 기반 조건문만 허용)
- 불충분 시 응답 전략:
  - 답변 거절이 아니라 `근거 부족` 상태로 반환
  - 추가로 필요한 조문 범위/시점 명시

### G. Confidence Scorer (신뢰도 스코어링)
신뢰도는 단순 LLM 자기평가가 아니라 **근거 기반 계산식**으로 산정:

`confidence = w1*evidence_coverage + w2*citation_precision + w3*version_consistency + w4*agent_agreement - w5*risk_penalty`

권장 피처:
- evidence_coverage: 핵심 주장 중 근거 연결 비율
- citation_precision: 인용 조문 정확도(조문번호/항/호 일치)
- version_consistency: 기준시점 대비 법령 버전 일치 여부
- agent_agreement: 다중 에이전트 결론 합치도
- risk_penalty: 고위험 규칙 점수

출력 형식:
- `confidence_score`: 0.0~1.0
- `confidence_breakdown`: 피처별 점수
- `confidence_reason`: 점수 산출 근거

### H. Cost Logger (비용 로그 수집)
수집 단위:
- 요청 ID
- API 호출 횟수/지연시간/실패율
- LLM 입력/출력 토큰
- 에이전트별 실행 시간
- 재시도 횟수
- 총 비용(정책상 단가 적용)

활용:
- 고위험 요청당 평균 비용
- 멀티에이전트 전환 임계값 최적화
- 실패 유형(타임아웃/파싱/근거부족) 분석

---

## 4) 데이터 계약(스키마 초안)

### `Evidence`
```json
{
  "law_id": "string",
  "law_name": "string",
  "article": "제00조",
  "paragraph": "제0항",
  "item": "제0호",
  "text": "원문",
  "effective_date": "YYYY-MM-DD",
  "source_url": "string",
  "retrieved_at": "ISO-8601"
}
```

### `RiskAssessment`
```json
{
  "risk_level": "low|medium|high",
  "risk_reasons": ["R001", "R014"],
  "required_flow": "single_agent|multi_agent|refuse"
}
```

### `AnswerPacket`
```json
{
  "answer": "근거 기반 답변",
  "citations": [
    {
      "law_name": "...",
      "article": "제00조",
      "source_url": "..."
    }
  ],
  "confidence_score": 0.0,
  "confidence_breakdown": {
    "evidence_coverage": 0.0,
    "citation_precision": 0.0,
    "version_consistency": 0.0,
    "agent_agreement": 0.0,
    "risk_penalty": 0.0
  },
  "cost": {
    "tokens_in": 0,
    "tokens_out": 0,
    "api_calls": 0,
    "latency_ms": 0,
    "estimated_cost": 0.0
  }
}
```

---

## 5) 요청 처리 플로우(엔드투엔드)

1. 요청 수신 및 유효성 검사
2. 질의 정규화(법령명/쟁점/시점)
3. 1차 원문 검색
4. 자동 고위험 판단
5. 위험도 기반 에이전트 플로우 분기
6. 근거-주장 매핑 검증
7. 신뢰도 계산
8. 비용 로그 기록
9. 근거 포함 최종 응답 반환

실패 처리 원칙:
- 외부 API 실패 시 재시도(지수 백오프) 후 실패 사유 명시
- 근거 불충분 시 단정 답변 대신 “확인 필요 항목” 반환

---

## 6) 운영/거버넌스
- 규칙 버전 관리: `risk_rules_v*`, `guardrail_rules_v*`
- 감사 가능성: 요청별 근거 체인 저장(질문→조문→문장)
- 품질지표:
  - citation missing rate
  - evidence mismatch rate
  - high-risk safe-response rate
  - cost per successful answer

---

## 7) 구현 우선순위(권장)

### Phase 1 (MVP)
- 국가법령정보센터 API 어댑터
- 근거 인용 포함 단일 에이전트 답변
- 기본 비용 로그

### Phase 2
- 자동 고위험 판단 룰엔진
- 조건부 멀티에이전트 분기
- 신뢰도 점수 계산

### Phase 3
- 고위험 안전검토 에이전트 고도화
- 비용-성능 최적화(동적 에이전트 선택)
- 감사/리포팅 대시보드

---

## 8) 절대 금지 정책의 기술적 강제
- 근거 없는 문장 출력 차단(하드 필터)
- 인용 누락 시 응답 실패 처리
- 법령 시점 미확정 시 확정적 결론 금지
- 모델 프롬프트가 아닌 서버 레벨 검증으로 강제

위 설계는 “법령 원문 근거 우선”을 시스템 제약으로 두어, 환각·추정·일반화를 구조적으로 억제한다.
