---
description: 특정 담당자의 태스크 조회 (이름 또는 user id)
argument-hint: "<담당자(이름|id)> [--overdue] [--undated] [--all]"
---

`list_tasks` 도구로 특정 담당자의 태스크를 마감 임박순으로 조회하세요. 인자: $ARGUMENTS

- 첫 인자 = **담당자** (멤버 이름 예: `김철수`, 또는 user id). 도구가 프로젝트 members로 자동 id 해석합니다. 비멤버면 가능한 멤버 목록을 안내합니다.
- `--overdue` → `overdue=true` (마감 지난 것만)
- `--undated` → `undated=true` (날짜 미정: 계획 종료일 없는 것만)
- `--all` → `not_finished=false` (완료 포함 전체)

조회 프로젝트는 현재 레포에 저장된 프로젝트로 고정됩니다("내" 태스크는 `/gdc-my-tasks`).
결과는 번호 / 제목 / 상태 / 마감일 / URL 표로 보여주세요. 상태·우선순위는 응답의 `status_label`·`priority_label`(한글), 프로젝트는 `project_name`을 씁니다.
사용자가 특정 태스크를 "열어줘"라고 하면 `open_task(task_id)`로 Chrome 새 탭에 엽니다.
