---
description: 새 태스크 생성 (선택 목록·한글·담당자 자동)
---

새 태스크를 생성합니다. 사용자 입력: $ARGUMENTS

원칙:
- 자유 입력: **제목 · 내용(description) · 예상 시작일 · 예상 종료일**. 상태/우선순위/업무유형/관련자는 **선택 목록**으로 고릅니다.
- **담당자는 묻지 않습니다** — 로그인 사용자로 자동 등록됩니다.
- ⚠️ **모든 선택 질문에 반드시 "건너뛰기" 보기를 포함**(생략 금지). 실제 값 보기는 **최대 3개**, 나머지는 "기타(Other)"로.

절차:
1. `get_context`로 현재 레포의 project_id 확인(없으면 `/gdc-login` 안내).
2. `get_project_enums(project_id)`로 status / priority / task_type / **members**(관련자 후보: id·name) 조회. 보기는 한글 `label`, `create_task`에 넘길 값은 `name`. 목록은 프로젝트별 동적(커스텀 포함).
3. **제목·내용**을 $ARGUMENTS에서 받거나 한 번 물어봅니다(자유 입력).
4. status / priority / task_type / **관련자**를 **선택 질문(AskUserQuestion)**으로 한 호출에 함께 묻습니다.
   - 각 질문은 **실제 값 최대 3개 + "건너뛰기"**. 값이 4개 이상이어도 다 채우지 말고 3개만, 나머지는 설명에 나열해 **"기타"(Other)**로 입력하게 합니다.
   - 새 태스크는 미완료 상태(등록/진행/검토)를 우선 노출, 완료 계열(해결/완료)은 기타로.
   - **관련자**는 members 이름으로 다중 선택 + "건너뛰기", 고른 이름을 user id로 환산해 `participant_ids`로 넘깁니다.
5. **예상 시작일/종료일**은 자유 입력(`YYYY-MM-DD`, 생략 가능) → `planned_start_date`/`planned_end_date`.
6. 건너뛴 항목은 생략하고 `create_task`로 생성, task_id·프로젝트명·URL을 보고합니다.
