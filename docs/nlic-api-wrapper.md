# NLIC API Wrapper

`src/nlic_api_wrapper.py`는 국가법령정보센터 API 래퍼입니다.

## 기능
- `search_law(query)`
- `get_article(law_id, article_no)`
- `get_version(law_id)`
- `validate_article(law_id, article_no)`

## get_article 조회 전략
- 사용자 입력 조문번호(`제1조`, `제10조의2`)를 유지한 채 응답에 포함합니다.
- 내부적으로는 공식 Open API `JO` 형식 후보를 함께 생성합니다.
- 예:
  - `제1조` -> `["제1조", "000100"]`
  - `제10조의2` -> `["제10조의2", "001002", "001000"]`
- 우선 시도 순서:
  - `lawService.do target=law`
  - `lawService.do target=lawjosub`
  - 필요 시 레거시 raw 조문번호 조합 재시도
  - 실패 시 `law` 조회로 `MST`를 추출한 뒤 `MST + JO`로 재시도
- 디버그 확인용 필드:
  - `matched_via`
  - `attempted_queries`
  - `article_candidates`

## OC 값
- OC 값은 코드/문서에 하드코딩하지 않습니다.
- 실행 시 환경변수 `NLIC_OC`로 주입하거나 초기화 인자 `oc`로 전달합니다.

## 캐시
- 메모리 TTL 캐시 사용 (`cache_ttl_seconds`, 기본 300초)
- 동일 파라미터 요청은 캐시에서 반환
- `clear_cache()`로 캐시 초기화
