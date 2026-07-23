---
task_id: 15222
task_url: https://gdc.gemiso.com/tasks/15222
---

# 문서 변경의 태스크 반영 개선 — 추가/수정 분기·append·부분 교체·이미지 보존

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | server/edit_task_description·doc_utils, commands, hooks |
| 날짜 | 2026-07-23 |
| 상태 | done |
| 관련 | #345, server, doc_utils, sync_doc_progress, update_task, add_task_comment, create_task |

## 요청 내용

작업 요청 문서에 **추가 작업**이 생겨 태스크에 반영할 때:

1. 추가된 작업을 **태스크 본문(description)에 추가**할지, **하위 태스크로 새 태스크를 생성**할지 물어본다.
2. 본문에 추가하는 경우 기존 내용을 **덮어쓰지 않고 append**(추가분만 반영)한다.
3. 추가가 아니라 **내용 자체가 변경**되는 경우, 해당 부분만 수정할 수 있는지 검토하고 반영한다.
4. 내용 변경 시 기존 **이미지/첨부파일이 유지**되는지 검토한다.

## 배경

**현재 구조 (반영 경로별 동작):**

```
문서 저장 ──자동 훅(PostToolUse)──▶ 진행률·상태·날짜만 동기화  (비대화형, 본문 미변경, 질문 불가)
문서 저장 ──에이전트 반영───────▶ description 통째 덮어쓰기      (질문 없음, append 아님)
```

