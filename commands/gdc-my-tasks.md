---
description: 내 미해결 태스크 조회 (선택 프로젝트 기준)
argument-hint: "[--overdue] [--undated] [--all]"
---

`list_my_tasks` 도구로 내 미해결 태스크를 마감 임박순으로 조회하세요.
조회 프로젝트는 현재 레포에 저장된 프로젝트로 고정됩니다(프로젝트 지정 옵션 없음).

사용자 인자: $ARGUMENTS
- `--overdue` → `overdue=true` (마감 지난 것만)
- `--undated` → `undated=true` (날짜 미정: 계획 종료일 없는 것만)
- `--all` → `not_finished=false` (완료 포함 전체)

결과는 번호 / 제목 / 상태 / 마감일 / URL 표로 보여주세요. 상태·우선순위는 응답의 `status_label`·`priority_label`(한글), 프로젝트는 `project_name`(ID 대신)을 씁니다.
사용자가 특정 태스크를 "열어줘"라고 하면 `open_task(task_id)`로 Chrome 새 탭에 엽니다.
