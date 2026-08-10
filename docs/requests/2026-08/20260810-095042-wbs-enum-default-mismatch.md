---
task_id: 15761
task_url: https://gdc.gemiso.com/tasks/15761
---

# MCP 태스크 생성 시 상태/우선순위/유형이 프로젝트 enum과 어긋나는 문제

| 속성 | 값 |
|------|-----|
| 유형 | fix |
| 영역 | server/gdc_mcp |
| 날짜 | 2026-08-10 |
| 상태 | done |
| 관련 | gdc_mcp/server.py, tests/, .claude-plugin/plugin.json |

## 요청 내용

WBS 프로젝트(WS3 / 프로젝트 46 `WBS 테스트`)에 MCP로 태스크를 생성하면 매핑이 이상하다.

- 태스크 목록에서만 **MCP로 생성한 태스크의 유형·우선순위 라벨이 영어**로 보인다.
- 사이드 패널·상세 페이지에서는 정상(한글)으로 보인다.
- `제목4`만 UI에서 생성한 태스크다.

코드 검토 후 개발 계획을 수립한다.

## 배경 (원인 분석)

### 실측 데이터 (WS3 / 프로젝트 46)

| 태스크 | 생성 경로 | status | priority | task_type | 프로젝트 enum 포함 |
|--------|-----------|--------|----------|-----------|--------------------|
| #11 제목4 (15752) | UI | `등록` | `보통` | (한글) | O |
| #10 제목2 (15750) | MCP | `open` | `medium` | `other` | **X** |
| #9 제목3 (15749) | MCP | `open` | `medium` | `other` | **X** |
| #8 제목1 (15748) | MCP | `open` | `medium` | `other` | **X** |
| #7·#6 임시 검증 (15491·15487) | MCP | `open` | `medium` | `other` | **X** |

프로젝트 46의 enum(`get_project_enums`)은 전부 한글이다 — 상태 `등록/진행/완료`, 우선순위 `낮음/보통/높음/긴급`, 유형 `기획/분석·설계/개발/테스트/기타`.

### 근본 원인 — 클라이언트(이 레포)

`gdc_mcp/server.py`의 `create_task`(:912-936)와 `task_from_doc`(:1556-1569)은
`status`/`priority`/`task_type`이 `None`이면 **payload에서 제거**한다.
그러면 서버가 Django 모델 기본값을 쓴다.

- `backend/tasks/models.py:142-156` → `task_type="other"`, `status="open"`, `priority="medium"` (하드코딩)
- 그런데 프로젝트 enum 시드는 **두 종류**다 (`backend/projects/models.py:605-648`)
  - 이슈관리형: `open/medium/other` (영문)
  - **WBS형: `등록/보통/기타` (한글)**
- 모델 기본값은 영문 시드 고정 → **WBS 프로젝트에는 존재하지 않는 값이 저장된다.**

서버 `TaskSerializer.validate`(`backend/tasks/serializers.py:622-653`)는 **값이 전달된 경우에만** enum 소속을 검증한다. 생략하면 검증을 타지 않고 기본값이 그대로 들어간다.

### UI는 왜 멀쩡한가 — 레퍼런스 클라이언트의 보정 로직

`frontend/src/components/tasks/TaskCreateDialog.tsx`도 **초기값은 MCP와 동일하게** `other/open/medium`으로
하드코딩되어 있다(:186-188). 차이는 프로젝트 enum 목록을 받은 뒤 **보정한다는 점**이다.

```js
// TaskCreateDialog.tsx:68-81
const PREFER_STATUS    = ['등록', 'open']
const PREFER_PRIORITY  = ['보통', 'medium']
const PREFER_TASK_TYPE = ['기타', 'other']

// 생성 모드 디폴트 보정 — 현재 값이 프로젝트 커스텀 세트에 없으면 시드 디폴트 우선으로 대체
const pickName = (items, prefer, current) => {
  const names = items.filter(i => i.is_active).map(i => i.name)
  if (!names.length || (current && names.includes(current))) return current
  return prefer.find(p => names.includes(p)) ?? names[0]   // 최종 폴백: 프로젝트의 첫 활성 항목
}
```

