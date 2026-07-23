---
description: 태스크 상세 조회 (id 또는 제목, 하위·연관·상위 태스크 포함)
argument-hint: "<태스크(id|제목)>"
---

`get_task` 도구로 한 태스크의 상세를 조회하세요. 인자: $ARGUMENTS

- 인자는 태스크 **id(정수)** 또는 **제목(문자열)**. 제목이면 도구가 현재 프로젝트에서 검색해 해석합니다(정확 1건이면 채택, 다수면 후보 목록 안내, 0건이면 오류).
- 응답의 `status_label`·`priority_label`·`task_type_label`(한글)과 `project_name`을 씁니다(코드/ID 대신).
- **상위(parent)**: 있으면 번호·제목·URL을 한 줄로.
- **하위 태스크(sub_tasks)**: 번호 / 제목 / 상태 / 진행률 / URL 표로.
- **연관 태스크(related_tasks)**: 각 항목의 `direction`(outgoing=대상으로, incoming=원본에서)과 `link_type`, 대상/원본 번호·제목·URL을 함께 보여줍니다. `blocks`/`blocked_by`는 방향에 따라 의미가 반대이므로 방향을 명시해 표기합니다.

조회 프로젝트는 현재 레포에 저장된 프로젝트로 고정됩니다. 사용자가 특정 태스크를 "열어줘"라고 하면 `open_task(task_id)`로 Chrome 새 탭에 엽니다.
