# task_from_doc 메타 단계 코드 필터 추가

| 속성 | 값 |
|------|-----|
| 유형 | fix |
| 영역 | server/api, commands |
| 날짜 | 2026-06-29 |
| 상태 | done |
| 관련 | server, task_from_doc, gdc-task-from-doc, 20260626-171539-task-doc-flow-rules |

## 요청 내용

배포본(0.1.9)으로 작업 요청 문서 기반 태스크를 생성했을 때, 태스크 본문 `[작업 내용]`에 빌드·검증 메타 단계가 그대로 포함되는 문제를 수정한다(예: 태스크 14587).

## 배경

직전 작업([20260626-171539-task-doc-flow-rules.md](20260626-171539-task-doc-flow-rules.md)) 항목 1(메타 단계 제외)은 **프롬프트/docstring 지침으로만** 강제했다. `task_from_doc`은 에이전트가 만들어 넘긴 `description`을 그대로 저장하므로, 에이전트가 지침을 어기고 원본 문서 "작업 결과"의 빌드/검증 단계를 옮기면 본문에 남는다(프롬프트 전용 강제의 구조적 한계). 사용자 결정: **코드 필터 + 프롬프트 강화** 병행.

## 작업 결과

### 1. 코드 변경 (`gdc_mcp/server.py`)

- [x] `_strip_meta_steps(description)` 추가 — `[작업 내용]` 헤더 이후 `-`/`*` 블렛 중 메타 키워드(빌드/build/타입체크/검증/verif/테스트/test/lint/커밋/commit/푸시/push/INDEX.md/이력 추가/동작 확인/정상 동작/npm run)에 걸리는 줄을 제거. 그 외 줄(요약·실제 산출물)은 보존.
- [x] `task_from_doc`: payload 구성 전 `description = _strip_meta_steps(description)` 적용. docstring 템플릿에 메타 제외 + 자동 제거 명시.

### 2. 프롬프트·커맨드 강화

- [x] `gdc_task_from_doc` 프롬프트 + [commands/gdc-task-from-doc.md](commands/gdc-task-from-doc.md): 제외 대상(빌드/타입체크/검증/테스트/lint/커밋/배포·동작 확인/INDEX 이력) 예시 명시, "원본 작업 결과에 있어도 옮기지 않음", "넣더라도 도구가 자동 제거" 안내.

### 3. 배포

- [x] `.claude-plugin/plugin.json` version 0.1.9 → 0.1.10.

## 참고 사항

- 코드 필터는 false positive 위험(정상 단계 오제거)이 있으나 사용자가 수용. 키워드는 명확한 프로세스/CI 용어로 한정.
- 검증: 태스크 14587 description으로 `_strip_meta_steps` 호출 시 메타 블렛 2개(`npm run build…`, `정상 동작 확인`) 제거·실제 단계 2개 유지 확인.
- 기존 태스크(14587 등)는 소급 수정되지 않음 — 다음 생성부터 적용.
