---
task_id: 15223
task_url: https://gdc.gemiso.com/tasks/15223
---

# 하위 태스크 조회 기능 추가

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | server/get_task, server/api, commands |
| 날짜 | 2026-07-23 |
| 상태 | done |
| 관련 | server, client, commands/gdc-tasks |

## 요청 내용

MCP 전반에 **하위 태스크·연관 태스크 조회** 기능을 붙인다. 태스크 #346(15223)의 요구는 다음과 같다.

- **AS-IS**: 상위 태스크의 링크(ID)를 직접 알려줘야만 하위 태스크를 조회할 수 있음.
- **TO-BE**:
  - 한 태스크의 **하위 태스크**와 **연관 태스크**를 모두 조회 가능.
  - 태스크를 **ID뿐 아니라 제목으로도** 조회 가능.

> 요구는 모두 **조회(read)** 범위다. 링크/하위 관계의 **생성·수정은 범위 밖**으로 둔다(상위 지정은 이미 `create_task`/`update_task`의 `parent`로 가능).
>
> 태스크 description은 라벨(AS-IS/TO-BE) 평문이며 댓글은 0개다. 추가 의사결정 맥락 없이 description 기준으로 정리했다.

## 배경 (코드 검토 결과)

서버(gdc-service) 측 데이터·API는 이미 하위/연관 관계를 제공하고 있으며, **부족한 것은 MCP 클라이언트가 이를 노출·활용하지 않는 점**이다. 이 레포는 클라이언트 브리지이므로 서버 본체는 수정하지 않는다.

**1. 서버는 이미 하위/연관을 반환한다.**
- 태스크 상세 `GET /api/tasks/tasks/{id}/`(retrieve)는 `TaskDetailSerializer`로 응답하며 다음을 포함한다 ([serializers.py:1378-1393](../../../../gdc/gdc-service/backend/tasks/serializers.py)):
  - `sub_tasks[]` — 하위 태스크 목록(`TaskListSerializer`).
  - `outgoing_links[]` / `incoming_links[]` — 연관 태스크 링크(`TaskLinkSerializer`: `link_type`, 대상/원본 `title`·`number`).
  - `parent` — 상위 태스크 id.
- 제목 검색: 목록 `GET /api/tasks/tasks/?search=<제목>` 은 BM25+trgm 하이브리드 검색을 지원한다 ([search.py:7](../../../../gdc/gdc-service/backend/tasks/search.py)).
- 연관 링크 전용: `GET /api/tasks/links/?source_task=&target_task=` ([views.py:1451](../../../../gdc/gdc-service/backend/tasks/views.py)).

**2. MCP는 이 필드들을 드롭한다.**
- [server.py:741 `get_task`](../gdc_mcp/server.py) 는 `t`에서 필요한 스칼라 필드만 골라 반환하고 `parent`·`sub_tasks`·`*_links`를 버린다(현재 `get_task`가 목록 API가 아닌 상세 API를 호출하므로 이 필드들이 응답 안에 있음에도 사용하지 않음).
- 태스크 식별은 어디서나 **정수 ID 전용** — 제목→태스크 해석 헬퍼가 없다.

→ 결론: **얇은 클라이언트 확장**만으로 TO-BE를 달성할 수 있다. 새 서버 엔드포인트 불필요, 새 REST 왕복 최소.

## 작업 결과

### Phase 1 — `get_task`에 하위/연관/상위 노출
- [x] `get_task` 반환에 필드 추가: `parent`(상위 요약), `sub_tasks`(하위 요약 목록), `related_tasks`(outgoing+incoming 통합: 방향·`link_type`·대상 번호/제목/URL). → `_parent_summary`·`_related_tasks` 헬퍼 추가([server.py](../gdc_mcp/server.py)).
- [x] 각 항목은 요약 형태로 압축해 응답 비대화 방지. `_finalize_task_list`의 항목 dict를 공용 `_task_summary(t)` 헬퍼로 추출해 `list`·`get_task`가 재사용(인라인 중복 제거).
- [x] docstring에 "하위/연관/상위 태스크 포함" 명시(자연어 호출 유도).

### Phase 2 — 제목 기반 조회(ID or 제목 해석)
- [x] `_resolve_task(ctx, id_or_title)` 헬퍼 추가: 정수/정수문자열이면 ID, 그 외 문자열이면 현재 프로젝트에서 `search`로 해석 — 정확 일치 1건이면 채택, 다수면 후보 목록(number·title·url)으로 안내, 0건이면 오류. (멤버/고객사 해석과 동일 UX)
- [x] `get_task`를 `async def get_task(ctx, task_id: int | str)`로 확장(파라미터 **이름 유지**, 타입만 넓힘) — `_resolve_task` 경유.
- 제목 검색 범위는 **현재 프로젝트로 한정**한다(결정 완료).

> 전용 조회 도구(`list_subtasks`/`list_related_tasks`)는 **만들지 않는다** — 특정 태스크의 하위/연관을 `get_task` 확장으로 함께 조회하면 충분하고, 하위/연관만 대상으로 하는 검색은 요구되지 않았다(결정 완료).

### Phase 3 — 슬래시 커맨드/프롬프트 대응
- [x] 조회 기능에 대응하는 `/gdc-task` 슬래시 커맨드([commands/gdc-task.md](../../commands/gdc-task.md)) + `gdc_task` MCP 프롬프트를 1:1로 추가(Desktop 병행). id/제목 입력, 상위·하위·연관 표기 안내 포함.

### Phase 4 — 로컬 사전 검증 & 배포
- [x] **검증(WS3 / 46 WBS)**: 상위 1·하위 2·연관대상 1 셋업 + related 링크 생성 → `get_task` 로직 직접 호출. 결과 **PASS** — sub_tasks 2건·related_tasks(outgoing/related) 1건·parent null, 하위에서 parent 요약(→상위) 노출, 제목 "[검증] 연관대상" 해석 정확. **임시 태스크 4건 전부 삭제·전역 컨텍스트 원복 완료.** (실행 세션 MCP는 구버전이라 최신 로컬 모듈 직접 호출로 검증)
- [x] 순수 로직 회귀: `python -m pytest tests/` 76 passed.
- [x] 사용자 노출 동작 변경 → `.claude-plugin/plugin.json` `version` 0.2.7 → **0.3.0** 상향.

## 참고 사항

- **서버 무수정 원칙**: 모든 변경은 `gdc_mcp/`(클라이언트) 한정. gdc-service 본체는 건드리지 않는다.
- **성능**: `get_task`는 이미 상세 API 1회 호출로 하위/연관을 모두 받으므로 Phase 1은 추가 왕복 0. 제목 해석(Phase 2)만 `search` 1회 추가.
- **부모(parent) 관계**: 상위 지정(쓰기)은 이미 `create_task`/`update_task`의 `parent`로 지원됨 → 이번 범위 밖. 조회(읽기)에서 상위 태스크를 노출하는 것만 Phase 1에 포함.
- **결정 사항**:
  1. (완료) 전용 조회 도구는 만들지 않고 `get_task` 확장으로 통합.
  2. (완료) 연관 태스크는 **방향 유지**로 표시. `TaskLink`는 `source→target` 방향 + 유형(`related`/`blocks`/`blocked_by` — GDC 서버가 정의한 연관 유형)을 가진다. `blocks`/`blocked_by`는 조회 주체에 따라 의미가 반대(예: `A --blocks--> B`는 A 조회 시 "B를 차단함", B 조회 시 "A에게 차단됨")이므로, `{방향, 유형, 대상}`을 그대로 노출한다.
  3. (완료) 제목 조회는 현재 프로젝트 한정.
