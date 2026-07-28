# 태스크 검색·상세 필드 보강·멘션/알림 조회 MCP 도구 추가

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | server/gdc_mcp |
| 날짜 | 2026-07-28 |
| 상태 | partial |
| 관련 | server, client |

## 요청 내용

MCP 기능 검토에서 도출한 후보 중 3건을 한 묶음으로 처리한다. 세 항목 모두 **gdc-service는 무수정**이고 이 레포(클라이언트)에서만 작업한다.

1. **`search_tasks`** — 현재 프로젝트 스코프의 키워드 + 다중 필터 태스크 검색 도구 신설
2. **`get_task` 응답 필드 보강 + 프로젝트 상세 TTL 캐시** — 누락 필드 노출(추가 왕복 0), 중복 REST 왕복 제거
3. **`list_my_notifications` / `list_my_mentions`** — 내 알림·멘션 조회 도구 신설(**조회 전용**)

검토에서 함께 나온 **태그(tags) 노출**은 실사용이 없어 보류한다(후속 대상).

### 결정 사항 (사용자 확인 완료)

| 결정 | 값 |
|------|-----|
| 알림/멘션 범위 | **알림 + 멘션 둘 다** — 성격이 달라 서로 대체되지 않음 |
| 읽음 처리(쓰기) | **미포함** — 조회 전용. 에이전트가 웹 UI 읽음 상태를 바꾸지 않음 |
| 검색 스코프 | **현재 레포 프로젝트 고정** — 기존 `list_tasks`·`_resolve_task`와 동일 |

### 1) `search_tasks` 설계

호출: `GET /api/tasks/tasks/` (기존 `_TASKS` 재사용). 서버는 `BM25SearchFilter`(BM25 + pg_trgm 하이브리드, `search` 파라미터)와 `TaskFilter`를 제공한다.

| MCP 파라미터 | 서버 파라미터 | 비고 |
|---|---|---|
| `query` | `search` | 생략 가능(필터만으로도 조회) |
| `status` / `priority` / `task_type` | 동명(CSV `BaseInFilter`) | 리스트 → CSV 변환 |
| `assignee` / `participant` | `assignee` / `participant` | 이름·id 허용 → `_resolve_members`로 해석 |
| `customer` | `customer` | 이름·id 허용 → `_resolve_customer` 재사용 |
| `planned_end_from` / `planned_end_to` | `planned_end_date_from` / `_to` | `overdue`/`undated`의 서버측 대체 |
| `root_only` | `root_only` | 최상위 태스크만. **`query`와 동시 지정 불가**(아래 참조) |
| `not_finished` | `status=<미완료 CSV>` | 기존 도구와 동일 규약. `status` 명시 시 그 값이 우선 |
| `ordering` | `ordering` | 서버 `ordering_fields` 화이트리스트 검증 후 전달 |
| `limit` | `page_size` | 기본 20 |

- 응답은 기존 `_task_summary`를 그대로 재사용해 다른 목록 도구와 표기를 통일한다.
- `overdue`는 **서버 필터**(`planned_end_date_to=<어제>`)로 처리한다. 기존 두 도구와 동일하게 `not_finished`와 **직교**로 둔다(묶지 않는다). `undated`는 서버에 "날짜 없음" 필터가 없어 클라이언트 필터를 유지하되, 기존 도구처럼 **`page_size=200` 선취**(서버 상한 `TaskPagination.max_page_size=200`) 후 거른다 — 200건 초과 프로젝트에서 누락 가능함을 docstring에 명시한다.
- `not_finished`가 참일 때 필요한 미완료 상태 목록은 2)의 캐시를 타므로 왕복이 늘지 않는다.
- **정렬은 관련도순이 아니다** — `TaskViewSet.ordering = ["-number"]`가 기본값이고 백엔드 순서가 `DjangoFilter → BM25 → KoreanOrdering`이라, BM25가 매긴 `_search_priority` 정렬을 OrderingFilter가 **항상** 덮어쓴다(`ordering` 미전송 시에도 `view.ordering`으로 폴백). 즉 결과는 "가장 관련 있는 N건"이 아니라 "매칭 중 번호가 큰 N건"이다. docstring에 명시하고, 응답에 **서버 총 매칭 수(`count`)를 함께 실어** 잘림을 인지할 수 있게 한다.
- **`root_only` + `query` 배타** — BM25는 매칭 ID를 부모 치환 없이 반환하고([search.py:45-49](../../../../gdc/gdc-service/backend/tasks/search.py)) `root_only`는 `parent IS NULL`로 거르므로, 둘을 함께 쓰면 **매칭된 하위 태스크가 통째로 사라진다**(웹 UI는 `subtree_match`로 조상 체인을 붙여 해결). 동시 지정 시 오류로 안내한다.
- **컨텍스트 미설정 시 오류** — 프로젝트 없이 호출하면 BM25 스코프(`project_id__in=queryset.values("project_id")`)가 접근 가능한 전 프로젝트로 퍼지므로, `list_tasks`와 동일하게 `ValueError`로 차단한다.

