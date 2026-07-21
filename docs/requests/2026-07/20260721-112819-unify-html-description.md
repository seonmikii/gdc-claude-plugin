---
task_id: 15384
task_url: https://gdc.gemiso.com/tasks/15384
---

# 태스크 생성 경로 description HTML 렌더링 통일 (2단계)

| 속성 | 값 |
|------|-----|
| 유형 | refactor / feat |
| 영역 | server/create_task·update_task·sync_doc_progress, gdc_mcp/doc_utils, SKILL(ux-ticket) |
| 날짜 | 2026-07-21 |
| 상태 | partial |
| 관련 | task-from-doc-improvement(1단계), doc_utils(description_to_html), SKILL(ux-ticket, 삭제 예정) |

## 요청 내용

1단계에서 `task_from_doc`에만 적용한 **description → GDC 리치텍스트(HTML) 변환**을,
다른 태스크 생성/수정 경로(`create_task`·`update_task`·`sync_doc_progress`)로 확대해
**모든 경로에서 본문이 일관되게 렌더링**되도록 통일한다.

**전제 제약(신규): `SKILL.md`(ux-ticket)는 이 작업 후 삭제 예정 → 플러그인은 SKILL.md 없이 자립 동작해야 한다.**
코드·프롬프트·커맨드·훅에 SKILL.md/ux-ticket 런타임 참조가 **0건**임을 확인함(grep) — 이미 자립 상태이며
(`description_to_html`은 doc_utils 내장, 프롬프트는 라벨 템플릿을 인라인 포함), 2단계는 이 자립성을 유지·보장한다.

**결정 C·D·E 확정(C-1 / D-1+D-2(b) / E-1) 후 구현 완료(v0.2.4, 56 tests green). 라이브 반영은 MCP 서버 재기동 후.**
서버 재기동 후 create/update 경로의 실제 렌더링 라이브 재확인은 남은 후속 점검이다.

## 배경

### 1단계 결과 (완료분)

- [doc_utils.py](../../../gdc_mcp/doc_utils.py)에 `description_to_html` 헬퍼 추가 —
  라벨 `<p><strong>`, 문단 `<p>`, 블렛 `<ul><li><p>`, 섹션 간격 `<p></p>`, 텍스트 `&`·`<`·`>` 이스케이프.
- `task_from_doc`이 `_strip_meta_steps` 후 이 헬퍼를 태워 전송(v0.2.3). 실제 태스크로 렌더링·볼드 검증 완료.

### 왜 통일이 필요한가

GDC `description`은 **모든 경로에서 동일하게 HTML로 저장·렌더링**된다(실증 확인).
그런데 현재 변환은 `task_from_doc` **한 경로에만** 적용돼 있고, 나머지는 평문을 그대로 보낸다:

| 경로 | 현재 description 처리 | 문제 |
|------|----------------------|------|
| `task_from_doc` | 라벨 템플릿 → **HTML 변환** | (1단계 완료) |
| `create_task` | 자유 입력 **그대로 전송** | `gdc_task_new`이 평문 전송 → 본문 뭉개짐 |
| `update_task` | 자유 입력 **그대로 전송** | 상동 |
| `sync_doc_progress` | 문서 재생성 본문 **그대로 전송** | 문서 본문(평문)이 태스크에 평문으로 반영 |

### ⚠️ 무조건 변환하면 안 되는 이유 (이중 변환 방지)

`create_task`/`update_task`의 description은 **자유 입력**이라 평문일 수도, 이미 HTML일 수도 있다.
공통 레이어가 **무조건 평문→HTML 변환**을 하면 **이미 HTML인 본문이 이스케이프돼 깨진다**(`<p>` → `&lt;p&gt;` 노출).
이미-HTML 입력은 두 경로에서 발생한다:

- **`task_from_doc`의 산출물** — 이미 `description_to_html`로 HTML을 만든 뒤 공통 레이어를 또 거치면 **이중 변환**된다.
- **방어적 대비** — 에이전트/사용자가 직접 HTML을 넘기는 경우. ux-ticket SKILL은 삭제되지만, 누군가 HTML을
  넘겨도 깨지지 않아야 견고하다(플러그인은 특정 호출자 관례에 의존하지 않는다).

즉 공통 레이어는 **"평문(변환 필요)" vs "이미 HTML(통과)"** 를 구분해야 한다 — 평문 경로(`gdc_task_new` 등)는 변환하고
HTML 경로는 통과시킨다. 이 판별 방식이 이번 설계의 핵심 결정이다.

## 개선 방향 (결정 지점)

### 결정 C (핵심) — 공통 레이어의 입력 판별 방식

- **C-1 (권장): 자동 감지.** description에 블록 태그(`<p`·`<ul`·`<li`)가 있으면 이미 HTML로 보고 **그대로 통과**,
  없으면 **평문으로 보고 `description_to_html` 변환**. API 변경 없음, "도구 레벨 정규화" 원칙 부합, 호출자 무수정.
  - 리스크: 평문에 리터럴 `<p>` 같은 문자열이 들어가면 HTML로 오판(희귀). → 문서화 + 필요 시 라벨 템플릿 사용 권장.
- **C-2: 포맷 플래그 파라미터.** `create_task`/`update_task`에 `description_format: "auto"|"html"|"raw"` 추가.
  호출자가 의도를 명시. 명확·견고하지만 **API 표면 증가 + 기본값 결정 + 모든 호출 경로·프롬프트 수정** 필요.