보정된 값은 생성 payload에 **항상 명시 전송**된다(:354-356, :499-501).

→ gdc-service의 계약은 **"클라이언트가 프로젝트 enum에서 값을 골라 항상 보낸다"** 이고,
레퍼런스 클라이언트인 UI는 그 보정을 구현하고 있다. **MCP에만 이 보정이 없는 것이 이번 결함의 근본 원인**이다.
이슈관리 프로젝트에서 문제가 없던 것은 모델 기본값이 그 프로젝트의 enum에 우연히 포함되기 때문이다.

### 왜 목록에서만 영어로 보이는가 — 서버(프론트) 측

```
WBS 태스크 목록  WbsTaskTab.tsx:945/973/1001
    └ <DetailBadge name={task.task_type} …/>   → 원본 name 그대로 출력  → "other"
상세/사이드패널  TaskCard.tsx:53-58 등
    └ resolveOptionLabel(…, 'taskType')        → t('taskType.other', …) → "기타"
```

`optionLabel.ts`의 i18n 폴백이 상세 화면에서 `other→기타`, `medium→보통`으로 번역해 주기 때문에
**저장값이 잘못됐다는 사실이 목록에서만 드러난 것**이다. 라벨 문제가 아니라 **저장값 문제**다.

### 더 심각한 부작용 — 미완료 조회에서 누락

상태 `open`은 프로젝트 46의 상태 집합(`등록/진행`)에 없으므로 미완료 필터에서 통째로 빠진다. 실측:

```
search_tasks()                    → 6건 (MCP 생성 5건 포함)
search_tasks(not_finished=True)   → 1건 (UI 생성 '제목4'만)
```

즉 `list_my_tasks` / `list_tasks` / `search_tasks(not_finished=True)`에서 **MCP로 만든 태스크가 보이지 않는다.**
`get_task`의 `status_category`도 `null`로 나오고, 목록 뱃지 색상(`*_detail`)도 매칭 실패로 회색 처리된다.

부가적으로 MCP 응답의 `_STATUS_LABELS`/`_PRIORITY_LABELS`/`_TASKTYPE_LABELS`(server.py:169-178)가
`open→등록`, `medium→보통`으로 한글 라벨을 붙여 주기 때문에 **MCP 응답만 봐서는 이상을 알 수 없다**(발견이 늦어진 이유).

## 수행 계획

### 1단계 — enum 해석 헬퍼 추가 (순수 로직)

`server.py`에 프로젝트 enum 기준 해석기를 추가한다. 기존 `_done_status_name`/`_in_progress_status_name`(:1420-1447)과 같은 방식.

- `_resolve_enum_value(project_json, kind, value)` — `kind ∈ {status, priority, task_type}`
  - **값이 있을 때**: 프로젝트 enum name과 정확 일치 → 통과.
    불일치면 라벨 매핑표(`_STATUS_LABELS` 등)로 양방향 해석(`높음↔high`, `보통↔medium`).
    그래도 없으면 `ValueError`로 사용 가능한 값 목록을 안내(서버 400 대신 도구 레벨 차단).
  - **값이 없을 때(핵심 수정)**: UI의 `pickName`(TaskCreateDialog.tsx:68-81)과 **동일한 규칙**으로 고른다 —
    선호 목록에서 먼저 찾고, 없으면 프로젝트의 첫 활성 항목.
    - status → `['등록', 'open']` → 없으면 첫 활성 항목 → 46번은 `등록`
    - priority → `['보통', 'medium']` → 없으면 첫 활성 항목 → 46번은 `보통`
    - task_type → `['기타', 'other']` → 없으면 첫 활성 항목 → 46번은 `기타`
  - `is_active=False` 항목은 후보에서 제외(UI와 동일)
  - **UI와 규칙을 일치시키는 것이 목적**이다 — 같은 프로젝트에서 UI 생성과 MCP 생성의 기본값이 달라지지 않는다.