- 자동 훅([server.py:1499-1520](../../../gdc_mcp/server.py#L1499-L1520))은 stdin→exit 단발 배치라 사용자와 대화할 채널이 없다. → **질문/본문 반영은 훅에서 불가**, 에이전트가 관여하는 명시적 반영 시점에서만 가능.
- description 반영은 `sync_doc_progress(description=...)`·`update_task(description=...)` 모두 **전체 교체** ([server.py:951](../../../gdc_mcp/server.py#L951), [server.py:711](../../../gdc_mcp/server.py#L711)). 추가분만 붙이거나 일부만 고치는 수단이 없고, 재구성한 본문을 통째로 보내므로 **본문 인라인 이미지가 유실**된다(아래 §이미지/첨부 보존 참조).

## 설계

### 1. 반영 흐름 (분류 → 질문 → 라우팅)

문서→태스크 "반영"은 **명시적 행동에서만** 일어난다: (a) 에이전트가 문서를 고친 뒤 반영("태스크에 반영해줘"), (b) 신규 커맨드 `/gdc-apply`. **자동 훅은 지금처럼 진행률·상태·날짜만** 담당(변경 없음).

에이전트가 `get_task`로 **현재 태스크 본문**을 가져와 문서(`## 작업 결과`/본문)와 비교해 **추가 작업 vs 내용 변경**으로 분류한다(에이전트 판단).

```
[반영 트리거] ──▶ get_task로 현재 본문 확보 ──▶ 문서와 비교·분류
      │
      ├─ 추가 작업? ──▶ 물어봄 ─┬─ ① 본문 append : [작업 내용] 아래 블릿 추가
      │                         ├─ ② 댓글        : [추가 (날짜)] 라벨 + 블릿
      │                         └─ ③ 하위 태스크  : create_task(parent=task)
      │
      └─ 내용 변경? ──▶ 물어봄 ─┬─ ① 본문만 최신화 (바뀐 라벨 섹션만 교체)
                               ├─ ② 댓글만        ([변경 (날짜)] + 이유 + 전/후), 본문 유지
                               └─ ③ 둘 다          (본문 교체 + 변경이력 댓글)
```

- **질문은 자동 팝업이 아니다.** 반영을 트리거할 때 에이전트가 묻는다(훅은 대화 불가).
- 내용 변경은 **질문이 선행**하고 그 답에 따라 본문/댓글/둘 다로 라우팅한다. 댓글은 ②·③에서만 남는다.
- 변경 이유(변경이력 댓글용)는 에이전트가 문서 diff·맥락에서 초안 작성, 사용자가 수정 가능.

### 2. 새 도구 & 순수 헬퍼

**신규 도구 1개** — `edit_task_description(task_id, mode, ...)`:

- `mode="append_work"`: `[작업 내용]` 섹션 `<ul>` 뒤에 블릿 추가(없으면 라벨 블록 신설). **통째 덮어쓰기 아님** — `get_task`로 현재 HTML을 받아 append만 PATCH.
- `mode="replace_section"`: 지정한 `[라벨]` 블록만 교체, 나머지 섹션 보존.

②댓글 / ③하위 태스크 / 변경이력 댓글은 **기존 도구**(`add_task_comment`, `create_task`)로 처리 — 새 도구 불필요.

**`doc_utils.py` 순수 함수 추가**(pytest 검증 대상):

- `split_label_sections(html)` — `<p><strong>라벨</strong></p>` 경계로 라벨 섹션 파싱.
- `append_work_bullets(html, bullets)` — `[작업 내용]`에 `<li>` 블릿 추가.
- `replace_label_section(html, label, new_html)` — 라벨 섹션 교체.

라벨 경계가 명확해 **정확 HTML 조각 매칭 없이 안전하게 섹션 단위 부분 교체**가 된다. 임의 문장 단위 in-place 교체는 GDC의 HTML 재정규화로 취약 → 채택하지 않음.

> **파서 작성 순서(중요):** 라벨 경계 가정 `<p><strong>라벨</strong></p>`은 `description_to_html`가 **생성**하는 형식이지 GDC가 저장·재정규화 후 **반환**하는 HTML이 아니다(에디터가 `<strong>`→`<b>`, 속성/래핑 변경 가능). 따라서 정규식/파서를 짜기 **전에** WS3 테스트 태스크에 `[작업 내용]` 본문을 저장→`get_task`로 실제 반환 HTML을 확보하고, 그 실측 형식에 맞춰 `split_label_sections`를 구현한다.

### 3. 오케스트레이션 (질문 로직 위치)

- **신규 커맨드 `/gdc-apply`** + 대응 **MCP 프롬프트**(슬래시↔프롬프트 1:1 규칙) — 분류→질문→라우팅.
- 기존 `/gdc-sync`(진행률 강제 동기화)는 그대로 유지, 역할 분리.
- 수동 반영 경로와 커맨드가 **동일 도구/지침(공통 로직)** 을 공유.

### 4. 이미지/첨부 보존 (gdc-service 코드 근거, 읽기 전용 확인)

| 종류 | 저장 방식 | PATCH description 영향 |
|------|-----------|------------------------|
| 태스크 첨부파일 | 별도 엔티티 `TaskAttachment`(S3, `attachments` M2M) [tasks/models.py:319](../../../../gdc/gdc-service/backend/tasks/models.py#L319) | `attachment_ids` 미전송 시 **유지** [serializers.py:368](../../../../gdc/gdc-service/backend/tasks/serializers.py#L368) → 안전 |
| 본문 인라인 이미지 | description HTML 내 `<img data-attachment-id="N" src="<presigned>">` [serializers.py:92-96](../../../../gdc/gdc-service/backend/tasks/serializers.py#L92-L96), 조회 시 src 재갱신 [L576](../../../../gdc/gdc-service/backend/tasks/serializers.py#L576) | **전체 덮어쓰기 시 유실** — 재구성 본문엔 `<img>` 없음 |

`data-attachment-id`가 안정적 앵커, `src`는 조회 때마다 재갱신 → **`<img>` 태그만 보존하면 이미지 유지**.

**안전 원칙 (설계 확정):**

- 문서로 본문을 **통째 재구성해 보내지 않는다.** 항상 `get_task`로 현재 HTML을 받아 **최소 편집**(append / 라벨 섹션 1개 교체)만 PATCH → 편집 대상 밖 `<img data-attachment-id>` 자동 보존.
- `append_work`: 기존 HTML 뒤에만 추가 → 이미지 100% 보존.
- `replace_section` 헬퍼: 교체 대상 섹션 내부에 미디어(`data-attachment-id`/`<img>`)가 있으면 **경고 후 사용자에게 유지/삭제를 물어 분기**(결정 확정).
  - **① 이미지 유지(`keep_media=True`, 기본)**: 섹션에서 `<img>` 태그를 추출해두고 텍스트/블릿만 새 내용으로 교체한 뒤, 추출한 `<img>`를 **섹션 끝에 재삽입** → 이미지 보존.
  - **② 이미지 삭제(`keep_media=False`)**: 섹션 전체를 새 내용으로 교체(`<img>` 함께 제거).
  - **절충(합의 확정)**: `keep_media=True`일 때 보존 이미지는 **원래 인라인 위치가 아니라 해당 섹션 하단**에 놓인다(재작성 텍스트 내 정확한 옛 위치 복원은 GDC 재정규화로 취약 → 채택 안 함). 같은 섹션 내 유지는 보장, 문단 간 위치 이동만 감수.

→ 이번 개선은 append/부분 교체로 전환하며 **기존 전체 덮어쓰기의 이미지 유실까지 부수적으로 해소**한다.

**기존 lossy 경로 리다이렉트(결정 확정):** `sync_doc_progress(description=...)`의 full-replace([server.py:951](../../../gdc_mcp/server.py#L951))와 이를 지시하는 sync 프롬프트([server.py:1493-1494](../../../gdc_mcp/server.py#L1493-L1494))는 여전히 "본문 통째 재생성"을 유도해 이미지 유실 footgun이 남는다. 프롬프트/지침을 새 `edit_task_description`(최소편집) 기반으로 리다이렉트해 full-replace 유도를 제거한다. (`sync_doc_progress`는 진행률·상태·날짜 동기화 본연 역할 유지)

## 작업 결과

- [x] `doc_utils.py`에 순수 헬퍼 추가(`split_label_sections`·`append_work_bullets`·`replace_label_section`, +`label_section_has_media`) + pytest(19 케이스)
- [x] `edit_task_description` 도구 추가(`append_work`/`replace_section`, get_task→최소편집→PATCH raw HTML)
- [x] `replace_section` 섹션 내부 미디어(`<img>`) 감지 시 경고 후 유지/삭제 분기(`keep_media`); 유지 시 `<img>` 추출→텍스트만 교체→섹션 끝 재삽입
- [x] (선행) WS3 테스트 태스크(#15428)로 GDC 실제 반환 HTML 확보 → 생성 형식 그대로 반환(`<strong>` 유지) 실증 → 그 형식에 맞춰 `split_label_sections` 구현
- [x] `sync_doc_progress` full-replace 유도 프롬프트/지침을 `edit_task_description` 최소편집 기반으로 리다이렉트(프롬프트+커맨드 md)
- [x] `/gdc-apply` 커맨드 + 대응 MCP 프롬프트 추가(분류→질문→라우팅, 슬래시↔프롬프트 1:1)
- [x] 수동 반영 경로가 동일 도구/지침 공유(`edit_task_description`+`gdc_reflect` 공통) 반영
- [x] `.claude-plugin/plugin.json` 버전 업(0.3.0→0.4.0)
- [x] 로컬 사전 검증(WS3/45, #15428): append 후 기존 블렛·타 섹션 잔존·`<ul>` 중복 없음 / replace_section 시 타 섹션 보존 / keep_media 시 `<img data-attachment-id>` 태그 보존+경고 / 본문 원복 후 임시 태스크 삭제(204)·컨텍스트 WS6/16 복원 — 전 항목 성공
- [x] `docs/INDEX.md` 이력 추가

## 참고 사항

- **범위 밖(non-goals):** 자동 훅에서 질문/본문 반영(구조상 불가, 미변경) · 임의 문장 단위 in-place 교체(취약, 제외).
- **불변 규칙:** gdc-service 본체는 이 레포에서 수정하지 않는다(위 근거는 읽기 전용 확인). 서버 동작 변경 필요 시 별도 처리.
- **로컬 사전 검증 대상:** 테스트 워크스페이스 3([TEST] GDC 메인), 이슈관리 성격 → `45 이슈관리 테스트`(도메인 불명확 시 사용자 확인). 검증용 임시 데이터·컨텍스트는 원복.
- 구현 완료(브랜치 `feat/task-edit-reflect`). pytest 95건 통과, WS3 실서버 사전 검증 성공·원복 완료.
- 커맨드/프롬프트명 변경: `/gdc-reflect`→`/gdc-apply`, `gdc_reflect`→`gdc_apply` (v0.4.1).