### 2) `get_task` 보강 + 프로젝트 상세 캐시

**(a) 누락 필드** — 아래는 모두 이미 상세 응답(`TaskSerializer.Meta.fields`)에 담겨 오는 값이라 **추가 REST 왕복 0**이다. 현재 `get_task`([server.py:1029-1051](../../../gdc_mcp/server.py#L1029-L1051))는 이들을 버리고 있다.

`actual_start_date`, `actual_end_date`, `customer`/`customer_name`, `weight`, `is_pinned`, `is_archived`, `tag_list`, `participants_detail`, `creator_name`, `created_at`/`updated_at`, `mention_count`

`update_task`로 쓸 수 있는 필드(실제 날짜·고객사·비중·고정)를 **읽을 수 없어 왕복 검증이 불가능한** 상태를 해소한다.

**(b) 프로젝트 상세 캐시** — 현재 `/api/projects/{id}/`를 각자 GET하는 지점:

| 함수 | 위치 |
|---|---|
| `_not_finished_names` | [server.py:323-325](../../../gdc_mcp/server.py#L323-L325) |
| `_status_category` | [server.py:943-957](../../../gdc_mcp/server.py#L943-L957) |
| `_done_status_name` | [server.py:1183-1196](../../../gdc_mcp/server.py#L1183-L1196) |
| `_in_progress_status_name` | [server.py:1199-1210](../../../gdc_mcp/server.py#L1199-L1210) |
| `_resolve_members` | [server.py:482-483](../../../gdc_mcp/server.py#L482-L483) |
| `_resolve_mention_usernames` | [server.py:1370-1371](../../../gdc_mcp/server.py#L1370-L1371) |
| `_apply_progress_sync` | [server.py:1104](../../../gdc_mcp/server.py#L1104) |
| `get_context` / `set_context` / `get_project_enums` | [server.py:199](../../../gdc_mcp/server.py#L199), [272](../../../gdc_mcp/server.py#L272), [292](../../../gdc_mcp/server.py#L292) |

`task_from_doc` 한 번에 `_status_category` + `_done_status_name`(또는 `_in_progress_status_name`)이 겹쳐 최소 2회, `list_my_tasks`는 프로젝트 미설정 시 결과 태스크마다 `_not_finished_names`를 호출한다(내부 `cache` dict로 프로젝트 단위 중복은 이미 방지). AGENTS.md의 "불필요한 REST 왕복 감축" 규칙에 걸리는 지점이다.

- **방식**: `client.py`가 아니라 `server.py`에 짧은 TTL(60초) 프로세스 캐시 헬퍼 `_project(project_id)` 하나를 두고, 위 함수들이 직접 `client.get` 대신 이를 호출한다.
- **무효화**: `set_context`는 캐시를 비운다. 프로젝트 설정(상태 enum·멤버)은 세션 중 거의 바뀌지 않으므로 TTL만으로 충분하다.
- **범위 밖**: 태스크 상세(`/api/tasks/tasks/{id}/`)는 캐시하지 않는다 — 편집 직후 재조회가 잦아 stale 위험이 실익보다 크다.

### 3) 알림·멘션 조회

| 도구 | 엔드포인트 | 파라미터 | 응답 |
|---|---|---|---|
| `list_my_notifications` | `GET /api/notifications/` | `is_read`(미읽음만), `limit`(→ `page_size`, **최대 99**) | 유형(7종)·제목·발신자·태스크 번호/제목·프로젝트·읽음 여부·생성 시각 + `unread_count` |
| `list_my_mentions` | `GET /api/dashboard/mentions/` | `mention_type`(mentioned/authored/both), `project_id`, `date_from`/`date_to`, `search`, `limit`(**서버 20건 고정** — 아래 참조) | 작성자·태스크 번호/제목·프로젝트·본문 미리보기(100자)·생성 시각 |

- 알림 유형(`mention`/`description_mention`/`assignee_change`/`task_comment`/`participant_added`/`task_status_changed`/`task_updated`)은 status·priority와 동일하게 **한글 라벨 매핑 dict**를 둔다.
- 미읽음 수는 `/api/notifications/unread-count/`로 1회 더 호출한다(전체 건수 파악용, 응답에 없음).
- **멘션 `limit`은 서버에서 안 먹는다** — `MyMentionListView`는 `pagination_class` 미지정 → 전역 `PageNumberPagination`(`PAGE_SIZE=20`)이고 전역 설정에 `page_size_query_param`이 없어 **20건 고정**이다. 기본 `limit`을 20으로 두고, 초과 요청 시 `page`를 순회해 채운다.
- **멘션 미리보기는 HTML을 벗겨서 재가공한다** — 서버의 `content_preview`는 `mention.content[:100]` **raw 슬라이스**라 댓글 HTML(v0.6.4 멘션 하이라이트 span 포함) 태그 중간이 잘린다(알림 serializer는 `strip_tags`를 하지만 멘션은 안 한다). 클라이언트에서 태그 제거 후 100자로 다시 자른다.
- 두 도구 모두 `_task_url`로 태스크 링크를 붙여 곧바로 `get_task`/`open_task`로 이어지게 한다.
- **스코프**: 알림은 서버가 수신자 기준으로만 필터하므로 워크스페이스 제한이 없다(전 워크스페이스 혼재 — docstring에 명시). 멘션은 현재 레포 컨텍스트의 `workspace`/`project_id`를 기본 적용한다.
- 읽음 처리(`mark_read`/`read-all`)는 이번 범위에서 제외한다.

## 배경

### 검색 도구 부재

노출된 목록 도구는 `list_my_tasks`(본인 고정)·`list_tasks`(담당자 지정) 둘뿐이고, 서버 검색은 `_resolve_task`의 제목 해석 경로([server.py:587](../../../gdc_mcp/server.py#L587))에서 내부적으로만 쓰인다. "'로그인' 관련 태스크", "이번 주 마감인 개발 유형 태스크" 같은 질의를 도구로 표현할 수 없다.

또한 기존 두 도구의 `overdue`/`undated`는 200건을 받아 클라이언트에서 거르는 방식([server.py:384-386](../../../gdc_mcp/server.py#L384-L386))이라 200건을 넘는 프로젝트에서 누락이 생길 수 있다. `search_tasks`는 처음부터 서버 필터(`planned_end_date_to`)로 처리한다.

### 기존 목록 도구는 유지

`list_my_tasks`/`list_tasks`는 시그니처를 바꾸지 않는다. 슬래시 커맨드 `/gdc-my-tasks`·`/gdc-tasks`와 프롬프트가 이미 이 두 도구에 1:1로 묶여 있어, 필터를 흡수시키면 커맨드 계층까지 연쇄 변경된다. 검색·필터는 신규 도구로 분리한다.

## 작업 결과

### Phase 1 — `search_tasks` 도구 추가

- [x] 순수 헬퍼 pytest 선행 작성 — `tests/test_search_params.py` 25건(리스트→CSV, `status`>`not_finished` 우선순위, `overdue`→`planned_end_date_to`, `undated`→200 선취, `ordering` 화이트리스트, `query`+`root_only` 배타, 날짜 형식·순서)
- [x] `search_tasks` 도구 구현 — `_search_params`(순수 조립) + 도구 본체. `_task_summary`·`_finalize_task_list` 재사용, 멤버/고객사는 기존 `_resolve_members`·`_resolve_customer` 경유(프로젝트 상세 1회만 받아 재사용 — `_not_finished_names`에 `project=` 인자 추가), 응답에 `total_matched` 동봉, 컨텍스트 미설정 시 `ValueError`
- [x] docstring 작성 — 현재 프로젝트 고정 스코프, 결과가 관련도순이 아님(번호 내림차순), `undated` 클라이언트 필터 한계(200건), `query`+`root_only` 배타, `query` 생략 가능 명시
- [x] 로컬 사전 검증(Phase 1분) — WS3 / 45 이슈관리 테스트에 **읽기 전용** 호출: `query="테스트"` 1건 매칭, `not_finished` 11건, `undated` 정상 동작, 날짜 필터가 서버에 실제 적용됨 확인(전 태스크가 날짜 미정이라 0건 = 정상). 데이터 생성 없음, 컨텍스트 변경 없음
- [x] `uv run python -m pytest tests/` 142건 통과(신규 25건 포함, 회귀 0)

### Phase 2 — `get_task` 필드 보강 + 프로젝트 상세 캐시

- [ ] `_project(project_id)` TTL 캐시 헬퍼 추가 + `set_context` 무효화, pytest(만료·무효화·히트 시 호출 0회)
- [ ] 프로젝트 상세를 GET하는 8개 지점을 `_project` 경유로 교체(`project=` 인자로 이미 재사용 중인 경로는 그대로 유지)
- [ ] `get_task` 응답에 누락 필드 추가 + docstring 갱신

### Phase 3 — 알림·멘션 조회 도구 추가

- [ ] 알림 유형 한글 라벨 매핑 + `list_my_notifications` 구현(미읽음 필터, `unread_count` 동봉)
- [ ] `list_my_mentions` 구현(현재 레포 컨텍스트 기본 적용, `mention_type`/기간/검색, **20건 고정 페이지 순회 + 미리보기 HTML 제거 후 100자 재가공**)
- [ ] 두 도구 docstring — 알림은 전 워크스페이스 혼재, 멘션은 컨텍스트 스코프, 읽음 처리 미지원 명시

### Phase 4 — 검증·배포

- [ ] `uv run python -m pytest tests/` 전체 통과(회귀 0)
- [ ] 로컬 사전 검증 — WS3 / 45 이슈관리에서 세 도구 실제 호출, 임시 데이터 삭제·컨텍스트 원복
- [ ] `plugin.json` 버전 범프(v0.7.0) + `README.md` 도구표 갱신 + `docs/INDEX.md` 이력 추가

## 참고 사항

### 커맨드/프롬프트 계층

이번 3개 도구에는 대응 슬래시 커맨드를 만들지 않는다. 자연어 호출로 충분하고, 커맨드를 늘리면 `/gdc-*` 1:1 대응 규칙상 MCP 프롬프트도 함께 늘어난다. 사용해 보고 반복 호출 패턴이 생기면 그때 커맨드로 승격한다.

### 범위 밖 (후속 후보)

- 태그 노출 + 이름 해석 (`get_project_enums`에 `tags` 추가) — 실사용 없어 보류
- 연관 태스크 링크 생성/삭제(`/api/tasks/links/`), 변경 이력(`/api/tasks/histories/`), 일괄 수정(`bulk_update`), 첨부 목록
- 주간 싱크/대시보드 요약(`/api/dashboard/weekly-sync/`)
- 알림 읽음 처리(`mark_read`/`read-all`)
- gdc-service에 태스크 `number` 필터 추가 — `_task_resolver`의 최대 5페이지 스캔([server.py:57-95](../../../gdc_mcp/server.py#L57-L95))을 근본 해결하지만 **본체 수정**이라 별도 협의 대상
- `create_task`/`update_task`의 400 응답 한글 변환 — 별건
