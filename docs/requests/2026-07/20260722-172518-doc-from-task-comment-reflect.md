---
task_id: 15409
task_url: https://gdc.gemiso.com/tasks/15409
---
# 작업 요청 문서 생성 시 태스크 댓글 내용 반영

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | commands/gdc-doc-from-task, skill/gdc-doc-from-task |
| 날짜 | 2026-07-22 |
| 상태 | done |
| 관련 | gdc-doc-from-task, server(list_task_comments), #399 |

## 요청 내용

`gdc-doc-from-task`(태스크 기반 작업 요청 문서 자동 생성) 흐름이 태스크 **description만** 참고하고 **댓글(Mention)은 반영하지 않는다.** 요구사항·의사결정이 태스크 본문이 아니라 댓글로 논의되는 경우(특히 description이 비어 있는 태스크), 생성된 문서의 ②기획 정리 단계에서 핵심 맥락이 누락된다.

`#399`에서 추가한 댓글 도구(`list_task_comments`)를 doc-from-task 절차에 편입해, `get_task`와 **함께 댓글을 조회**하고 그 내용을 기획 정리에 반영하도록 개선한다.

### 요구사항
- doc-from-task 1단계에서 `get_task($1)`와 함께 `list_task_comments($1)`를 조회한다.
- 댓글 내용을 ②기획 정리(요구사항·배경 명확화)에 통합한다. description과 댓글이 상충하면 문서에 그 사실을 드러낸다.
- 댓글이 0개면 기존 동작(description 기반)과 동일하게 진행한다 — 별도 오류/차단 없음.
- 서버 페이지네이션상 한 요청 최대 20개(최신 우선)라는 제약을 인지하고, 그 이상은 별도 언급한다.

### 범위 밖 (Non-goals)
- 서버(`../gdc/gdc-service`) 수정 없음 — 클라이언트 절차 문서만 변경.
- 댓글 생성/수정/삭제 도구 자체는 이미 `#399`에서 완료 — 본 작업은 **조회 소비측**만 다룬다.
- `task_from_doc`(문서→태스크) 역방향 흐름은 대상 아님.

## 배경

- 태스크 `#399`(id 15394, GDC-Support)에서 댓글 CRUD 도구(`list_task_comments`/`add_task_comment`/`update_task_comment`/`delete_task_comment`)를 추가·검증 완료(v0.2.5).
- 그러나 문서 자동 생성 커맨드(`commands/gdc-doc-from-task.md`)는 여전히 `get_task`만 지시하고 댓글을 언급하지 않아, 새로 생긴 조회 도구가 doc 생성 흐름에서 활용되지 않는다.
- 실제로 이번 대상 태스크 `#399`는 description이 비어 있어, 댓글이 없으면 문서로 옮길 실질 내용이 부족한 구조였다 — 댓글 반영의 필요성을 그대로 보여주는 사례.

## 작업 결과

- [x] `commands/gdc-doc-from-task.md` 1단계에 `list_task_comments($1)` 조회 지시 추가
- [x] 2단계(②기획 정리)에 "댓글 내용 반영" 문구 추가 — description+댓글 통합, 상충 시 명시
- [x] 댓글 0개 / 20개 초과(페이지네이션) 케이스 지침 명문화
- [x] `gdc_mcp/server.py`의 `gdc_doc_from_task` **MCP 프롬프트**에 동일 지시 반영 — 커맨드 ↔ MCP 프롬프트 1:1 대응 유지 (AGENTS 규칙)
- [x] `commands/gdc-doc-from-task.md`에 (하위)태스크 생성 시 라벨 섹션 템플릿(`/gdc-task-new` 형식: `[요약]`/`[AS-IS]`/`[TO-BE]`/`[작업 내용]`) 사용 지침 추가 — 태스크 description 평문 누락 재발 방지
- [x] 사용자 노출 동작 변경 → `.claude-plugin/plugin.json` version 상향 (0.2.5 → 0.2.6)
- [x] 도구 직접 호출로 댓글 있는 태스크 수동 검증 — 테스트 프로젝트 45(이슈관리 테스트) 태스크 15386에 댓글 2개 추가 → `get_task`+`list_task_comments`가 count=2·본문 정상 반환 확인 → 댓글 삭제로 원복(count=0). 소비 단계 정상.

## 참고 사항

- 변경 파일(예정): `commands/gdc-doc-from-task.md`, `gdc_mcp/server.py`(`gdc_doc_from_task` MCP 프롬프트), `.claude-plugin/plugin.json`.
- 커맨드와 MCP 프롬프트는 1:1 대응(AGENTS 규칙)이므로 댓글 반영 지시를 **두 곳 모두**에 넣는다 — 커맨드만 고치면 Desktop용 프롬프트와 괴리 발생.
- `list_task_comments`는 실행 세션의 MCP 서버 버전이 v0.2.5 이상이어야 노출된다 — 미노출 시 `/plugins`로 플러그인 갱신 필요.
- 상위 태스크: [#399](https://gdc.gemiso.com/tasks/15394) 댓글 조회 및 생성/수정 기능 추가.
- 컨텍스트 주의: 현재 레포 저장 컨텍스트는 project 31(클라우드본부)이나, 상위 `#399`/본 하위 태스크는 project 16(GDC-Support)에 존재한다.
