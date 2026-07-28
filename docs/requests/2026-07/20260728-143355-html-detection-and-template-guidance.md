---
task_id: 15485
task_url: https://gdc.gemiso.com/tasks/15485
---

# 본문 HTML 오판 수정 + 태스크 생성 도구에 라벨 템플릿 안내 추가

| 속성 | 값 |
|------|-----|
| 유형 | fix |
| 영역 | server/gdc_mcp |
| 날짜 | 2026-07-28 |
| 상태 | done |
| 관련 | doc_utils, server, test_description_html |

## 요청 내용

태스크 본문(description)이 규격대로 저장되지 않는 결함 두 가지를 함께 수정한다.

1. **`is_html()` 오판** — 평문 안에 리터럴 HTML 태그 문자열이 있으면 "이미 HTML"로 판정해 변환을 통째로 건너뛴다. 판정 기준을 "텍스트가 태그로 **시작**할 때"로 좁힌다.
2. **템플릿 안내 부재** — 태스크 본문을 평문으로 받는 도구·경로 중 라벨 섹션 템플릿 규격을 안내하지 않는 곳이 있다. 도구 docstring과 반영 절차(프롬프트·커맨드)에 템플릿을 명시한다.

### 본문 기록 경로 전수 점검

| 경로 | 변환 | ① 앵커링 | ② 템플릿 안내 |
|------|------|---------|--------------|
| `create_task` | `normalize_description` | 자동 적용 | **없음 → 추가** |
| `update_task` | `normalize_description` | 자동 적용 | **없음 → 추가** |
| `task_from_doc` | `normalize_description` | 자동 적용 | 있음(docstring) |
| `sync_doc_progress(description=)` | `normalize_description`([server.py:1119](../../../gdc_mcp/server.py#L1119)) | 자동 적용 | **없음 → 추가** |
| `add_task_comment`/`update_task_comment` | `_build_comment_html` → `normalize_description` | 자동 적용 | 해당 없음(댓글은 `[추가 (날짜)]` 형식) |
| `edit_task_description` | **`normalize_description` 미경유** — `append_work_bullets`가 `html.escape` 직접([doc_utils.py:272](../../../gdc_mcp/doc_utils.py#L272)), `replace_section`은 원시 HTML 계약 | 무관(오판 발생 불가) | 해당 없음 |
| `/gdc-apply` ③ 하위 태스크 | `create_task(parent=)` 호출 | 자동 적용 | **없음 → 추가** |
| `/gdc-link-task` 반영 단계 | `_apply_steps()` 공유 | 자동 적용 | **없음 → 추가** |

①은 `normalize_description`을 경유하는 모든 진입점에 자동 적용되므로 누락이 없다. ②는 위 표의 **없음** 5곳이 대상이다.

## 배경

### 실제 재현 (2026-07-28, 태스크 #417 생성 시)

`create_task`에 라벨 섹션 평문을 넘겼으나 본문이 줄바꿈 없는 한 덩어리로 저장됐다. 넘긴 평문에 아래 **설명 문장**이 포함돼 있었던 것이 원인이다.

```
... 현재 본문 선두에 평문 <p>@username</p>만 붙는다.
```

문장 속 리터럴 `<p>`가 `_HTML_TAG_RE`에 걸려 `is_html()`이 `True` → `normalize_description`이 원문을 그대로 통과 → `\n`이 무시되고 `[라벨]`도 볼드 처리되지 않았다.

- `_HTML_TAG_RE`([doc_utils.py:98-101](../../../gdc_mcp/doc_utils.py#L98-L101))는 `p|br|ul|ol|li|div|span|strong|…` 태그 목록이고, **수정 전** `is_html`이 이를 **텍스트 아무 위치에서나** `search`했다.
- 이 한계는 수정 전 `normalize_description` docstring에 `주의: 평문에 리터럴 태그 문자열이 있으면 HTML로 오판할 수 있다(희귀)`로 이미 주석돼 있었으나, **희귀하지 않다** — 이 레포의 작업 상당수가 HTML 변환 자체를 다루므로 태스크 본문·댓글에 `<p>`·`<span>`이 일상적으로 등장한다.

### 템플릿 안내가 프롬프트 계층에만 있음

라벨 섹션 템플릿(`[요약]` → 선택·짝 `[AS-IS]`/`[TO-BE]` → `[작업 내용]`)은 다음에만 명시돼 있다.

- `task_from_doc` 도구 docstring([server.py:1257-1274](../../../gdc_mcp/server.py#L1257-L1274))
- 프롬프트 `gdc_task_new`([server.py:1830-1831](../../../gdc_mcp/server.py#L1830-L1831)) / `gdc_task_from_doc`([server.py:1848-1849](../../../gdc_mcp/server.py#L1848-L1849))
- 슬래시 커맨드 `commands/gdc-task-new.md` / `gdc-task-from-doc.md` / `gdc-doc-from-task.md`

반면 `create_task`·`update_task` docstring에는 언급이 없다. `/gdc-task-new`를 거치지 않고 도구를 직접 호출하는 경로(에이전트가 자연어 요청을 도구로 바로 매핑하는 경우 포함)에서는 규격 안내를 받지 못해 임의 라벨이 들어간다. 실제로 #417 최초 생성 시 `[배경]`/`[목표]`/`[변경 범위]`/`[참고]`라는 비규격 라벨이 사용됐다.

## 작업 결과

- [x] `is_html()` 판정을 **선두 앵커링**으로 변경([doc_utils.py:104-115](../../../gdc_mcp/doc_utils.py#L104-L115)) — `_HTML_TAG_RE.search(text)` → `_HTML_TAG_RE.match(text.lstrip())`(텍스트가 태그로 시작할 때만 HTML). 정규식 자체는 유지, `normalize_description` docstring의 '오판 가능(희귀)' 주의문도 새 규칙으로 교체
- [x] `create_task`([server.py:639-657](../../../gdc_mcp/server.py#L639-L657)) / `update_task`([server.py:769-776](../../../gdc_mcp/server.py#L769-L776)) docstring에 라벨 섹션 템플릿 규격 추가 — `[요약]`(필수) → `[AS-IS]`/`[TO-BE]`(선택·짝) → `[작업 내용]`(필수, `-` 블렛). 체크박스·프로세스 메타 단계(빌드/검증/테스트/커밋/버전 범프) 제외 원칙 함께 명시. `update_task`에는 '본문 통째 교체 → 부분 수정은 `edit_task_description`' 안내도 추가
- [x] `sync_doc_progress`([server.py:1149-1151](../../../gdc_mcp/server.py#L1149-L1151)) docstring의 `description` 설명에 동일 템플릿 규격 추가
- [x] `_apply_steps()`의 **③ 하위 태스크** 단계([server.py:1945-1947](../../../gdc_mcp/server.py#L1945-L1947))에 템플릿 준수 문구 추가 + 대응 커맨드 [commands/gdc-apply.md:15](../../../commands/gdc-apply.md#L15) 동일 반영. 문구는 `gdc-doc-from-task.md:15`의 기존 표현과 맞췄고, `/gdc-link-task`는 프롬프트가 같은 헬퍼를 공유 + 커맨드는 `/gdc-apply`에 위임하므로 자동 반영(중복 문구 없음 확인). 템플릿 출처 표기는 계층별로 분리 — `_apply_steps`는 프롬프트 전용 헬퍼이므로 **프롬프트 이름 `gdc_task_new`**(Desktop은 슬래시 커맨드 미지원, [server.py:1884](../../../gdc_mcp/server.py#L1884)와 동일 규칙), 커맨드 `.md`에만 `/gdc-task-new` 표기
- [x] pytest 3건 추가(`tests/test_description_html.py`) — 문장 중간 리터럴 태그가 **평문으로 변환·이스케이프**되는지, 선행 공백/개행이 있는 HTML은 통과하는지, `<span data-type=...>` 인용이 섞인 라벨 평문도 변환되는지. 추가 직후 2건 실패 확인 후 구현
- [x] 기존 결합 테스트(`test_is_html_matches_normalize_passthrough_rule`) 유지 확인 — 무수정 통과. 전체 **115 passed**(기존 112 + 신규 3), 회귀 0
- [x] 로컬 사전 검증 — WS3 / **45 이슈관리·46 WBS 양쪽**에서 리터럴 태그 섞인 평문으로 `create_task` → `<p><strong>요약</strong></p>…<ul>` 변환 + 태그 문자열 `&lt;p&gt;` 이스케이프 보존 확인, 태그로 시작하는 HTML은 `update_task`에서 이중 변환 없이 통과 확인. 임시 태스크 6건(15486·15487·15488·15489·15490·15491) 전부 삭제·잔존 0 확인, 컨텍스트 WS6/16 복원
- [x] `plugin.json` v0.6.3 범프 + `README.md` `create_task`/`update_task` 행에 템플릿 안내 반영 + `docs/INDEX.md` 이력 추가

## 참고 사항

### 선두 앵커링의 호환성

정상 경로의 HTML은 모두 태그로 시작하므로 통과 동작이 유지된다.

- `description_to_html` 산출물은 `<p>`/`<ul>` 블록으로 시작한다.
- `edit_task_description`이 다루는 서버 저장 본문(`cur["description"]`)도 GDC 에디터 산출물이라 블록 태그로 시작한다.

**리스크:** `설명 한 줄\n<p>진짜 HTML</p>`처럼 **평문이 앞에 붙은 HTML**을 넘기는 호출부가 있으면 그 입력은 이제 평문 취급되어 태그가 이스케이프된다. 확인 대상은 `normalize_description`을 실제로 경유하는 5곳뿐이다 — `create_task`([server.py:690](../../../gdc_mcp/server.py#L690)) / `update_task`([server.py:806](../../../gdc_mcp/server.py#L806)) / `sync_doc_progress`([server.py:1119](../../../gdc_mcp/server.py#L1119)) / `task_from_doc`([server.py:1302](../../../gdc_mcp/server.py#L1302)) / `_build_comment_html`([server.py:1400](../../../gdc_mcp/server.py#L1400)). `edit_task_description`은 위 전수 점검 표대로 `normalize_description`을 경유하지 않으므로 확인 대상이 아니다.

### 부수 영향 — `#N` 언급 해석

`is_html()`은 `_has_task_mentions`([server.py:60-62](../../../gdc_mcp/server.py#L60-L62))에서 "이미 HTML이면 `#N` 조회를 건너뛴다"는 판단에도 쓰인다. 앵커링 후에는 **문장 중간에 태그 문자열이 있고 `#N` 언급도 있는 평문**이 조회 대상에 포함된다 — 변환이 실제로 일어나는 입력이므로 **의도된 정합**이며, 해당 경우에만 목록 조회 1회가 추가된다.

### 범위 밖

- `_HTML_TAG_RE`의 태그 목록 확장/축소는 다루지 않는다(오판 원인은 검색 위치이지 태그 집합이 아니다).
- `format: "auto"|"text"|"html"` 같은 명시 파라미터 추가는 API 표면이 늘어 채택하지 않는다. 앵커링으로 오판이 남으면 그때 재검토한다.
- 이미 잘못 저장된 기존 태스크 본문의 일괄 보정은 하지 않는다(#417은 수기 재작성으로 처리 완료).

전수 점검에서 함께 드러난 **기존 불일치 2건**은 동작 변경을 수반하므로 이번 범위에 넣지 않고 별건으로 남긴다.

- **`append_work` 블렛에 자동 링크 미적용** — `normalize_description` 경로는 `#N` 태스크 언급·URL이 링크로 변환되지만(#409), `append_work_bullets`는 `html.escape`만 한다([doc_utils.py:272](../../../gdc_mcp/doc_utils.py#L272)). 같은 문장을 본문 생성으로 넣으면 링크, `/gdc-apply` 블렛 추가로 넣으면 평문이 되는 비대칭이 있다.
- **`_strip_meta_steps`가 `task_from_doc` 전용** — 유일 호출부가 [server.py:1301](../../../gdc_mcp/server.py#L1301)이라, `/gdc-apply` ③으로 만드는 하위 태스크에는 프로세스 메타 단계 코드 필터가 걸리지 않는다. 이번에는 docstring·절차 문구 안내로만 다루고, 코드 필터 확대는 별도 판단이 필요하다.

### 검증 컨텍스트

`.claude/rules/tasks.md`의 로컬 사전 검증 규칙에 따라 **테스트 워크스페이스 3([TEST] GDC 메인)** 에서 수행한다. 본 작업은 이슈/WBS 어느 도메인에도 특정되지 않는 공통 본문 변환이므로, **45 이슈관리 테스트와 46 WBS 테스트 양쪽**에서 각각 검증한다(사용자 지정).

검증 시나리오(프로젝트별 동일):

1. `set_context`로 대상 테스트 프로젝트로 전환.
2. 문장 중간에 리터럴 태그가 섞인 라벨 섹션 평문으로 `create_task` → 본문이 `<p><strong>요약</strong></p>…` 형태로 변환됐는지 확인(태그 문자열은 이스케이프되어 텍스트로 보존).
3. 태그로 시작하는 HTML을 `update_task`로 전달 → 이중 변환 없이 그대로 통과하는지 확인.
4. 검증 태스크 삭제 → 컨텍스트를 운영값(워크스페이스 6 / 프로젝트 16)으로 복원.
