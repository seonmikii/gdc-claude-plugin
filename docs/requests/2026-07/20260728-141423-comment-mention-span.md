---
task_id: 15484
task_url: https://gdc.gemiso.com/tasks/15484
---

# 댓글 멘션을 하이라이트 span으로 삽입

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | server/gdc_mcp |
| 날짜 | 2026-07-28 |
| 상태 | done |
| 관련 | 태스크 #417, server.py, tests/test_validation.py |

## 요청 내용

`add_task_comment` / `update_task_comment`의 `mentions` 인자로 멘션을 넣을 때, 현재는 본문 선두에 **평문** `<p>@username</p>`으로만 붙는다. 이를 GDC 프론트 에디터가 생성하는 것과 동일한 **멘션 span 노드**로 삽입해, 저장된 댓글에서 멘션이 하이라이트(볼드·강조색)로 렌더되도록 개선한다.

## 배경

- 현재 `_build_comment_html`(`gdc_mcp/server.py:1394-1404`)이 `prefix = " ".join(f"@{u}" ...)` → `<p>{prefix}</p>` 형태로 **평문**을 붙인다.
- gdc-service 백엔드 알림 매칭(`backend/tasks/serializers.py:273-279`)은 본문 텍스트의 `@뒤 토큰`을 `username` 컬럼과 대조하므로, **평문 `@username`도 알림 자체는 정상 발송**된다.
- 그러나 프론트 뷰어/에디터는 `span[data-type="mention"]` 노드일 때만 멘션으로 재인식한다(`frontend/src/components/common/RichTextEditor/extensions/UserMention.ts`). 평문은 그냥 텍스트로 보여, 사용자 입장에서 "멘션이 안 걸린 것"처럼 보인다.
- 렌더 형태는 **배경 pill(chip)이 아니라 볼드+강조색 텍스트**다 — `.tiptap-editor .tiptap .mention` / `.tiptap-viewer .tiptap .mention` = `font-weight:600; color:var(--primary)` (`frontend/src/index.css:329-333`). 배경 chip은 `tag-mention`(태그) 쪽 스타일이다.
- 뷰어(NodeView)는 `@{data-label}`(full_name)로 표시하고, 저장 HTML의 텍스트는 `@{data-id}`(username)로 유지된다 — 표시와 알림 파싱이 분리된 구조.
- 실제 재현: 태스크 #386(15376)에 MCP로 멘션 등록 시 `@ghkr53@gmail.com`(해당 계정은 로그인 아이디가 이메일)이 평문으로 들어가 chip이 없었음. username 자체는 MCP가 정확히 해석했고(알림은 발송됨), 부족한 것은 **span 래핑**뿐이었다.

프론트가 생성하는 멘션 HTML 구조(목표 형태):
```html
<p><span data-type="mention" class="mention" data-id="{username}" data-label="{full_name}">@{username}</span> …</p>
```
- `data-id` = username, `data-label` = full_name(표시용), span 내부 텍스트 = `@{username}`.
- 멘션 span은 **인라인 노드**이므로 반드시 `<p>` 블록 안에 넣는다(현행 `<p>{prefix}</p>` 래핑 유지). 최상위 bare span으로 두면 재편집 시 문단 구조가 어긋난다.
- `class="mention"`은 프론트 `UserMention.configure({HTMLAttributes:{class:'mention'}})` 산출과 동일하게 넣는다 — CSS 강조가 이 클래스에 걸려 있다.
- 백엔드 알림 매칭은 `Mention.create`/`update`에서 `re.findall(r"@([\w.@+-]+)", content)`를 **원문 HTML**에 적용하므로(`backend/tasks/serializers.py:274`), span 내부 텍스트 `@{username}`으로 그대로 매칭된다 → 알림 호환.
- **속성 순서가 웹훅 평문에 영향(고정 필요)**: 웹훅/알림 평문 변환 `_tiptap_to_plain`(`backend/tasks/signals.py:14-19`)은 `<span[^>]*data-type="mention"[^>]*data-label="([^"]*)"…`로 파싱하므로, **`data-type`이 `data-label`보다 앞**이고 **쌍따옴표**여야 평문이 `@{full_name}`이 된다. 순서가 어긋나면 span 태그가 일반 제거되어 `@{username}`으로 열화(기능 파손은 아니나 표시 품질 하락). 목표 형태는 이 조건을 만족하므로 **테스트에서 속성 순서를 단언해 고정**한다. `html.escape(quote=True)`가 만드는 `&quot;`는 리터럴 `"`가 아니므로 `[^"]*` 캡처를 깨지 않는다.
- 프론트 파서 사양 재확인(`@tiptap/extension-mention@3.20`): 기본 `parseHTML`이 `span[data-type="mention"]`, 속성은 `data-id`→`id` / `data-label`→`label`. 뷰어(`RichTextViewer.tsx` `MentionViewer`)는 `@{label ?? id}`를 `class="mention"`으로 렌더 → 목표 형태와 일치.
- **태그 동기화 부작용 없음**: 댓글 저장 시 호출되는 `sync_task_tags_from_content`의 `_TAG_MENTION_RE`는 `data-type="tagMention"`을 요구하므로(`serializers.py:88-90`), user mention span은 매칭되지 않는다(`data-id`가 비숫자여도 `int()` 오류 없음).
- **v0.6.3 `is_html` 선두 앵커링과 무충돌**: 멘션 prefix는 `normalize_description` **이후** 결합되므로 본문 판별에 영향이 없고, `_HTML_TAG_RE`에는 `span`이 포함돼 있어 span으로 시작하는 HTML 재입력도 통과 처리된다.