- **UI 규칙 재현 가능성 확인 완료**: 프로젝트 상세에 임베드된 `task_statuses`는 `ProjectStatusSerializer`가
  `is_active`를 포함하고(`backend/projects/serializers.py:113-117`) 모델 `Meta.ordering = ["order"]`
  (`backend/projects/models.py:256-259`)라, UI가 쓰는 별도 엔드포인트와 **필터·정렬이 동일**하다.
  → `names[0]` 최종 폴백까지 `_project()` 응답만으로 UI와 같은 값을 낸다.
- 라벨 역매핑 안전성 확인: `_STATUS_LABELS`/`_PRIORITY_LABELS`/`_TASKTYPE_LABELS`의 한글 값에 중복이 없어
  역방향 매핑이 단사(injective)다(`완료→closed`/`해결→resolved`로 갈리지 않음).
  WBS 전용 유형 `분석/설계`·`테스트`는 영문 대응이 없으므로 이슈관리 프로젝트에 전달되면
  의도대로 후보 목록과 함께 차단된다.
- 검증: pytest(순수 로직, `tests/test_enum_resolve.py`) — 이슈관리 시드·WBS 시드·커스텀 enum·미존재 값 각각.

### 2단계 — `create_task` / `task_from_doc` 적용

- 세 필드를 **항상 명시 전송**하도록 변경(생략 시 1단계 기본값 주입).
- `create_task`는 현재 조건부로만 `_project()`를 조회(:895-899) → 항상 필요해지므로 무조건 조회로 정리(TTL 캐시라 실사용 왕복 증가 0~1회).
- `task_from_doc:1566`의 `_status_category(project, status)`에도 조회한 `project_json`을 넘겨 `create_task:931`과 형태를 맞춘다.
- 검증: pytest + WS3/46 실호출(생성 → `등록/보통/기타` 저장 확인 → 삭제).

### 3단계 — `update_task` 적용

- 전달된 값만 1단계로 해석·검증한다(미전달 필드에 기본값을 주입하지 않는다 — 부분 수정 의미 유지).
- **왕복 비용 증가**: `update_task`는 현재 `weight`/`assignee`/`participant_ids`가 있을 때만 프로젝트를 조회한다(:1014-1021).
  세 필드를 검증하려면 project_id가 필요하고, 그건 **캐시되지 않는 태스크 상세 GET**(:1015)을 거친다
  → `update_task(status=...)` 단독 호출이 **1회 → 3회 요청**이 된다.
  :1014의 조건에 세 필드를 추가해 `project_json`을 **한 번만 받아 재사용**한다(그 이상 늘지 않게).
- 검증: 잘못된 값 전달 시 도구 레벨 차단 메시지 확인.

### 4단계 — enum 불일치 표시 (검토 후 축소 채택)

`_STATUS_LABELS`/`_PRIORITY_LABELS`/`_TASKTYPE_LABELS`(server.py:169-178)는 프로젝트 enum을 보지 않고
무조건 번역하므로, **프로젝트에 없는 값도 정상처럼 보인다**. 이번 결함의 발견이 늦어진 직접적 원인이다.

**규칙 — 기존 `*_label`은 현행 그대로 두고, enum 미소속 값이 있을 때만 `enum_mismatch`를 덧붙인다.**

원안은 미소속 값의 라벨도 원값으로 되돌리는 것이었으나, 진단 목적은 `enum_mismatch` 하나로 충족되고
라벨 변경은 사용자 노출 응답의 표면적만 넓힌다고 판단해 **축소 채택**했다(기존 출력 형태 변화 0 → 버전은 0.7.1 유지).

```jsonc
// get_task(15748) — 변경 후
{
  "status": "open", "status_label": "등록",        // 현행 유지
  "priority": "medium", "priority_label": "보통",  // 현행 유지
  "task_type": "other", "task_type_label": "기타", // 현행 유지
  "enum_mismatch": ["status", "priority", "task_type"]   // 불일치 항목이 있을 때만 포함
}
```

- 적용 범위: `get_task`, 목록 요약(`_task_summary`/`_finalize_task_list`).
  - `_task_summary`(:362-383)는 `task_type`을 노출하지 않지만 `TaskListSerializer`가 `task_type`을 포함하므로
    **판정 자체는 세 필드 모두 가능**하다(라벨만 노출되지 않을 뿐). 판정기는 입력 dict에 있는 필드만 검사한다.
