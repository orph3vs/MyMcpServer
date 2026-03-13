# 실행 체크리스트 (비개발자용)

아래 순서대로 실행하면 "정상 동작" 여부를 빠르게 확인할 수 있습니다.

## 1) 테스트 통과 확인
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

정상 기준:
- 마지막에 `OK`
- `Ran ... tests` 출력

## 2) 로컬 단건 실행
```bash
python run_local.py "개인정보 제3자 제공 기준" --context "기준시점: 2025-01-01"
```

정상 기준:
- JSON 출력
- `request_id`, `mode`, `score` 필드 존재

## 3) HTTP 서버 헬스체크
터미널 A:
```bash
python -m src.http_server
```

터미널 B:
```bash
curl http://localhost:8000/health
```

정상 기준:
- `{"status": "ok"}` 응답

## 4) HTTP 질의 요청
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"user_query":"개인정보 위탁과 제3자 제공 차이","context":"기준시점: 2025-01-01"}'
```

정상 기준:
- JSON 응답
- `request_id`, `risk_level`, `mode`, `score` 필드 존재

## 참고
- 네트워크 환경 제약이 있으면 외부 NLIC 호출 단계에서 `error`가 나올 수 있습니다.
- 이 경우에도 파이프라인/에러 처리/로그 저장 동작 자체는 정상일 수 있습니다.
