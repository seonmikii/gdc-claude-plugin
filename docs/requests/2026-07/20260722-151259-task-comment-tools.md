---
task_id: 15394
task_url: https://gdc.gemiso.com/tasks/15394
---

# 태스크 댓글(Mention) 조회·생성·수정·삭제 MCP 도구 추가

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | server/api |
| 날짜 | 2026-07-22 |
| 상태 | done |
| 관련 | gdc_mcp/server, gdc_mcp/doc_utils, gdc_mcp/client, plugin |

## 요청 내용

MCP 플러그인에 **태스크 댓글 조회 및 생성/수정/삭제** 기능을 추가한다. gdc-service의 댓글은 `Mention` 모델로 구현되어 있으며 REST 경로는 `/api/tasks/mentions/` 다. 다음 4개 MCP 도구를 이 레포에 추가한다.

| 도구 | 메서드 / 경로 | 인자 | 반환 요약 |
|---|---|---|---|
| `list_task_comments` | GET `/api/tasks/mentions/?task={id}` | `task_id`, `limit=20` | count, comments[](id·author_name·text·is_edited·created_at) |
| `add_task_comment` | POST `/api/tasks/mentions/` | `task_id`, `content`, `mentions?` | id·author_name·created_at |
| `update_task_comment` | PATCH `/api/tasks/mentions/{id}/` | `comment_id`, `content`, `mentions?` | id·is_edited·updated_at |
| `delete_task_comment` | DELETE `/api/tasks/mentions/{id}/` | `comment_id` | deleted:true |

### 확정된 설계 결정

- **작업 범위**: 조회 + 생성 + 수정 + 삭제 4종.
- **@멘션 지원**: `mentions` 인자(멤버 이름 또는 user id 리스트)를 받아 프로젝트 멤버의 `username`으로 해석 → `@user1 @user2` 한 줄을 content 앞에 붙인 뒤 변환한다. 서버가 본문의 `@username`을 파싱해 멘션 알림을 발송한다.
- **본문 변환**: 기존 `normalize_description()` 재사용(평문→HTML, 이미 HTML이면 통과).
- **노출 표면**: MCP 도구만. 슬래시 커맨드/MCP 프롬프트는 이번 범위에서 제외.

## 배경

- gdc-service에는 댓글(Mention) REST API가 **이미 전부 구현**되어 있다 — list/create/update/delete, `@username` 파싱, 멘션·댓글 알림(webhook/notification). 따라서 **이 레포(클라이언트)에만** 도구를 추가하면 되고 **gdc-service 본체는 수정하지 않는다**(서버 배포·마이그레이션 불필요, 플러그인 재설치로 반영).
- 사실 근거(gdc-service):
  - 라우팅: `backend/tasks/urls.py` `router.register("mentions", MentionViewSet)` → `backend/config/urls.py`가 `api/tasks/`에 마운트 → 전체 경로 `/api/tasks/mentions/`.
  - 뷰셋: `backend/tasks/views.py` `MentionViewSet`(ModelViewSet) — `filterset_fields=["task"]`(→ `?task=` 쿼리로 필터), 기본 정렬 `created_at`(오래된 순). **커스텀 `pagination_class` 없음 → 전역 기본(`PageNumberPagination`, `PAGE_SIZE=20`) 적용, `page_size_query_param` 미지원** → `?page_size=`는 무시되고 한 요청당 최대 20건(`?page=`로만 다음 페이지). (tasks/projects 뷰셋은 `page_size_query_param`을 opt-in해 동작하지만 멘션은 아님.)
  - 직렬화: `backend/tasks/serializers.py` `MentionSerializer` — 쓰기 가능 필드 `task`·`content`·`attachment_ids`, 읽기 전용 `id`·`author`·`is_edited`·`created_at`·`updated_at`. `author_name`은 `author.get_full_name`(**실명**, 로그인 username 아님 — username은 별도 `author_username`). `content`는 리치텍스트(HTML). `author`는 서버가 로그인 사용자로 강제.
  - 권한: 인증 사용자+프로젝트 접근권이면 조회·생성 가능. **수정/삭제는 작성자 본인만**(`perform_update`/`perform_destroy`에서 `PermissionDenied`).
  - 멘션: `create()`/`update()` 모두 `@([\w.@+-]+)` 정규식으로 `content`의 `@username`을 파싱해 `mentioned_users`에 **재설정**하고 `task_commented` 알림 이벤트를 발송. username은 **전체 User**에서 매칭(프로젝트 멤버 제한 없음).

