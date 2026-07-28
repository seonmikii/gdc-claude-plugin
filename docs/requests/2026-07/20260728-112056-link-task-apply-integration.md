---
task_id: 15435
task_url: https://gdc.gemiso.com/tasks/15435
---
# /gdc-link-task 기능 개선 — 연동 후 태스크 본문 반영(/gdc-apply) 연결

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | commands/gdc-link-task, server/gdc_link_task 프롬프트 |
| 날짜 | 2026-07-28 |
| 상태 | done |
| 관련 | #410, #292(상위), gdc-apply, link_task_to_doc, edit_task_description, sync_doc_progress |

## 요청 내용

`/gdc-link-task`로 **기존 태스크 ↔ 기존 문서**를 연동할 때, 현재는 문서 frontmatter에 `task_id`/`task_url`만 기록되고 **태스크 본문(description)은 그대로 남는다**. 연동 대상 문서에 이미 정리된 요청 내용·작업 계획이 있어도 태스크에는 반영되지 않아, 연동 직후 태스크와 문서 내용이 어긋난 상태가 된다.

개선 목표: **연동 직후 문서 내용을 태스크에 반영하는 흐름(`/gdc-apply`)까지 이어지게** 한다.

- 연동(frontmatter 기록) → 태스크 현재 본문 확보 → 문서와 비교·분류 → 반영 위치 질문 → 라우팅(본문 최소편집 / 댓글 / 하위 태스크)
- 반영은 **본문 통째 덮어쓰기 금지** 원칙을 유지한다(인라인 이미지 유실 방지, [#345 결정](20260723-143718-task-edit-reflect-improvement.md)).
- 진행률·상태·날짜는 기존대로 `/gdc-sync`(`sync_doc_progress`) 담당 — 반영 흐름과 역할을 섞지 않는다.

### 현황 (관련 코드 검토 결과)

| 구성요소 | 현재 동작 | 위치 |
|---|---|---|
| `link_task_to_doc(doc_path, task_id)` | 태스크 존재 확인(GET) 후 문서 frontmatter upsert만. **태스크 PATCH 없음** | [server.py:1026-1044](../../../gdc_mcp/server.py#L1026-L1044) |
| `/gdc-link-task` 커맨드 | 1) 경로 확정 2) `link_task_to_doc` 호출 3) 결과 보고 + "진행률은 `/gdc-sync`" 안내로 종료 | [commands/gdc-link-task.md](../../../commands/gdc-link-task.md) |
| `gdc_link_task` 프롬프트 | 커맨드와 동일 3단계(1:1 유지) | [server.py:1858-1867](../../../gdc_mcp/server.py#L1858-L1867) |
| `/gdc-apply` · `gdc_apply` | 분류(추가/변경) → `AskUserQuestion` → `edit_task_description`(append_work/replace_section) / `add_task_comment` / `create_task` 라우팅 | [commands/gdc-apply.md](../../../commands/gdc-apply.md), [server.py:1883-1903](../../../gdc_mcp/server.py#L1883-L1903) |

→ 반영에 필요한 도구·흐름(`/gdc-apply`)은 **이미 전부 존재**한다. 빠진 것은 **연동 커맨드에서 그 흐름으로 이어지는 연결**뿐이다.

### 설계 결정

**1) 도구(`link_task_to_doc`)가 아니라 오케스트레이션(커맨드/프롬프트) 계층에서 연결한다.**

반영에는 "추가 작업 vs 내용 변경" 분류와 반영 위치 질문(`AskUserQuestion`)이 필요한데, MCP 도구는 비대화형 단발 호출이라 질문 채널이 없다. `link_task_to_doc`에 본문 PATCH를 넣으면 **질문 없이 본문을 덮어쓰는** 결과가 되어 #345에서 확정한 안전 원칙과 충돌한다. → 도구는 현재 그대로 두고, 커맨드/프롬프트 절차에 반영 단계를 추가한다.

```
[/gdc-link-task <task_id> [doc]]
   │
   ├─ 1. 문서 경로 확정
   ├─ 2. link_task_to_doc(doc, task_id)   → frontmatter task_id/task_url 기록
   ├─ 3. get_task(task_id)로 현재 본문 확보 → 문서와 항목 단위 비교
   │        │
   │        ├─ 이미 반영됨 ──▶ 연동 결과만 보고(끝)
   │        └─ 미반영 항목 있음
   │                └─ 4. 게이트 질문(AskUserQuestion) — 2지선다
   │                       ├─ ① 지금 반영 ──▶ /gdc-apply 절차 수행
   │                       │                   (분류 → 위치 질문 → 라우팅)
   │                       └─ ② 연동만 ──▶ 끝
   └─ 5. 결과 보고 + 진행률은 /gdc-sync 안내
```

**2) 반영은 선택 단계(opt-out 가능)로 둔다.** 연동만 하고 싶은 경우(문서가 아직 초안, 태스크 본문이 최신인 경우)가 있으므로 4단계에 "연동만" 선택지를 둔다. 이미 연동된 문서를 다시 반영할 때는 기존 `/gdc-apply`를 그대로 쓴다(중복 경로 신설 없음).

**2-1) 반영 절차는 복사하지 않고 `/gdc-apply`에 위임한다.** `/gdc-apply`는 이미 분류·위치 질문·`keep_media` 경고·HTML 형식 규칙까지 7단계를 갖고 있다. 이를 `gdc-link-task`에 복사하면 동일 절차가 4곳(커맨드 2 + 프롬프트 2)에 존재해 이후 apply 규칙 변경 시 드리프트가 확실하다.

