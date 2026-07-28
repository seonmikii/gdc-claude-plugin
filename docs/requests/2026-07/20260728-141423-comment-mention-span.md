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
| 상태 | partial |
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

## 작업 결과

- [ ] `_resolve_mention_usernames`(`server.py:1352-1391`)가 username뿐 아니라 **full_name도 함께** 반환하도록 확장 (`(username, full_name)` 쌍 리스트). full_name이 비면 **username으로 대체**(프론트의 "label 없는 과거 데이터" 처리와 동일). 두 호출부(`add_task_comment` `server.py:1454`, `update_task_comment` `server.py:1483`) 시그니처 정리
- [ ] `_build_comment_html`(`server.py:1394-1404`)의 prefix 생성을 평문 → 멘션 span으로 교체(`<p>` 문단 래핑 유지). `data-label`(full_name)·`data-id`는 **`html.escape(..., quote=True)`** 로 속성 이스케이프(full_name에 괄호·`&`·따옴표 포함 가능), span 내부 텍스트도 escape
- [ ] 테스트 갱신(`tests/test_validation.py:204-246`): 기존 `_resolve_mention_usernames`(반환 타입 `list[str]` → 쌍 리스트) / `_build_comment_html`(평문 prefix 단언) 테스트를 새 스펙으로 수정 + 멘션 span 구조(data-type/data-id/data-label/`@username` 텍스트)·`#N` 태스크 언급 자동 링크 공존 회귀 추가
- [ ] 실서버 라운드트립: 테스트 컨텍스트(워크스페이스 3 / 프로젝트 45)에서 멘션 등록 → 하이라이트 렌더 + 알림 발송 동시 확인, 임시 데이터 삭제 및 컨텍스트 원복
- [ ] `README.md:145`(`add_task_comment` 행) 설명 갱신 + `plugin.json` 버전 범프 + `docs/INDEX.md` 이력 한 줄 추가

## 참고 사항

- **변경 범위:** `gdc_mcp/server.py`만 수정(플러그인 클라이언트). gdc-service(서버)·프론트는 무변경.
- **이메일 username 캡처 주의:** `data-id="ghkr53@gmail.com"`처럼 username에 `@`가 있으면, 백엔드 정규식 `@([\w.@+-]+)`이 attribute 값 내부의 `@gmail.com`에서 `gmail.com`도 캡처한다. 이는 어떤 username과도 일치하지 않아 **무해**(추가 알림 없음)하나, 문서에 남긴다. 정식 매칭은 span 텍스트 `@{username}`이 담당.
- **수정 경로도 동일**: `MentionSerializer.update`가 content 변경 시 같은 정규식으로 재파싱하고 **신규 멘션 델타에만** 알림을 보낸다(`serializers.py:354-367`). 따라서 평문→span 전환으로 이미 멘션된 사용자에게 중복 알림이 가지 않는다.
- 멘션은 기존과 동일하게 **본문 선두 한 문단**에만 배치(중간 커서 삽입 미지원).
- **라운드트립 중복 표시(기존 동작 유지)**: `list_task_comments`는 HTML을 벗긴 평문(`@username …`)을 반환하므로, 그 평문을 그대로 `update_task_comment(content=..., mentions=[...])`로 되돌리면 선두 span과 본문 속 평문 `@username`이 함께 남아 두 번 보인다. 현행 평문 prefix에서도 동일한 비대칭이지만 span 도입 후에는 강조 렌더 때문에 눈에 더 띈다 — 이번 범위에서 다루지 않고(호출 측 사용 패턴 문제) 문서에만 남긴다.
- 대안(범위 밖): 백엔드가 attribute(`data-id`) 기반으로 멘션을 파싱하도록 바꾸는 방법도 있으나, gdc-service 서버 변경이 필요하고 기존 평문 호환을 깨므로 채택하지 않음.
