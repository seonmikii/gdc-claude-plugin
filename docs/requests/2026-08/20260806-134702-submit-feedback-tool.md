---
task_id: 15631
task_url: https://gdc.gemiso.com/tasks/15631
---

# 건의사항 제출·조회 도구 추가 (submit_suggestion / list_my_suggestions)

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | server/gdc_mcp, commands |
| 날짜 | 2026-08-06 (2026-08-10 서버 설계 변경 반영, 2026-08-11 서버 배포 확인) |
| 상태 | **구현 완료** — Phase 0~4 완료(4-3 알림 수신만 계정 제약으로 미검증), v0.8.0 |
| 관련 | server, client, gdc-suggest, plugin.json, README, suggestions(gdc-service) |

## 요청 내용

사용자가 플러그인을 쓰다가 생긴 **개선 요청·불편 사항·버그**를 그 자리에서 제출하고, 자기가 낸 건의가 어떻게 처리됐는지 확인할 수 있는 MCP 도구를 추가한다.

**2026-08-10 변경:** 저장소가 **GDC 태스크 → 건의사항(`suggestions`) 전용 엔티티**로 바뀌었다. gdc-service에 [건의사항 수집 기능](../../../../gdc/gdc-service/docs/requests/2026-08/20260810-150041-user-suggestion-board.md)([#478](https://gdc.gemiso.com/tasks/15781))이 구현되어, 플러그인은 그 API를 호출하기만 하면 된다.

## 배경

### 왜 바뀌었나 — 태스크 저장소가 만든 연쇄

태스크를 저장소로 쓰려면 `can_write_project`(프로젝트 ADMIN/MEMBER 또는 워크스페이스 매니저 이상)를 통과해야 하고, 비멤버는 403이었다. 그래서 가입 요청 → 관리자 승인 흐름이 필요했고, 승인의 결과물(프로젝트 전체 쓰기 권한 + 워크스페이스 편입)이 의견 한 건 받는 대가로 과하다는 문제까지 이어졌다.

목표는 "누구나 의견을 낼 수 있다"인데 승인 흐름을 끼우면 **"관리자가 승인해줘야 낼 수 있다"** 가 되어 목표와 어긋난다. 건의사항을 프로젝트에 속하지 않는 **전역 엔티티**로 빼면서 이 연쇄가 통째로 사라졌다.

| | 기존 계획 (2026-08-06) | 확정 (2026-08-10) |
|---|---|---|
| 저장소 | #292 하위 태스크 (프로젝트 16) | `Suggestion` — 워크스페이스·프로젝트 FK 없음 |
| 제출 자격 | 프로젝트 멤버만 | **인증된 사용자 누구나** |
| 권한 실패 경로 | 403 → 가입 요청 → 관리자 승인 | **없음** |
| 진행 확인 | 태스크 상태 | 건의 상태 6종 + 관리자 답변 + 인앱 알림 |
| 컨텍스트 의존 | 부모 태스크·프로젝트 고정 상수 필요 | **없음** (전역) |

**이번 작업에서 통째로 사라진 것:** 부모 태스크 상수(`_FEEDBACK_PARENT_TASK_ID`)와 환경변수 override, 분류→`task_type` 매핑, 담당자 자동 지정, 로컬 pending 큐(B-2)와 `resend` 재전송, 가입 요청 연동(B-1), 권한 없음 분기 전체. → 도구 2개와 커맨드 1개만 남는다.

> 가입 요청([20260806-142238-project-join-request.md](../../../../gdc/gdc-service/docs/requests/2026-08/20260806-142238-project-join-request.md), [#462](https://gdc.gemiso.com/tasks/15672))은 **보류** — 이 기능의 요구 출처가 사라졌고, 일정 미정 대기열로 이동했다. 분석 자체는 유효하다.

### 서버가 확정한 계약 (구현 코드 기준)

| 항목 | 값 |
|------|-----|
| 제출 | `POST /api/suggestions/` — body `{category, title, content}`. `author`는 서버가 `request.user`로, `status`는 `received`로 고정(요청 본문에서 받지 않음) |
| 목록 | `GET /api/suggestions/` — **비관리자는 본인 것만** 쿼리셋에서 걸러짐. 필터 `status`·`category` |
| 상세 | `GET /api/suggestions/{id}/` — `content`·`admin_reply`·`replied_by_name`·`replied_at` 포함 |
| 분류 | `bug`(버그) / `feature`(기능 요청) / `improvement`(개선 제안, 기본값) / `other`(기타) |
| 상태 | `received`(접수) / `reviewing`(검토중) / `planned`(반영예정) / `completed`(반영완료) / `hold`(보류) / `rejected`(반려) |
| 제목 | `CharField(200)` — 초과 시 서버가 400 |
| 권한 | `list`·`retrieve`·`create`는 `IsAuthenticated`만. 처리(`PATCH`)·삭제는 관리자 |

- 관리자가 답변·상태 변경 시 제출자에게 **인앱 알림**(`suggestion_replied`, "건의사항 답변")이 발송된다. 기존 `list_my_notifications`로 그대로 잡히지만, 플러그인의 `_NOTIFICATION_LABELS`가 7종 하드코딩이라 **새 유형은 원문 코드로 노출**된다 → 라벨 추가 필요.
- **페이지네이션이 태스크와 다르다.** `SuggestionViewSet`은 전역 기본값(`PageNumberPagination`, `PAGE_SIZE=20`)을 쓰는데 `page_size_query_param`이 설정돼 있지 않아 **`page_size` 파라미터가 무시된다**. 태스크는 전용 `TaskPagination`이 있어 먹히는 것 — 20건을 넘겨 받으려면 `list_my_mentions`처럼 `page`를 넘겨 수집해야 한다.
- **배포 상태(2026-08-11 확인): 운영(`gdc.gemiso.com`) 반영 완료.** `feat/gdc-478-user-suggestion-board`의 기능 커밋(`e2717c9`)이 `origin/develop`에 포함됐고, 운영 엔드포인트가 살아 있다 — `GET`·`POST /api/suggestions/`와 `GET /api/suggestions/{id}/`가 모두 **401**(인증 필요)을 반환한다. 존재하지 않는 경로(`/api/no-such-route/`)는 **404**를 주므로 라우트 존재가 구분된다. 착수 조건은 해소됐다.

## 설계

### 흐름

```
  사용자: "검색 정렬이 이상해요" / /gdc-suggest
            │
            ▼
  submit_suggestion(content, category="improvement", title?)
            │
            ├─ POST /api/suggestions/  { category, title, content }
            │
            ├─ 201 ──▶ { id, title, category, status:"received", created_at }
            │            "접수됐습니다(#12). 처리되면 알림으로 알려드립니다"
            │
            ├─ 401 ──▶ "gdc_login으로 인증하세요" (기존 규약)
            └─ 404 ──▶ "서버에 건의함 기능이 아직 배포되지 않았습니다"

  확인:  list_my_suggestions()   →  GET /api/suggestions/    (본인 것만 서버가 필터)
         get_suggestion(id)      →  GET /api/suggestions/{id}/  (관리자 답변 읽기)

  답변:  관리자 답변 → 인앱 알림 → 기존 list_my_notifications 에 "건의사항 답변"으로 표시
```

컨텍스트(워크스페이스/프로젝트) 판정이 없다 — 어느 레포에서 호출하든 동일하게 동작한다.

### 도구 1 — `submit_suggestion`

| 파라미터 | 타입 | 기본 | 설명 |
|----------|------|------|------|
| `content` | str (5~2000자) | 필수 | 건의 본문 |
| `category` | `bug` / `feature` / `improvement` / `other` | `improvement` | 분류 (서버 기본값과 일치) |
| `title` | str? | None | 생략 시 `content` 첫 줄(최대 40자)로 자동 생성. 서버 상한 200자를 넘지 않도록 자른다 |

- 본문 길이 하한(5자)은 클라이언트에서 검증한다 — 서버엔 하한이 없어 빈 문장 제출을 막으려면 도구 레벨이 유일한 지점이다(입력 검증은 도구 레벨 규칙).
- 응답은 접수 번호·상태·조회 방법 안내까지 담는다. 토큰·자격증명은 포함하지 않는다.

### 도구 2 — `list_my_suggestions`

| 파라미터 | 타입 | 기본 | 설명 |
|----------|------|------|------|
| `status` | str? | None | 상태 필터 (`received`/`reviewing`/… 또는 한글 라벨 해석) |
| `category` | str? | None | 분류 필터 |
| `limit` | int | 20 | 최대 건수. 20 초과면 `page`를 넘겨 수집 |

- 목록 응답에 `content`·`admin_reply`가 없다(`SuggestionListSerializer`는 `has_reply` 불리언만 준다). **답변 본문을 보려면 상세 조회가 필요**하므로 `get_suggestion(id)`를 함께 둔다 — 목록에서 `has_reply=true`인 건만 열어보게 안내한다.
- 상태·분류는 서버 코드값과 한글 라벨을 함께 표시한다(기존 `_STATUS_LABELS` 패턴과 동일).

### 도구 3 — `get_suggestion`

`GET /api/suggestions/{id}/` 단건 조회. 본문 + 관리자 답변 + 답변자/답변 시각. 남의 건의는 서버 쿼리셋 필터로 404가 되므로 별도 방어가 필요 없다.

### 커맨드·프롬프트

- `/gdc-suggest` 슬래시 커맨드 + 동명 MCP 프롬프트를 **쌍으로** 추가한다(Desktop은 슬래시 미지원). 프롬프트는 분류를 `AskUserQuestion` 선택지로 묻고 본문만 자유 입력받는다.

## 작업 계획

### Phase 0 — 선행

- [x] 0-1. 저장소 방식 확정 — 태스크 → 건의사항 전용 엔티티 (2026-08-10, gdc-service [#478](https://gdc.gemiso.com/tasks/15781))
- [x] 0-2. **선행:** gdc-service 건의사항 기능 **운영 배포** 확인 — 2026-08-11 충족. `e2717c9`가 `origin/develop`에 머지됐고 운영 `/api/suggestions/`가 401로 응답(미존재 경로는 404)
- [x] 0-3. 도구 이름 확정 — `submit_suggestion`/`list_my_suggestions`/`get_suggestion` (서버 문서의 예시 표기는 `submit_feedback`/`list_feedback`). **`submit_suggestion` 채택** — 같은 클라이언트에 mymy 플러그인의 `submit_feedback`이 이미 등록돼 있어 자연어 호출 시 대상이 모호해진다.

### Phase 1 — `submit_suggestion`

- [x] 1-1. 순수 헬퍼 pytest 선작성 — 제목 자동 생성(첫 줄·40자·공백·200자 상한), 분류 검증, 본문 길이 검증(5~2000) → `tests/test_suggestions.py` 20건. 추가 직후 ImportError로 실패 확인 후 구현
- [x] 1-2. `server.py`에 `submit_suggestion` 등록 (`client.py` 경유, 컨텍스트 비의존 docstring 명시)
- [x] 1-3. 401/404 안내 분기 — 401은 `client.py`가 기존 규약대로 처리, 404는 "건의함 미배포" 안내로 분기
- [x] 1-4. `uv run python -m pytest tests/` 전체 회귀 → **207건 통과**(기존 187 + 신규 20)

### Phase 2 — 조회 도구

- [x] 2-1. `list_my_suggestions` 등록 — 상태·분류 필터, 20건 초과 시 `page` 순회 수집. **`mine=true` 추가**(아래 참고)
- [x] 2-2. `get_suggestion` 등록 — 관리자 답변·답변자·답변 시각 노출
- [x] 2-3. `_NOTIFICATION_LABELS`에 `suggestion_replied`("건의사항 답변") 추가 + 기존 누락이던 `task_created`("태스크 생성")도 함께 채움

### Phase 3 — 커맨드·프롬프트·문서

- [x] 3-1. `commands/gdc-suggest.md` + `@mcp.prompt gdc_suggest` 쌍 추가 (커맨드 13종 / 프롬프트 12종)
- [x] 3-2. README 도구표에 신규 도구 3종 추가 + 개수 문구 갱신(도구 28→31, 커맨드 12→13, 프롬프트 11→12)
- [x] 3-3. `.claude-plugin/plugin.json` 버전 0.7.1 → **0.8.0**
- [x] 3-4. `docs/INDEX.md` 이력 한 줄 추가

### Phase 4 — 로컬 사전 검증

실행 세션의 MCP 서버가 구버전이라 로컬 코드를 직접 호출해 검증했다(`uv run python`, shim 미사용).

- [x] 4-1. 운영 서버에 `submit_suggestion` 1회 제출 → `#1` / `status=received` 반환. 한글 분류('기타'→`other`)·제목 자동 생성(40자 절단) 동작 확인
- [x] 4-2. `list_my_suggestions`(total 1, `has_reply=false`)·`get_suggestion`(본문·`admin_reply=None`) 되읽기 확인
- [~] 4-3. 관리자 `PATCH` 200 → `status=검토중`, `admin_reply`·`replied_by_name`·`replied_at` 노출, 목록 `has_reply=true` 확인. **알림 수신은 미검증** — 서버가 `author == sender`면 알림을 만들지 않아(`notifications/utils.py:147`) 단일 계정으로는 재현 불가. 라벨 매핑은 `_NOTIFICATION_LABELS['suggestion_replied'] == '건의사항 답변'`으로 직접 확인
- [x] 4-4. 검증용 건의 `DELETE` 204 → 목록 잔존 **0건**, 상세 조회도 차단됨(원복 완료)

> 기존의 "테스트 워크스페이스(WS3/45)에서 검증" 규칙은 이번엔 적용되지 않는다 — 건의사항은 워크스페이스에 속하지 않아 격리할 대상이 없다. 대신 **검증용 제출은 반드시 삭제해 원복**한다.

## 참고 사항

- 변경 파일 후보: `gdc_mcp/server.py`(도구 3개 + 프롬프트 + 알림 라벨), `commands/gdc-suggest.md`(신규), `tests/`(신규 케이스), `README.md`, `.claude-plugin/plugin.json`. **신규 모듈 없음** — 로컬 pending 저장이 사라져 파일 저장 로직이 필요 없다.
- `_NOTIFICATION_LABELS`에는 `task_created`도 빠져 있다(서버엔 존재). 한 줄이라 이번에 함께 채웠다.
- **구현 중 발견 — 목록에 `mine=true`가 필요하다.** 계약 표에는 "비관리자는 본인 것만 걸러짐"이라고만 적었는데, 실제 `SuggestionViewSet.get_queryset`은 **건의사항 관리자(`system_admin` 또는 `suggestions.change_suggestion` 보유)에게는 전체를 준다.** 관리자가 `list_my_suggestions`를 부르면 남의 건의까지 "내 건의"로 나오므로 `mine=true`를 항상 붙인다.
- **구현 중 발견 — 자기 건의에 자기가 답변하면 알림이 없다.** `create_suggestion_reply_notification`이 `author == sender`를 건너뛴다. 정상 동작이지만, 알림 흐름 전체를 검증하려면 계정 2개가 필요하다.
- 건의 본문에 사용자가 토큰·비밀번호를 붙여넣을 수 있다. 서버가 마스킹하지 않으므로(팀이 읽어야 하는 내용) docstring에 "자격증명은 넣지 말 것"을 명시하는 선에서 처리한다.
- 서버 범위에서 제외된 것들: 중복 제출 감지, 제출 횟수 제한(throttle), 유입 경로(`source`) 기록, 태스크 연계, 첨부파일. **플러그인에서 우회 구현하지 않는다.**
- 연동 태스크 [#453](https://gdc.gemiso.com/tasks/15631)의 제목·본문은 태스크 저장소 시절 내용이라 이 문서와 어긋난다 — 갱신 필요.
