---
task_id: 15350
task_url: https://gdc.gemiso.com/tasks/15350
---

# create_task/update_task 편집 필드 전체 확장 (UI 폼과 동등화)

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | server/api |
| 날짜 | 2026-07-20 |
| 상태 | 구현 완료 (실사용 검증 대기 — 플러그인 재설치 후 확인) |
| 관련 | server, client, tokens |

## 요청 내용

MCP 플러그인의 `update_task` 도구가 수정할 수 있는 컬럼이 제한되어 있음.
GDC 웹 UI의 태스크 수정 다이얼로그에서 수정 가능한 값은 **모두** MCP에서도 수정 가능해야 함.

**범위 확장(2026-07-20 사용자 결정):** UI는 생성/수정이 같은 다이얼로그(`TaskCreateDialog.tsx`)를 공유하므로
`create_task`에도 동일 기준을 적용한다. 생성 쪽 격차(parent, customer, weight, 실제 날짜 2종, progress, tag_ids)를 함께 해소한다.

## 배경 — 현재 구현 검토 결과

### 기준: 서버·UI에서 수정 가능한 필드

- 백엔드 `TaskSerializer`(gdc-service `backend/tasks/serializers.py`)의 쓰기 가능 필드:
  `project, parent, title, title_en, needs_vdc_share, description, task_type, status, priority,
  assignee, customer, planned/actual 날짜 4종, progress, weight, is_pinned, is_archived, tag_ids, participant_ids`
- 프론트 수정 폼 스키마(`frontend/src/lib/schemas/task.ts` `taskSchema`)도 동일 집합이며,
  `parent/assignee/customer/날짜 4종/weight`는 **nullable(해제 가능)**.

### 현재 `update_task`(gdc_mcp/server.py:463)가 노출하는 필드

`title, description, status, priority, task_type, assignee, progress,
planned/actual 날짜 4종, customer(int), parent, is_pinned, tag_ids, participant_ids`

### 격차 (UI 대비 부족한 부분)

| # | 격차 | 상세 |
|---|------|------|
| 1 | `weight` 미노출 | WBS 프로젝트 **전용** 비중(%) — UI는 WBS 프리셋에서만 입력칸 노출, 서버도 비WBS는 거부. **유지 확정** — 단 WBS 프로젝트에서만 허용 (2026-07-20) |
| 2 | `customer`가 int ID 전용 | UI는 고객사 **이름 드롭다운**. MCP엔 고객사 목록·이름 해석 수단이 없어 자연어로 사실상 지정 불가 |
| 3 | **필드 해제(null) 불가** | payload를 `if v is not None`으로 걸러 null 전송이 원천 차단됨. UI에서 가능한 "실제 종료일 비우기, 고객사 `-`, 담당자 해제, 상위 태스크 해제" 등이 MCP로는 불가능 |

- `needs_vdc_share`(VDC 공유 필요)·`title_en`(영문 제목)은 검토 시 격차로 식별됐으나 **사용자 결정으로 범위 제외** (2026-07-20).
- `is_archived`는 서버상 쓰기 가능하나 UI 수정 폼이 아닌 별도 보관 액션이므로 이번 범위에서 제외.
- `project`(프로젝트 이동)는 별도 이동 API(parent_action 정책)가 소유하므로 제외.
- 관련자 전체 해제는 `participant_ids=[]`로 이미 가능(빈 리스트는 None이 아니어서 payload에 포함됨).

## 수행 계획

- [x] 1. `update_task` 파라미터 추가 — `weight: int | None` (WBS 프로젝트 전용)
  - MCP 파라미터는 프로젝트별 동적 숨김이 불가하므로 **도구 레벨 가드**로 구현: weight 전달 시 태스크의 프로젝트 preset을 확인해 WBS가 아니면 서버 왕복 전에 ValueError("비중은 WBS 프로젝트에서만 설정 가능")로 차단
  - 왕복 최소화: assignee/participant 해석 시 이미 태스크 상세(`project` id)·프로젝트 상세(`preset` 포함)를 조회하므로 응답을 재사용 (태스크/프로젝트 중복 GET 금지)
  - 형제 그룹 비중 합 100 초과 검증은 서버가 수행하므로 플러그인 재구현 불필요 (서버 오류 메시지 그대로 전달)
  - docstring에 WBS 전용임을 명시 (자연어 호출 시 비WBS에서 시도하지 않도록). parent 변경 시 weight를 서버가 자동 초기화(weight 동시 전달 시 제외)하는 동작도 docstring에 언급
  - 검증: WBS 프로젝트 태스크에 비중 PATCH → `get_task`/웹 UI에서 반영 확인, 비WBS 태스크에 weight 전달 → 도구 레벨 차단 메시지 확인
