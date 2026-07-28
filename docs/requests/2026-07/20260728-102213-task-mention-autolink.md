---
task_id: 15434
task_url: https://gdc.gemiso.com/tasks/15434
---

# 태스크 언급(#N) 자동 링크 연동

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | server/doc_utils, server/server |
| 날짜 | 2026-07-28 |
| 상태 | done |
| 관련 | doc_utils, server, 20260724-114402-html-autolink |

## 요청 내용

[URL 자동 연동(#409, v0.6.0)](20260724-114402-html-autolink.md)의 **후속 분리 항목**. 설명·댓글 평문에 태스크를 **번호(`#N`)로 언급**하면 해당 태스크 상세 페이지로 자동 링크한다.

- 예: `이슈 #409 참고` → `이슈 <a href="…/tasks/15434">#409</a> 참고`

## 배경

### 현황 (관련 코드 검토)

- URL 자동 연동은 [doc_utils.py](gdc_mcp/doc_utils.py) `_escape_and_linkify`(순수 함수)로 구현됨 — description·댓글이 공유하는 `normalize_description`→`description_to_html` 경로에서 동작.
- 태스크 상세 URL은 내부 **id** 기준(`_task_url`=`{_WEB_URL}/tasks/{id}`, [server.py](gdc_mcp/server.py))인데 사용자는 **번호**(`#409`)로 언급 → **번호→id 변환에 REST 조회 필수**.
- 번호 해석 메커니즘은 이미 존재: [server.py](gdc_mcp/server.py) `_resolve_task`가 `client.get(_TASKS, params={"project", "search", "page_size"})`로 조회하고 결과에 `id`·`number`·`title`을 담는다. 번호는 **프로젝트 스코프**로 유일.
- ∴ 번호 링크는 **순수 함수 밖(서버 계층)** 에서 `client` 기반 resolver로 처리해야 한다.

### 결정 사항

| # | 항목 | 결정 |
|---|------|------|
| 1 | 언급 문법 | `#N`(N=숫자). 경계 규칙 `(?<![\w#])#(\d+)\b` — 앞이 영숫자·`_`·`#`가 아니고 뒤가 숫자 경계. `이슈 #409`·`(#409)` O / `#fff`(색상)·`v2#3`의 `#3`은 앞이 숫자라 X, 마크다운 헤더 `# 제목`은 `#` 뒤 공백이라 X |
| 2 | 미해결 번호 | 현재 프로젝트에 없는 `#N`은 **평문 유지**(링크 안 함) |
| 3 | 링크 표시 텍스트 | **확정**: `#N`만 링크(`<a>#409</a>`), 바로 뒤에 `(제목)`을 평문으로 본문 삽입. 예: `이슈 #409 참고` → `이슈 <a>#409</a> (HTML 변환시 링크 연동) 참고` |
| 4 | 스코프 | **현재 컨텍스트 프로젝트 내 번호만**. 크로스 프로젝트/워크스페이스는 이번 범위 제외 |
| 5 | URL 내부 오탐 | 이미 `<a>`로 감싼 URL(프래그먼트 `#409` 포함 가능)은 재처리 금지 |

### 설계(안)

- `_escape_and_linkify(text, resolve_task_url=None)` — **선택적 콜백**(num→url|None) 파라미터 추가. 콜백 없으면(순수 테스트·문서 경로) 태스크 언급은 평문 유지 → **하위 호환**. URL 링크化와 **같은 escape 패스**에서 처리해 URL 내부 `#N` 오탐을 원천 차단(URL 구간은 이미 `<a>`로 소비됨).
- 서버 계층에서 `client` 기반 resolver 주입 — description(create/update/edit)·댓글(add/update)이 공유하는 `normalize_description` 호출부에 연결.
- **번호→id 조회 최소화** — 텍스트 내 `#N` **디둡** 후 프로젝트 태스크 목록 1회 조회로 매핑(불필요한 왕복 금지 — project.md 성능 규칙).

## 작업 결과

- [x] (착수 전) 결정 3(표시 텍스트) 사용자 확정 — `#N` 링크 + `(제목)` 평문
- [x] `_escape_and_linkify`에 `resolve_task` 콜백 추가(기본 None=하위 호환) + `_MENTION_RE=(?<![\w#])#(\d+)\b` — 순수 로직. `_escape_mentions`로 비-URL 구간만 언급 처리(URL 구간 선소비 → 프래그먼트 오탐 없음), `description_to_html`·`normalize_description`에 콜백 전달
- [x] 번호→url resolver(서버 `_task_resolver`, `client`) — `mention_numbers`로 디둡, **번호 필터 부재**(API 미지원 실증) → `-number` 목록을 `page_size=200`·최대 5페이지 조회로 매핑(미해결·상한초과·조회실패는 평문). 5개 `normalize_description` 호출부(create/update/sync_doc/task_from_doc/댓글) 연결, 언급 있을 때만 프로젝트 조회
- [x] pytest — 순수 경로(mock resolver): 제목 괄호 삽입/미해결 평문/무주입 하위호환/경계(색상·단어뒤)/URL프래그먼트 오탐 없음/제목 이스케이프/중복 링크/normalize 전달/`mention_numbers` 디둡 — **9건 추가, 전체 111건 통과**
- [x] 로컬 사전 검증 — `45 이슈관리 테스트`. 서버 구버전 → 업데이트 서버코드(`_task_resolver`+`normalize_description`) 직접 호출: `#5`→/tasks/15446·`#3` 링크, `#999`(없음) 평문. 실제 GDC 댓글 저장·재조회로 **`#N` 앵커·`(제목)`·미해결 평문 보존** 확인(검증 댓글 #42666 남김)
- [x] `plugin.json` version `0.6.0` → `0.6.1` 상향(URL 링크 연동에 이어지는 후속이라 patch)
- [x] 최종 검토 반영 — ① `doc_utils.is_html` 추출 + 서버 `_has_task_mentions` 게이트로 **이미 HTML인 본문/댓글은 번호 조회 자체를 생략**(update_task·댓글 경로의 헛된 `GET /tasks/{id}/` + 목록 스캔 제거), ② 목록 조회에 `ordering=-number` **명시**(서버 기본값 의존 제거 → 상한 스캔 범위 고정), ③ README에 자동 링크 동작 문단 추가(URL·`#N` 공통, v0.6.0분 누락 포함), ④ 문서 결정표 정규식·코드 링크 정합. pytest **112건 통과**

## 참고 사항

- 변경 파일: [gdc_mcp/doc_utils.py](gdc_mcp/doc_utils.py), [gdc_mcp/server.py](gdc_mcp/server.py)
- **번호 조회 비용**: gdc-service에 태스크 번호 필터·번호 검색이 없어(`TaskFilter`·BM25 search 실증) 목록을 페이지로 훑는다. ≤200 태스크 프로젝트는 1회 조회로 해결, 초과분·미해결·조회실패는 **평문 유지**(graceful). 언급 없는 본문/댓글은 추가 REST 0.
- **링크되지 않는 경우(모두 평문 유지)**: 현재 프로젝트에 없는 번호 / 숨김(archived) 태스크(목록 미포함) / 페이지 상한 초과 / 조회 실패 / **입력이 이미 HTML**(변환 자체를 통과시키므로 언급 해석 안 함 — URL 자동 링크와 동일 정책).
- 검증용으로 남긴 댓글(#42666, WS3/45)은 사용자가 확인 목적으로 **의도적으로 보존** 중 — 확인 후 삭제 대상.
- 반영은 플러그인 재설치/서버 재기동 후 도구 호출부터 적용(실행 세션은 기동 시점 코드 사용).