## 작업 결과

- [x] `_resolve_mention_usernames`(`server.py:1352-1391`)가 username뿐 아니라 **full_name도 함께** 반환하도록 확장 (`(username, full_name)` 쌍 리스트). full_name이 비면 **username으로 대체**(프론트의 "label 없는 과거 데이터" 처리와 동일). **`by_id`·`by_name` 두 맵 모두** 쌍을 담아야 한다(user id 멘션 경로는 `by_id`(`server.py:1372`)를 타므로 `by_name`만 고치면 id 경로에서 label 유실). 두 호출부(`add_task_comment` `server.py:1454`, `update_task_comment` `server.py:1483`) 시그니처 정리
- [x] `_build_comment_html`(`server.py:1394-1404`)의 prefix 생성을 평문 → 멘션 span으로 교체(`<p>` 문단 래핑 유지). `data-label`(full_name)·`data-id`는 **`html.escape(..., quote=True)`** 로 속성 이스케이프(full_name에 괄호·`&`·따옴표 포함 가능), span 내부 텍스트도 escape. 속성 순서는 `data-type` → `class` → `data-id` → `data-label` 고정(웹훅 평문 정규식 호환, 참고 사항 참조)
- [x] 테스트 갱신(`tests/test_validation.py:204-246`): 기존 `_resolve_mention_usernames`(반환 타입 `list[str]` → 쌍 리스트) / `_build_comment_html`(평문 prefix 단언) 테스트를 새 스펙으로 수정 + 회귀 추가 — 멘션 span 구조(data-type/class/data-id/data-label/`@username` 텍스트), **속성 순서(`data-type`이 `data-label`보다 앞)**, **full_name 없는 멤버 → `data-label`=username 폴백**(현 `PROJECT` 픽스처는 두 멤버 모두 full_name 보유 → 폴백 미검증 상태), full_name 특수문자 escape, `#N` 태스크 언급 자동 링크 공존
- [x] 도구 스펙(docstring) 갱신: `add_task_comment`(`server.py:1445` "`@user1 @user2` 한 줄") · `update_task_comment` · `_build_comment_html`(`server.py:1395-1399`) · 댓글 섹션 모듈 주석(`server.py:1347-1349`)의 "평문 멘션" 서술을 하이라이트 span 기준으로 수정 — docstring은 LLM이 보는 도구 스펙이므로 README보다 우선
- [x] 실서버 라운드트립: 테스트 컨텍스트(워크스페이스 3 / 프로젝트 45)에서 멘션 등록 → 하이라이트 렌더 + 알림 발송 동시 확인, 임시 데이터 삭제 및 컨텍스트 **WS6/16으로 복원**
- [x] `README.md:145`(`add_task_comment` 행) 설명 갱신 + `plugin.json` 버전 **0.6.3 → 0.6.4**(기존 도구 내 동작 개선) + `docs/INDEX.md` 이력 한 줄 추가