- [x] 2. `customer`를 `int | str`로 확장 — 이름 전달 시 `GET /api/customers/customers/?workspace=<현재 컨텍스트 워크스페이스>&search=<이름>`으로 ID 해석
  - 경로 주의: config/urls.py `api/customers/` prefix 아래 router가 `customers`를 재등록 → 실제 경로는 `/api/customers/customers/` (프론트 `services/customers.ts`와 동일). 응답은 페이지네이션(`results`) 형식.
  - `search`는 `name` 외 `representative_name`·`contacts__name`도 매칭 → 결과에서 `name` 정확 일치를 우선 채택, 그 외는 후보로만 취급
  - 동명/미존재 시 후보 목록을 담은 ValueError로 안내 (`_resolve_members` 패턴 준용)
  - 호출은 `client.py` 경유, 워크스페이스는 `tokens.py` 컨텍스트 사용
  - 주의: 권한(can_view_customers/OWNER) 없는 워크스페이스는 403이 아니라 **빈 결과**로 걸러짐(queryset 필터) → 결과 0건 시 "미존재 또는 열람 권한 없음 — ID로 직접 지정 가능" 안내 메시지 반환
  - 검증: 이름으로 고객사 지정/변경 → 반영 확인, 미존재/권한 없음(0건) 시나리오 메시지 확인
- [x] 3. 필드 해제(null) 지원 — `clear_fields: list[str] | None` 파라미터 추가
  - 허용 화이트리스트(UI nullable 필드와 동일): `parent, assignee, customer, planned_start_date, planned_end_date, actual_start_date, actual_end_date, weight`
  - 동작: payload 구성 후 `clear_fields`의 필드를 `null`로 강제 주입(동일 필드에 값과 해제를 동시 전달하면 ValueError)
  - 검증: 실제 종료일·고객사·담당자 해제 PATCH → UI에서 `-` 표시 확인
- [x] 4. `create_task` 파라미터 확장 — `parent, customer(int|str), weight, actual_start_date, actual_end_date, progress, tag_ids` 추가
  - weight WBS 가드·customer 이름 해석은 1·2번에서 만든 **공용 헬퍼를 재사용** (로직 중복 금지)
  - `_validate_dates`에 actual 날짜도 전달 (현재 create는 planned만 검증)
  - 완료 상태 자동 보정(progress=100·actual_end_date=오늘)은 **명시 전달값이 우선** — 사용자가 progress/actual_end_date를 직접 준 경우 덮어쓰지 않음
  - `clear_fields`는 생성에 불필요(기본값이 비어 있음) — update_task 전용 유지
  - `is_pinned`는 UI 생성 폼에 없으므로 create에는 추가하지 않음
  - 검증: parent/고객사 이름/태그/실제 날짜/진행률 지정 생성 → get_task·웹 UI 반영 확인, 비WBS weight 차단 확인
- [x] 5. docstring 갱신(양쪽 도구) — 신규 파라미터 설명(자연어 호출 가능 수준), 해제 방법, 고객사 이름 해석 규칙 명시
- [x] 6. `.claude-plugin/plugin.json` version 올리기 (사용자 노출 동작 변경) — 0.1.12 → 0.2.0
- [x] 7. `docs/INDEX.md` 이력 한 줄 추가

## 참고 사항

- 변경 파일(예정): `gdc_mcp/server.py`, `.claude-plugin/plugin.json`, `docs/INDEX.md`
- gdc-service 본체 수정 없음 — 서버는 이미 전 필드 PATCH를 지원하며, 격차는 전부 플러그인(브리지) 쪽.
- 완료 상태 자동 보정(진행률 100·실제 종료일)은 서버가 처리하므로 추가 로직 불필요.
- `create_task` 확장이 범위에 포함됨(2026-07-20 결정). 단 `needs_vdc_share`/`title_en`은 생성·수정 모두 **범위 제외** 유지.
- 자동화 테스트 없음 — 검증은 MCP 도구 직접 호출(자연어) + 웹 UI 확인으로 수동 수행.
