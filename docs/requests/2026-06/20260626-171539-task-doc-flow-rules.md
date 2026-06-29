# 태스크·작업 요청 문서 플로우 규칙 5종 추가

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | server/api, commands, rules |
| 날짜 | 2026-06-26 |
| 상태 | done |
| 관련 | server, gdc-task-from-doc, gdc-doc-from-task, gdc-task-new, tasks |

## 요청 내용

태스크 생성·작업 요청 문서 작성 플로우에 다음 5가지 규칙/동작을 추가·수정한다.

1. **태스크 본문에서 메타 단계 제외** — `task_from_doc`로 태스크 생성 시, 태스크 본문 `[작업 내용]`에 "INDEX.md 이력 추가"·검증·테스트 같은 메타 단계를 넣지 않는다. (INDEX 이력 관리 프로세스 자체는 그대로 유지)
2. **문서 본문 → 태스크 description 동기화** — 작업 요청 문서 본문에 수정사항이 생기면, 명시적 sync(`gdc_sync` / `sync_doc_progress`) 실행 시 연동된 태스크 본문(description)에도 반영한다. 자동 PostToolUse 훅은 기존대로 **진행률 전용**으로 유지한다.
3. **문서 작성 시 코드 검토 선행** — 태스크 기반 작업 요청 문서(`gdc-doc-from-task`) 작성 시, 태스크 description을 그대로 옮기지 말고 "관련 코드 검토 → 기획 정리 → 개발 계획 수립 → 문서 반영" 순서로 작성한다.
4. **완료 태스크 자동 보정** — 완료 상태로 태스크를 생성하면 `create_task`·`task_from_doc` 두 경로 모두 진행률 100%·실제 종료일=오늘로 자동 설정한다.
5. **유형 자동 매칭** — 작업 요청 문서로 태스크 생성 시 문서 내용(메타표 유형 + 본문)을 근거로 프로젝트 `task_type` enum을 최대한 자동 매칭한다.

## 배경

현재 플로우는 태스크 본문에 프로세스 메타 단계가 섞이고, 완료 태스크 생성 시 진행률/종료일을 수동 보정해야 하며, 문서가 태스크 description의 기계적 전사에 그치는 한계가 있다. 위 규칙으로 본문 품질·자동화·일관성을 높인다.

## 작업 결과

### 1. 코드 변경 (`gdc_mcp/server.py`)

- [x] `create_task`: 지정 `status`의 category가 `done`이면(`_status_category(project, status)`로 판별) payload에 `progress=100`·`actual_end_date=오늘`을 자동 주입. (항목 4)
- [x] `task_from_doc`: 문서 상태가 `done`으로 매핑될 때 payload에 `progress=100`·`actual_end_date=오늘`을 자동 주입. (항목 4)
- [x] `sync_doc_progress`: optional `description` 인자 추가 → 전달 시 진행률 PATCH에 함께 포함. `_apply_progress_sync(task_id, new_progress, description=None)`로 시그니처 확장·병합. 자동 훅(`_cli_sync_doc`)은 인자 없이 호출 → 진행률 전용 유지. (항목 2)

### 2. 프롬프트·커맨드 변경

- [x] `gdc_task_from_doc` 프롬프트 + [commands/gdc-task-from-doc.md](commands/gdc-task-from-doc.md): `[작업 내용]` 요약 시 이력·검증·테스트 메타 단계 제외 명시(항목 1), 문서 유형/본문 기반 `task_type` 자동 매칭 절차 추가(항목 5).
- [x] `task_from_doc` 도구 docstring: 메타 단계 제외·완료 자동 보정·유형 자동 매칭 규칙 반영.
- [x] `gdc_doc_from_task` 프롬프트 + [commands/gdc-doc-from-task.md](commands/gdc-doc-from-task.md): "코드 검토 → 기획 정리 → 개발 계획 수립 → 문서 반영" 단계 추가(항목 3).
- [x] `gdc_task_new` 프롬프트 + [commands/gdc-task-new.md](commands/gdc-task-new.md): 완료 계열 상태 선택 시 진행률/실제 종료일 자동 보정 안내(항목 4).
- [x] `gdc_sync` 프롬프트 + [commands/gdc-sync.md](commands/gdc-sync.md): 문서 본문 변경 시 `[작업 내용]` 요약을 재생성해 `sync_doc_progress`의 `description` 인자로 전달하도록 안내(항목 2).

### 3. 규칙 전달 경로 (로컬 rules 미수정)

- 항목 2·3은 **배포 대상인 프롬프트(server.py)·커맨드(commands/)** 에만 반영한다. `.claude/rules/tasks.md`는 이 레포 개발 시에만 적용되는 로컬 규칙이라 플러그인 사용자에게 배포되지 않으므로 수정하지 않는다. (§2에서 처리 완료)

### 4. 배포

- [x] 사용자 노출 동작 변경 → `.claude-plugin/plugin.json` version 상향 (0.1.8 → 0.1.9).

## 참고 사항

- 항목 4 코드 변경 시 기존 `_validate_dates`(실제 종료일 미래 차단)와 충돌 없음(오늘 날짜 허용).
- 항목 5는 코드 변경 없이 프롬프트/커맨드 절차로 처리(에이전트가 `get_project_enums`로 `task_type` 조회 후 매칭하여 인자 전달).

## 검토 확정 사항 (2026-06-29)

진행 전 최종 검토에서 다음 2가지를 확정한다(항목 4 관련).

- **(a) `create_task` REST 왕복 1회 추가 수용** — `create_task`는 현재 프로젝트 enum을 조회하지 않으므로, done 판별을 위해 `_status_category(project, status)`가 `GET /api/projects/{id}/`를 1회 호출한다. `status`가 명시될 때만 발생하며 영향이 작아 수용한다.
- **(b) 백엔드 의존 없이 클라이언트 명시 주입** — 완료 생성 시 백엔드 자동 보정 여부와 무관하게 클라이언트에서 `progress=100`·`actual_end_date=오늘`을 명시 주입한다(중복이어도 idempotent·무해). 별도 백엔드 검증 없이 진행.
