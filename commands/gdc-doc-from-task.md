---
description: 태스크 기반으로 작업 요청 문서 생성·연동
argument-hint: "<task_id>"
---

기존 태스크를 기반으로 작업 요청 문서(`docs/requests/...`)를 생성하고 그 태스크와 연동합니다. 태스크 ID: $1

1. `get_task($1)`로 상세(제목/내용/상태+category/우선순위/유형/날짜/진행률/URL)를 가져오고, **함께 `list_task_comments($1)`로 댓글(멘션)도 조회**합니다. 댓글에 요구사항·의사결정 맥락이 담긴 경우가 많습니다(특히 description이 빈 태스크). 댓글이 0개면 기존과 동일하게 description 기반으로만 진행합니다. `count`가 20을 넘으면 최신 20개만 조회됨을 문서에 언급합니다.
2. **태스크 description을 그대로 옮기지 말 것.** 다음 순서로 작성합니다: ①관련 코드 검토(태스크 내용에 해당하는 실제 코드/파일을 읽어 현황 파악) → ②기획 정리(요구사항·배경 명확화 — **description과 댓글 내용을 통합**하고, 둘이 상충하면 그 사실을 문서에 드러냄) → ③개발 계획 수립(단계별 작업 항목) → ④문서 반영.
3. `docs/requests/TEMPLATE.md` 형식으로 작성: 제목=태스크 제목, 메타표(날짜=오늘, 상태=`status_category` 매핑 done→done·in_progress→partial·그 외→partial, 유형/영역은 합리적으로), 요청 내용=②기획 정리 결과, 작업 결과=③개발 계획 체크리스트.
   - 문서 맨 위 frontmatter에 `task_id: $1`, `task_url: <url>`을 기록해 **태스크와 연동**합니다.
4. 경로: `docs/requests/YYYY-MM/YYYYMMDD-HHmmss-<짧은-설명>.md` (타임스탬프는 `date` 명령).
5. `docs/INDEX.md` `## 이력`에 한 줄 추가. 6. 생성 경로와 task_id/URL을 보고합니다.

※ 이 요청으로 (하위)태스크를 **함께 생성**하는 경우, 태스크 description은 평문 한 문단으로 넣지 말고 `/gdc-task-new`의 **라벨 섹션 템플릿(평문)**을 따른다: `[요약]` 한두 줄 → (선택·짝) `[AS-IS]`/`[TO-BE]` → `[작업 내용]` 아래 `-` 블렛(각 한 줄). `create_task`가 이를 GDC 리치텍스트(HTML)로 변환한다.
