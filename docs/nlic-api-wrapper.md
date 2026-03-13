# NLIC API Wrapper

`src/nlic_api_wrapper.py`는 국가법령정보센터 API 래퍼입니다.

## 기능
- `search_law(query)`
- `get_article(law_id, article_no)`
- `get_version(law_id)`
- `validate_article(law_id, article_no)`

## OC 값
- OC 값은 코드/문서에 하드코딩하지 않습니다.
- 실행 시 환경변수 `NLIC_OC`로 주입하거나 초기화 인자 `oc`로 전달합니다.

## 캐시
- 메모리 TTL 캐시 사용 (`cache_ttl_seconds`, 기본 300초)
- 동일 파라미터 요청은 캐시에서 반환
- `clear_cache()`로 캐시 초기화
