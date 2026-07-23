---
description: 문서 변경을 태스크 본문/댓글/하위 태스크에 반영 (분류→질문→라우팅)
argument-hint: "[path]"
---

작업 요청 문서의 변경을 연결된 태스크에 반영합니다. 경로: $1 (생략 시 현재 `docs/requests` 문서).

본문은 통째로 덮어쓰지 않습니다(인라인 이미지 유실 방지) — 아래 절차로 최소 편집/댓글/하위 태스크로 라우팅하세요.

1. 문서 frontmatter의 `task_id` 확인(없으면 `/gdc-link-task`·`/gdc-login` 안내). `get_task`로 현재 본문(description)을 가져옵니다.
2. 문서(요청 내용 / `## 작업 결과`)와 현재 본문을 비교해 **추가 작업**인지 **기존 내용 변경**인지 분류합니다.
3. **추가 작업**이면 `AskUserQuestion`으로 반영 위치를 묻습니다:
   - ① 본문 append — `edit_task_description(task_id, mode='append_work', bullets=[...])`로 `[작업 내용]`에 블렛 추가.
   - ② 댓글 — `add_task_comment`에 `[추가 (YYYY-MM-DD)]` 라벨 + 블렛.
   - ③ 하위 태스크 — `create_task(parent=task_id, ...)`.
4. **내용 변경**이면 `AskUserQuestion`으로 묻습니다:
   - ① 본문만 최신화 — `edit_task_description(task_id, mode='replace_section', label='<라벨>', new_body_html='<본문HTML>')`로 해당 라벨 섹션만 교체.
   - ② 댓글만 — `add_task_comment`에 `[변경 (YYYY-MM-DD)]` + 변경 이유 + 전/후(본문 유지).
   - ③ 둘 다 — 본문 교체 + 변경이력 댓글.
   - 변경 이유는 문서 diff·맥락에서 초안을 만들고 사용자가 수정하게 합니다.
5. `replace_section` 대상 섹션에 인라인 이미지가 있으면 도구가 경고합니다 — 유지(기본)/삭제를 사용자에게 확인하고 `keep_media`로 반영하세요.
6. `new_body_html`은 GDC 리치텍스트 형식(`<p>...</p>`, `<ul><li><p>...</p></li></ul>`)으로 작성합니다(라벨 문단 `<p><strong>라벨</strong></p>`은 도구가 유지).
7. 반영 결과(모드·대상·URL, 이미지 경고 있으면 함께)를 보고합니다. 진행률·상태·날짜 동기화는 `/gdc-sync`가 담당합니다.