## 작업 결과

### Phase 1 — client 헬퍼 확인·보강
- [x] `client.py`의 기존 `request()`로 POST/PATCH/DELETE를 처리한다(전용 헬퍼 신설 없이). DELETE는 **204(no content)** 응답이라 `.json()` 미호출 처리. (코드 변경 불필요 확인 — `request()`가 모든 메서드 처리, `raise_for_status()`는 204 통과)

### Phase 2 — doc_utils 순수 헬퍼 추가
- [x] `html_to_text(content)` 추가 — 조회 결과 content(HTML) 태그를 벗겨 터미널 표시용 텍스트로 변환(블록 태그→줄바꿈, 엔티티 unescape, 과다 빈 줄 축약). 파라미터명은 `html` 모듈 섀도잉 회피로 `content`.

### Phase 3 — server.py 멘션 해석 헬퍼
- [x] `_resolve_mention_usernames(project_id, mentions, project=None)` 추가 — 이름/ user id를 프로젝트 멤버의 `username`으로 해석. 비멤버는 `_resolve_members`와 동일하게 가능한 멤버 목록으로 ValueError 안내. 프로젝트 상세를 1회만 조회해 재사용. (+ `_build_comment_html` 헬퍼로 본문 HTML 변환·멘션 선두 주입 공통화)

### Phase 4 — server.py 도구 4종 등록
- [x] `list_task_comments(task_id, limit=20)` — `?task=&ordering=-created_at`로 최신순 조회, 상위 limit개를 시간순으로 뒤집어 `html_to_text`로 `text` 동봉, id·author_name(실명)·is_edited·created_at 반환. **최대 20건**(limit>20 서버 무시) docstring 명시, count(전체)·shown 반환.
- [x] `add_task_comment(task_id, content, mentions=None)` — 멘션 있으면 태스크 조회로 project id 확보 후 username 해석·본문 선두 주입 → `normalize_description` → POST.
- [x] `update_task_comment(comment_id, content, mentions=None)` — 멘션 있으면 댓글→태스크→project id 확보. PATCH. 403(작성자 아님)은 친절 ValueError로 변환. destructive(멘션 덮어씀) 동작 docstring 명시.
- [x] `delete_task_comment(comment_id)` — DELETE(204). 403은 친절 ValueError로 변환.
- [x] 각 도구에 자연어 호출용 구체적 docstring 작성(인자·제약·본인만 수정/삭제 안내).

### Phase 5 — 테스트·버전·문서
- [x] pytest(순수 로직만): `html_to_text` 태그 제거·엔티티·빈 줄 축약, `_resolve_mention_usernames` 이름/id→username·비멤버 오류, `_build_comment_html` 멘션 주입. (`uv run python -m pytest tests/` → 71 passed)
- [x] 서버 연동(실제 댓글 CRUD)은 도구 직접 호출로 수동 검증 — 운영 서버 테스트 프로젝트(45/이슈관리 테스트, task 15357)에서 add→list→update→delete 왕복 성공, html_to_text 평문 복원·`<` 이스케이프·is_edited 확인. 멘션은 멤버 검증(비멤버 차단) 동작 확인(실제 알림 발송은 미실시).
- [x] `.claude-plugin/plugin.json` version 0.2.4 → 0.2.5.
- [x] `docs/INDEX.md` `## 이력`에 한 줄 추가.

## 참고 사항

- **gdc-service 미수정**: 이번 작업은 기존 서버 API에 붙는 클라이언트 도구 추가만 포함한다. 서버 동작 변경이 필요하면 별도 처리.
- **멘션 배치 제약**: `@user…`는 content 맨 앞 별도 줄에 붙인다(본문 중간 커서 위치 삽입은 미지원). 서버 알림 발송에는 위치 무관.
- **YAGNI 제외**: 첨부(attachment_ids), 이모지 리액션, 편집 이력(`/history`·`/restore`), 스레드 답글, 슬래시 커맨드/프롬프트.
- **변경 파일(예정)**: `gdc_mcp/server.py`, `gdc_mcp/doc_utils.py`, `tests/`, `.claude-plugin/plugin.json`, `docs/INDEX.md`.