- **커맨드**: Claude Code에서 `/gdc-apply`가 Skill로 노출되므로 "반영 선택 시 `/gdc-apply` 절차 수행"으로 위임한다.
- **프롬프트**: Desktop은 프롬프트 간 호출이 없으므로 `gdc_apply` 본문을 모듈 레벨 헬퍼(`_apply_steps(path)`)로 추출해 `gdc_apply`·`gdc_link_task` 두 프롬프트가 **같은 문자열을 공유**한다. FastMCP `@mcp.prompt`로 감싼 함수를 직접 호출하지 않는다(래핑 객체).
- 게이트를 2지선다로 두는 이유: 링크 단계에서 반영 위치를 먼저 물으면 `/gdc-apply`의 분류 후 질문과 **중복 질문**이 된다.

**2-2) "이미 반영됨" 판정은 항목 단위 의미 비교로 한다.** 문서(마크다운)와 본문(GDC 리치텍스트 HTML)은 표현이 달라 텍스트 비교로는 항상 "차이 있음"이 된다. 문서의 요청 내용·`## 작업 결과` 항목이 태스크 `[작업 내용]` 블렛/섹션에 이미 담겨 있는지를 기준으로 판단하고, **애매하면 게이트 질문으로 넘긴다**(기본값).

**3) 본문이 비어 있는 태스크는 `append_work`로 처리한다.** `[작업 내용]` 섹션이 없으면 `append_work_bullets`가 라벨 블록을 신설하므로 별도 분기가 필요 없다.

**4) 진행률 동기화는 자동 실행하지 않는다.** 연동 시점에 문서 체크리스트가 태스크 상태를 앞질러 상태·실제 날짜가 의도치 않게 전이될 수 있다. 현행대로 `/gdc-sync` 안내만 유지한다.

## 작업 결과

- [x] `gdc_apply` 프롬프트 본문을 모듈 레벨 헬퍼 `_apply_steps(include_fetch, prefix)` + `_APPLY_HEAD`로 추출(`gdc_apply`는 헬퍼 호출로 축약). 절차 문구는 유지하되 append 항목에 "본문이 비어 있으면 `[작업 내용]` 라벨 블록 신설" 한 구절만 추가하고 `commands/gdc-apply.md`에도 동일 반영(슬래시↔프롬프트 1:1)
- [x] `commands/gdc-link-task.md`에 3~4단계 추가: `get_task` 본문 확보 → 항목 단위 비교 → 미반영 시 2지선다 게이트(지금 반영 / 연동만) → 반영 선택 시 `/gdc-apply` 절차 위임
- [x] `gdc_link_task` MCP 프롬프트([server.py:1858](../../../gdc_mcp/server.py#L1858))에 동일 절차 반영 — `[반영 절차]` 블록을 `_apply_steps(include_fetch=False, prefix="4-")` 공유로 삽입(슬래시↔프롬프트 1:1 유지). 바깥 단계 `1~5`와 번호가 겹치지 않도록 `4-1.`~`4-6.` 접두를 붙이고, 블록 제목에 "4단계에서 ①을 고른 경우에만 수행"을 명시
- [x] 본문 통째 덮어쓰기 금지·`edit_task_description` 최소편집 원칙을 절차 문구에 명시(빈 본문은 `append_work`로 라벨 블록 신설)
- [x] 진행률·상태·날짜는 `/gdc-sync` 담당임을 명시(연동 시 자동 sync 하지 않음)
- [x] `README.md` 커맨드 표(81행) 설명을 "연동 + 문서 내용 반영(선택)"으로 갱신
- [x] `.claude-plugin/plugin.json` 버전 업(0.6.1 → 0.6.2)
- [x] pytest 회귀 확인(`uv run python -m pytest tests/` → 112 passed, 신규 케이스 없음)
- [x] 로컬 사전 검증(WS3 / `45 이슈관리 테스트`): 사전 `get_context` = WS6/16 기록 → 임시 태스크 #15476 + 임시 문서로 연동 흐름 실행 → frontmatter 기록·미반영 항목(B·C)만 `append_work` 추가(기존 A 보존)·진행률 0 유지 확인 → 태스크 삭제·임시 문서 삭제·컨텍스트 WS6/16 복원 완료
- [x] `docs/INDEX.md` `## 이력` 한 줄 추가

## 참고 사항

- **범위 밖(non-goals):** `link_task_to_doc` 도구에 본문 PATCH 추가(비대화형 → 질문 불가, 덮어쓰기 위험) · 연동 시 진행률 자동 동기화 · 새 반영 도구 신설(기존 `edit_task_description`/`add_task_comment`/`create_task`로 충분) · `/gdc-apply` 절차 자체의 변경(헬퍼로 이동 + 빈 본문 안내 한 구절 보강까지만, 커맨드·프롬프트 동시 반영).
- 이번 변경은 **커맨드/프롬프트 문구(오케스트레이션) 중심**이라 Python 순수 로직 변경이 없어 pytest 신규 케이스는 없다(`_apply_steps`는 문자열 반환 헬퍼 — 기존 111건 회귀 확인만).
- 태스크 #410 댓글 0건 — 요구사항은 본문 `[AS-IS]`/`[TO-BE]`만 근거로 정리했다.
- 상위 태스크: [#292 MCP 서버 기능 개선](https://gdc.gemiso.com/tasks/14957).