- **C-3: 라벨 템플릿으로 전 경로 통일 + ux-ticket 재작성.** 모든 경로가 라벨 템플릿(평문)을 넘기고 도구가 변환.
  ux-ticket의 HTML 직접 작성을 폐기·재설계. 일관성 최고지만 **SKILL 전면 개편 비용**이 크고 과설계 우려(AGENTS).
- **→ 확정: C-1 (자동 감지).** API 무변경 + 이중 변환 방지 + 견고성. 오판 리스크는 문서화로 커버.

### 결정 D — SKILL.md 삭제 대응 (정렬 → 자립)

ux-ticket SKILL이 삭제되므로 "SKILL과 정렬"은 불필요하다. 대신 두 가지만 처리한다:

- **D-1 (권장): 자립 + 방어적 통과.** 플러그인은 SKILL.md 없이 동작(런타임 참조 0건 확인). C-1 자동 감지가
  누가 HTML을 넘겨도 통과시켜 이중 변환을 막으므로 별도 SKILL 정렬 작업은 없다. 회귀 테스트로 이중 변환 방지만 보장.
- **D-2 (선택): 1단계 문서의 SKILL.md 링크 정리.** [1단계 문서](20260721-095435-task-from-doc-improvement.md)가
  SKILL.md를 링크·인용하는데, 삭제되면 죽은 링크가 된다. 역사적 기록으로 그대로 둘지 / 인용을 본문에 내재화(delink)할지 결정.
- **→ 확정: D-1 (자립 + 방어적 통과) + D-2(b) delink.** 자동 감지로 SKILL 정렬 불필요, 회귀 테스트로 이중 변환만 방지.
  1단계 문서의 SKILL.md 인용은 본문에 내재화하고 링크를 제거한다(Phase 2에서 수행 — 삭제 후 죽은 링크 방지).

### 결정 E — `sync_doc_progress` description 포함 여부

- **E-1 (권장): 포함.** 명시 sync 시 넘기는 재생성 본문도 공통 레이어를 태워 일관 처리.
- **E-2: 제외.** 진행률 전용으로 두고 본문 변환은 생성/수정 경로에만. (충돌 없음이 확실할 때만)
- **→ 확정: E-1 (포함).** 명시 sync의 재생성 본문도 공통 레이어로 일관 처리.

## 제안 범위 (승인 시 — 결정 C-1·D-1·E-1 확정 기준)

공통 변환 진입점을 **client 전송 직전 한 곳**(payload의 `description`)으로 모아 중복을 없앤다.
`task_from_doc`의 기존 변환은 이 공통 레이어로 흡수하되, 이미 HTML을 만들므로 자동 감지로 **통과**되어 동작 동일.

## 작업 결과

> 아래는 승인 시 수행할 계획이며, 현재는 미착수. (결정 C·D·E 확정 후 세부 조정)

### Phase 1 — 공통 변환 레이어

- [x] `doc_utils`에 입력 판별 래퍼 `normalize_description` 추가 — HTML 태그 감지 시 통과, 평문이면 `description_to_html`
- [x] `create_task`·`update_task`·`_apply_progress_sync`의 `description`에 공통 래퍼 적용
- [x] `task_from_doc`의 변환을 공통 래퍼(`normalize_description`) 경유로 정리(동작 동등 — 라벨 템플릿은 평문이라 변환됨)
- [x] 자동 감지·이중 변환 방지 pytest 추가(None/평문/이미-HTML/task_from_doc 산출물/부등호 이스케이프 등 7건, 총 16건)

### Phase 2 — 프롬프트·자립성

- [x] `gdc_task_new` 프롬프트·커맨드에 라벨 섹션 템플릿 안내 확대(선택·짝 규칙 동일, 1:1 유지)
- [x] 자립성 유지 — 코드·프롬프트·커맨드·훅에 SKILL.md/ux-ticket 런타임 참조 0건 확인(grep)
- [x] (D-2) 1단계 문서의 SKILL.md 인용 내재화·링크 제거(delink) — 삭제 후 죽은 링크 방지
- [x] 커맨드/프롬프트 1:1 대응 유지 확인

### Phase 3 — 검증·버전·문서

- [x] 공통 래퍼 로직 pytest 전체 통과(56건). GDC의 우리 HTML 렌더링은 1단계(#15383)에서 이미 확인 — 신규 태스크 미생성
- [x] `.claude-plugin/plugin.json` version 상향 (0.2.3 → 0.2.4)
- [x] `docs/INDEX.md` 이력 한 줄 추가

## 참고 사항

- **결정 확정**: C = C-1(자동 감지 판별), D = D-1(자립 + 방어적 통과) + D-2(b)(1단계 문서 delink),
  E = E-1(sync 포함). → Phase 1~3 착수 가능.
- **`SKILL.md`(ux-ticket)는 이 작업 후 삭제 예정** — 플러그인은 그것 없이 자립 동작해야 하며(런타임 참조 0건 확인),
  2단계는 이 자립성을 전제로 설계한다. (`SKILL (1).md` structure도 외부 참고 자산 — 별도 판단.)
- 1단계에서 확정: description=HTML 저장·렌더링, `<strong>` 지원, 섹션 간격 `<p></p>`.
- gdc-service 본체는 수정하지 않는다(클라이언트 브리지 원칙).
- 상위/하위/연관 태스크 연결(구 Gap 4)은 **별개 후속 과제**로, 이 문서 범위 아님.
- 편집 반영은 **MCP 서버 재기동 후** 라이브에 적용된다(1단계와 동일).