- 정상 데이터의 표시는 바뀌지 않는다 → 기존 워크플로우 영향 없음.
- **비용(원안 수정)**: `_task_summary`는 단일 프로젝트 전용이 아니다 —
  `list_my_tasks`의 컨텍스트 미설정 폴백(:428-437)은 mine 전체를 훑고,
  `get_task`의 `sub_tasks`·`related_tasks`(:1286-1287)도 다른 프로젝트일 수 있다.
  → 최악의 경우 **결과에 등장하는 고유 프로젝트 수만큼** `_project()` 호출.
  :429-437에 이미 있는 `cache: dict[int, set[str]]` 패턴을 재사용해 프로젝트당 1회로 묶는다
  (TTL 60초 캐시와 합쳐 단일 프로젝트 조회 시 실사용 왕복 증가 0~1회).
- 1~3단계 이후에도 불일치가 계속 생길 수 있는 경로가 남아 있어 진단 장치로 유지할 가치가 있다.
  - **프로젝트 설정에서 enum 삭제** — 이름 변경은 서버가 태스크까지 일괄 갱신하지만
    (`backend/projects/views.py:1467-1486`, 테스트 3건), **삭제는 사용 중 가드도 이관도 없다**(:1488-1490).
  - 레거시 데이터, 다른 스크립트·API 클라이언트.
- 부수 효과: 잘못된 저장값이 MCP 응답에서 조용히 정상처럼 보이는 상황을 `enum_mismatch`가 드러낸다.

### 5단계 — 기존 데이터 보정 (테스트 워크스페이스 한정)

**운영 데이터는 건드리지 않는다.** 조회·점검도 하지 않는다.

- 대상: **WS3 / 프로젝트 46 (`WBS 테스트`)** 뿐.
  - 15748·15749·15750 → `등록/보통/기타`로 보정(2·3단계 검증 겸용).
  - 과거 검증 잔여물 15487·15491(`[임시] is_html 앵커링 검증 p46`) → 삭제.
- 운영 워크스페이스의 WBS 프로젝트에 같은 데이터가 있을 수 있으나 **이번 작업 범위에서 제외**한다.
  필요하면 별도 요청으로 다룬다.

> 참고: WS3는 로컬 인스턴스가 아니라 운영 도메인(`gdc.gemiso.com`) 안의 **테스트 워크스페이스**다.
> 여기서의 "운영 건드리지 않기"는 **운영 워크스페이스/프로젝트(WS6/16 등 실제 업무 데이터)를 제외**한다는 뜻으로 해석했다.

### 6단계 — 버전·문서

- `.claude-plugin/plugin.json` `0.7.0 → 0.7.1`.
- README: 도구 목록·기본값 관련 서술이 없어(도구 표에 status/priority 기본값 설명 없음) **갱신 대상 없음** — 변경 시에만 반영.
- `docs/INDEX.md` 이력 1줄 추가.

## 서버(gdc-service) 측 관찰 — 결함 아님, 이 레포에서 수정하지 않음

**이번 결함의 원인은 서버가 아니다.** 조사 중 확인한 두 가지를 기록만 해 둔다.

1. **`backend/tasks/models.py:142-156` 모델 기본값 하드코딩** — 프로젝트 enum 기반이 아니라 영문 시드 고정이다.
   자기 validator(`serializers.py:622-653`)가 거부할 값을 생성 경로에서는 통과시킬 수 있다는 점에서 취약하지만,
   **"클라이언트가 값을 골라 보낸다"** 는 현행 계약 아래에서는 UI도 동일 전제로 동작한다(`pickName`).
   서버가 프로젝트 enum 기준으로 기본값을 정하도록 바꾸면 방어가 한 겹 늘지만, **선택적 개선**이며 이번 수정의 전제 조건은 아니다.
