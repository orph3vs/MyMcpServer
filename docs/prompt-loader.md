# Prompt Loader

`prompt_loader`는 요청마다 `system_prompt`와 `orchestration_prompt`를 자동 결합합니다.

## 버전 관리
- 매니페스트: `config/prompts/manifest.json`
- 버전별 파일:
  - `config/prompts/<version>/system_prompt.md`
  - `config/prompts/<version>/orchestration_prompt.md`

## 사용 예시

```python
from src.prompt_loader import build_request_prompt

payload = build_request_prompt(
    user_query="근로기준법 제56조 연장근로수당 요건을 알려줘",
    version="v1",
    context="기준시점: 2025-01-01"
)

# payload = {
#   "prompt_version": "v1",
#   "system": "[SYSTEM PROMPT]... [ORCHESTRATION PROMPT]...",
#   "user": "[CONTEXT]... [USER QUERY]..."
# }
```
