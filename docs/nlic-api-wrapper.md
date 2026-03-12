# NLIC API Wrapper

`src/nlic_api_wrapper.py`는 국가법령정보센터 API 래퍼입니다.

## 기능
- `search_law(query)`
- `get_article(law_id, article_no)`
- `get_version(law_id)`
- `validate_article(law_id, article_no)`

## OC 값
- 기본 OC 값은 `orph3vs_mcpserver`로 설정되어 있습니다.
- 필요 시 초기화 인자로 다른 값을 주입할 수 있습니다.

## 캐시
- 메모리 TTL 캐시 사용 (`cache_ttl_seconds`, 기본 300초)
- 동일 파라미터 요청은 캐시에서 반환
- `clear_cache()`로 캐시 초기화