2. **`frontend/src/components/wbs/WbsTaskTab.tsx:945/973/1001`** — `DetailBadge`가 `resolveOptionLabel`을 거치지 않고 원본 name을 출력한다.
   이번 건에서는 이 화면이 **잘못된 저장값을 그대로 보여준 유일한 화면**이었다(상세·사이드패널은 i18n 폴백 `other→기타`가 이상을 가렸다).
   남는 실제 문제는 영문 로케일에서 `name_en`이 무시되는 정도이고, 이를 `resolveOptionLabel`로 바꾸면 데이터 이상이 다시 가려진다 → **우선순위 낮음, 별도 판단 대상**.

1~3단계 클라이언트 수정만으로 이번 결함은 완결된다.

## 작업 결과

- [x] 1단계 — `_resolve_enum_value`·`_enum_checker` 추가 + pytest(`tests/test_enum_resolve.py` 20건)
- [x] 2단계 — `create_task`·`task_from_doc`에서 세 필드 항상 명시 전송(`_project()` 무조건 조회로 정리, `task_from_doc`의 `_status_category`에 `project_json` 전달)
- [x] 3단계 — `update_task` 값 해석·검증 적용(:1014 조건에 세 필드 추가 → 프로젝트 상세 1회 재사용, 미전달 필드는 미주입)
- [x] 4단계 — enum 불일치 표시(`get_task`·목록 요약에 `enum_mismatch`, 기존 `*_label`은 현행 유지, 프로젝트당 1회 조회)
- [x] 5단계 — WS3/46 데이터 보정(15748·15749·15750 → `등록/보통/기타`)·잔여물 15487·15491 휴지통 이동 (운영 데이터 미접근)
- [x] 6단계 — `plugin.json` 0.7.1 · README 도구표 3행(`create_task`/`update_task`/`get_task`) · `docs/INDEX.md` 이력 1줄
- [x] 로컬 사전 검증 — WS3/46에서 로컬 코드 직접 호출(생성·수정·차단), 임시 태스크 15760 영구 삭제, 컨텍스트 WS6/16 복원

### 검증 결과 (WS3 / 프로젝트 46, 로컬 코드 직접 호출)

| 항목 | 기대 | 결과 |
|------|------|------|
| enum 생략 생성 | `등록/보통/기타`, `status_category=planned` | ✅ (#15760) |
| 잘못된 값(`review`) | 도구 레벨 차단 + 후보 안내 | ✅ `사용 가능: 등록, 진행, 완료` (전송 없음) |
| 영문 코드 입력(`in_progress`/`high`) | `진행`/`높음`으로 해석 | ✅ |
| 미전달 필드(`task_type`) | 변경되지 않음 | ✅ `기타` 유지 |
| 보정 전 `get_task(15748)` | `enum_mismatch` 3필드 | ✅ |
| 보정 후 `search_tasks(not_finished=True)` | 누락 해소 | ✅ **1건 → 4건** |
| 정리 | 임시 데이터 잔존 0 | ✅ 15760 영구 삭제(204/204), 컨텍스트 WS6/16 복원 |
| 회귀 | pytest | ✅ 187 passed (기존 167 + 신규 20) |

## 참고 사항

- 원인 조사는 읽기 전용 조회만 수행했고(`get_project_enums`·`search_tasks`·`get_task`), 검증 후 컨텍스트를 WS6/16으로 복원했다.
- **다른 쓰기 경로 점검 완료**: `_apply_progress_sync`(server.py:1341-1349)는 이미 프로젝트 enum의 `category`로
  상태를 고르므로 안전하다 → **기본값 주입 경로는 `create_task`·`task_from_doc` 2곳이 전부**다.
- 진행 전 최종 검토(2026-08-10)에서 확인·수정한 것: ①1단계 UI 규칙 재현 가능성·역매핑 단사성 검증 추가,
  ②3단계 왕복 비용(1→3회) 명시, ③4단계 비용 서술 정정(목록은 다중 프로젝트 가능)·`task_type` 미포함 주의 추가,
  ④4단계 범위를 `enum_mismatch` 추가로 축소.
- 프로젝트 16(GDC-Support)은 영문 시드 기반이라 모델 기본값이 우연히 enum에 포함된다 → 지금까지 문제가 드러나지 않았다. **WBS형(한글 시드) 프로젝트에서만 발현**한다.
