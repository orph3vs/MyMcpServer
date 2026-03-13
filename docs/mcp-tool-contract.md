# MCP Tool Contract

`src/mcp_stdio_server.py`는 stdio 기반 MCP 서버를 제공합니다.

실행:
```bash
python -m src.mcp_stdio_server
```

지원 메서드:
- `initialize`
- `tools/list`
- `tools/call`

노출되는 tool:
- `ask`
  - 입력: `user_query`, `context?`, `request_id?`
- `answer_with_citations`
  - 입력: `user_query`, `context?`, `request_id?`
- `search_law`
  - 입력: `query`
- `get_article`
  - 입력: `law_id`, `article_no`
- `get_version`
  - 입력: `law_id`
- `validate_article`
  - 입력: `law_id`, `article_no`

설계 원칙:
- `/tools/*` HTTP 엔드포인트와 동일한 기능을 MCP tool로 노출합니다.
- `ask`와 `answer_with_citations`는 같은 파이프라인을 호출합니다.
- `answer_with_citations`는 모델 자동선택을 돕기 위한 법률 Q&A용 대표 alias입니다.
- `/ask`는 요약된 citation 구조를 반환합니다.
- 원본 API payload가 필요하면 `search_law`, `get_article`, `get_version`, `validate_article`를 직접 호출합니다.

반환 형식:
- MCP `tools/call` 결과는 `content[0].text`에 JSON 문자열을 담아 반환합니다.
- tool 내부 오류는 JSON-RPC 오류가 아니라 `isError=true`인 tool result로 반환합니다.
