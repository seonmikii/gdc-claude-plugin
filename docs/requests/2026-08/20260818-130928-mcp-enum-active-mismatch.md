---
task_id: 15853
task_url: https://gdc.gemiso.com/tasks/15853
---
# get_project_enums와 update_task의 task_type 허용 목록 불일치

| 속성 | 값 |
|------|-----|
| 유형 | fix |
| 영역 | server/gdc_mcp |
| 날짜 | 2026-08-18 |
| 상태 | partial (구현 완료, 건의사항 답변 등록 대기) |
| 관련 | gdc_mcp/server.py, tests/test_enum_resolve.py, 건의사항 #3, 20260810-095042-wbs-enum-default-mismatch.md |

## 요청 내용

MCP `get_project_enums`가 내려주는 `task_type` 목록과 `update_task`·`create_task`가 실제로 받아주는 목록이 달라, **조회한 값을 그대로 쓰면 수정이 실패한다.** 조회 결과를 신뢰할 수 있도록 두 도구가 같은 집합을 보게 하거나, 그럴 수 없다면 조회 응답에서 쓸 수 없는 값을 구분해 표시한다.

재현 (프로젝트 16 GDC-Support, 건의사항 #3):

1. `get_project_enums(16)` → `task_types`에 `기능 변경` 포함
2. `update_task(task_id=15844, task_type='기능 변경')` → 오류
   `task_type '기능 변경'는 이 프로젝트의 값이 아닙니다. 사용 가능: internal_meeting, planning, development, cs, 버그, 새 기능, 정책 변경, 개발 미확정, 보완 필요`

조회는 14종, 수정은 9종 — `external_meeting` / `design` / `other` / `기능 변경` / `확인 필요` 5종이 조회에만 나온다.

## 배경

### 원인 — `is_active` 필터가 한쪽에만 있다

코드를 확인한 결과, 두 목록이 갈라지는 지점은 한 줄이다.

| | 위치 | `is_active` 처리 |
|---|---|---|
| 조회 | `gdc_mcp/server.py:350-353` (`get_project_enums`) | **필터 없음** — 프로젝트 상세의 `task_types`를 그대로 나열 |
| 생성·수정 | `gdc_mcp/server.py:385` (`_resolve_enum_value`) | `if x.get("is_active", True)` — **비활성 항목 제외** |

즉 조회에만 나오는 5종은 프로젝트 설정에서 **비활성화된 유형**이다. `is_active`는 MCP 서버 전체에서 이 한 줄(385행)에만 등장한다.

```
프로젝트 상세 응답 (task_types 14종, is_active 포함)
        │
        ├── get_project_enums ──────────► 14종 전부 노출  ← 에이전트가 여기서 값을 고름
        │
        └── _resolve_enum_value ────────► 활성 9종만 통과 ← 여기서 거부됨
                 ↑
        create_task(985) / update_task(1121) / task_from_doc(1668) 공용
```

### 확인된 사실

- **`create_task`·`task_from_doc`도 같은 제약을 받는다** (건의사항의 미확인 항목). 셋 다 `_resolve_enum_value`를 거친다.
- **`status`·`priority`도 같은 불일치가 있다.** `_ENUM_KINDS`의 세 종류가 모두 같은 경로를 쓰는데, `get_project_enums`의 `statuses`·`priorities`도 `is_active`를 거르지 않는다.
- **비활성 값을 막는 것은 MCP 쪽 판단이다.** 백엔드 검증(gdc-service `backend/tasks/serializers.py:780-804`)은 `project.task_types.values_list("name")` 전체와 대조할 뿐 `is_active`를 보지 않으므로, 비활성 값도 서버는 받아준다. 즉 MCP가 서버보다 **더 엄격**하다.
- **그 엄격함 자체는 프론트와 일치한다.** 웹 UI의 유형/상태/우선순위 드롭다운은 `is_active`만 보여주고(gdc-service `frontend/src/components/tasks/TaskCreateDialog.tsx:825`, `frontend/src/hooks/use-task-filter-options.ts:122-125`), **수정 화면에서 해당 태스크의 현재 값이 비활성이면 그 값만 예외로 함께 노출**한다(`tt.is_active || (isEdit && task?.task_type === tt.name)`).

따라서 고칠 곳은 **조회 쪽**이다 — `_resolve_enum_value`를 느슨하게 풀면 웹에서 숨긴 값을 MCP만 계속 쓰게 되어 프론트와 어긋난다.

### 방향 — 숨기지 않고 표시한다

비활성 항목을 응답에서 **제거**하는 방식은 택하지 않는다. 이미 비활성 값으로 저장된 태스크가 존재하고(`get_task`의 `enum_mismatch`, 프론트의 수정 예외 처리가 그 전제), 특히 `not_finished_status_names`는 **기존 태스크를 거르는 필터 값**으로 쓰여(`list_my_tasks`/`list_tasks`의 `status` 파라미터, server.py:503·549·891) 비활성 상태를 빼면 그 상태로 저장된 미해결 태스크가 조회에서 통째로 누락된다.

대신 각 항목에 `is_active`를 실어 보내고, **바로 지정 가능한 이름만 따로 뽑은 목록**을 추가한다. 에이전트는 선택지를 만들 때 그 목록만 쓰면 되고, 저장된 값을 해석할 때는 전체 목록을 계속 볼 수 있다.

```
[AS-IS] get_project_enums(16) 응답
{
  "task_types": [
    {"name": "기능 변경", "label": "기능 변경"},     ← 지정하면 실패하는데 구분이 없다
    {"name": "development", "label": "개발"}, ...
  ]
}

[TO-BE]
{
  "task_types": [
    {"name": "기능 변경", "label": "기능 변경", "is_active": false},
    {"name": "development", "label": "개발", "is_active": true}, ...
  ],
  "assignable_task_type_names": ["internal_meeting", "planning", "development", ...],
  ...동일하게 assignable_status_names / assignable_priority_names
}
```

산출은 **표현식을 복제하지 않는다.** 활성 목록 계산(385행)을 `_enum_names(project, kind)` 헬퍼로 뽑아 `_resolve_enum_value`와 `get_project_enums`가 **같은 함수**를 호출하게 한다 — 같은 식을 두 곳에 두는 것은 이번 결함이 생긴 구조를 그대로 재생산하는 일이다. 오류 메시지에 비활성 사유를 붙이려면 비활성 목록도 필요하므로 헬퍼는 (활성, 비활성)을 함께 돌려준다.

**활성 항목이 0개인 경우**: `_resolve_enum_value`는 판단 근거가 없다고 보고 입력값을 그대로 통과시킨다(기존 동작, `test_empty_enum_leaves_value_untouched`). 이때 `assignable_*`는 **빈 배열**로 두고, "비어 있으면 제약 없음 — 서버 검증에 위임"을 docstring에 명시한다. 전체 목록을 대신 채우는 방식은 "활성만"이라는 규칙에 예외를 만들어 채택하지 않는다.

## 작업 결과

- [x] 활성/비활성 이름 목록을 돌려주는 `_enum_names` 헬퍼 추출 — `_resolve_enum_value`(385행)가 이 헬퍼를 쓰도록 교체
- [x] `get_project_enums` 응답의 `statuses`·`priorities`·`task_types` 각 항목에 `is_active` 추가 (프로젝트 상세 응답의 값을 그대로, 누락 시 `True`)
- [x] `assignable_status_names` / `assignable_priority_names` / `assignable_task_type_names` 추가 — 위 헬퍼를 **호출**해 산출(식 복제 금지). 활성 항목이 없으면 빈 배열
- [x] `done_status_names` / `not_finished_status_names`는 비활성 포함 그대로 유지하고, 용도(기존 태스크 필터용)를 docstring에 명시
- [x] `get_project_enums` docstring에 "생성·수정에 지정할 수 있는 값은 `assignable_*`, 전체 목록은 저장된 값 해석용" 구분과 "`assignable_*`가 비면 제약 없음(서버 검증에 위임)" 명시
- [x] `_resolve_enum_value`의 오류 메시지에 비활성 사유를 덧붙여 재시도 방향 제시 (예: `… '기능 변경'은 비활성 유형입니다. 사용 가능: …`)
- [x] `create_task`·`update_task`·`task_from_doc` docstring의 "`get_project_enums`로 확인" 안내를 `assignable_*` 기준으로 정정
- [x] `tests/test_enum_resolve.py`에 비활성 항목이 섞인 프로젝트 픽스처 추가 — 검증 기준은 두 방향:
  - `assignable_*`의 **모든 값**이 `_resolve_enum_value`를 그대로 통과한다
  - 응답 전체 목록 중 `is_active: false`인 name은 **전부 `ValueError`**로 막힌다
  - (통과 집합이 `assignable_*`와 문자 그대로 같지는 않다 — `_resolve_enum_value`는 라벨 별칭 `high`→`높음`도 받아주므로 통과 집합이 더 넓다)
- [x] `.claude-plugin/plugin.json` version `0.8.1` → `0.8.2`, 안내서 사이트 버전 표기 2곳(`site/index.html`) 동기화
- [ ] 건의사항 #3 상태를 `반영완료`로 변경하고 답변 등록 (웹)
- [x] `docs/INDEX.md` `## 이력`에 한 줄 추가

## 참고 사항

- 변경 범위는 **이 레포의 `gdc_mcp/server.py` 1개 파일 + 테스트**. gdc-service(백엔드·프론트·DB) 변경 없음 — 이 문서도 그래서 gdc-service가 아닌 이 레포에 둔다.
- 응답에 필드를 **추가**하는 변경이라 기존 필드를 읽던 호출자는 영향 없다.
- 프로젝트 상세는 TTL 캐시(`_project`)를 타므로 추가 왕복 없음.
- `site/artifact.html`은 이전 릴리스 시점(v0.8.0)에서 이미 갱신이 멈춰 있다. 이번 변경으로 생긴 어긋남이 아니라 손대지 않았다 — 별도 정리 필요.
- 후속 과제: 웹 UI가 "수정 시 현재 값이 비활성이면 그 값만 예외 노출"하는 것과 달리, MCP `update_task`는 대상 태스크의 현재 값이 비활성일 때 그 값을 **다시 보내면 거부**된다(태스크 조회 없이 값만 검증하므로). 값을 바꾸지 않으면 애초에 보내지 않으므로 실사용 경로는 아니라 이번 범위에서 제외한다.