## 로컬 사전 검증

테스트 컨텍스트 WS3(‘[TEST] GDC 메인’)/프로젝트 45(‘이슈관리 테스트’)에서 실행. 실행 세션 MCP 서버는 구버전(v0.6.3)이라 **업데이트된 로컬 코드를 직접 호출**(`uv run python`, shim 미사용)해 검증했다.

- [x] **pytest** — 119 passed(기존 115 + 신규 4). 구현 전 신규/수정 테스트 9건 실패 확인 후 구현(TDD).
- [x] **저장 라운드트립**(임시 태스크 #15492, 댓글 42674) — 전송 HTML과 서버 저장본이 **바이트 단위 동일**(서버 sanitize·속성 재정렬 없음). 8개 단언 모두 PASS: `data-type="mention"`·`class="mention"`·`data-id`(username)·`data-label`(full_name)·span 텍스트 `@username`·**속성 순서(type<label)**·`<p>` 문단 래핑·본문 문단 보존.
- [x] **알림 호환** — 응답 필드는 `mentioned_users`가 아니라 **`mentioned_users_detail`**(`MentionSerializer`). 임시 태스크 2건차에서 `[{id:46, username:'seonmiki98@gmail.com'}]` **1명만** 설정 → 이메일 username의 `@gmail.com` 추가 캡처가 무해하다는 문서 주장 실증(중복·오탐 없음). user id 경로(`by_id`) 해석도 `('seonmiki98@gmail.com','김선민')`로 정상.
- [x] **수정 경로** — PATCH 후에도 span 유지, 본문만 교체됨(`#999` 미해결 언급은 평문 유지).
- [x] **평문 변환 회귀** — `html_to_text`가 span을 일반 제거해 `@seonmiki98@gmail.com\n본문` 반환 → `list_task_comments` 출력 형태 기존과 동일.
- [x] **정리** — 임시 댓글 2건·태스크 2건(#15492, 알림 확인용 1건) 삭제, `[임시검증]` 잔존 0건 확인, 컨텍스트 WS6/16(GDC-Support)로 복원.

## 참고 사항

- **변경 범위:** `gdc_mcp/server.py`만 수정(플러그인 클라이언트). gdc-service(서버)·프론트는 무변경.
- **이메일 username 캡처 주의:** `data-id="ghkr53@gmail.com"`처럼 username에 `@`가 있으면, 백엔드 정규식 `@([\w.@+-]+)`이 attribute 값 내부의 `@gmail.com`에서 `gmail.com`도 캡처한다. 이는 어떤 username과도 일치하지 않아 **무해**(추가 알림 없음)하나, 문서에 남긴다. 정식 매칭은 span 텍스트 `@{username}`이 담당.
- **수정 경로도 동일**: `MentionSerializer.update`가 content 변경 시 같은 정규식으로 재파싱하고 **신규 멘션 델타에만** 알림을 보낸다(`serializers.py:354-367`). 따라서 평문→span 전환으로 이미 멘션된 사용자에게 중복 알림이 가지 않는다.
- 멘션은 기존과 동일하게 **본문 선두 한 문단**에만 배치(중간 커서 삽입 미지원).
- **라운드트립 중복 표시(기존 동작 유지)**: `list_task_comments`는 HTML을 벗긴 평문(`@username …`)을 반환하므로, 그 평문을 그대로 `update_task_comment(content=..., mentions=[...])`로 되돌리면 선두 span과 본문 속 평문 `@username`이 함께 남아 두 번 보인다. 현행 평문 prefix에서도 동일한 비대칭이지만 span 도입 후에는 강조 렌더 때문에 눈에 더 띈다 — 이번 범위에서 다루지 않고(호출 측 사용 패턴 문제) 문서에만 남긴다.
- 대안(범위 밖): 백엔드가 attribute(`data-id`) 기반으로 멘션을 파싱하도록 바꾸는 방법도 있으나, gdc-service 서버 변경이 필요하고 기존 평문 호환을 깨므로 채택하지 않음.
