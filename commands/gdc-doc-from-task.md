---
description: 태스크 기반으로 작업 요청 문서 생성·연동
argument-hint: "<task_id>"
---

기존 태스크를 기반으로 작업 요청 문서(`docs/requests/...`)를 생성하고 그 태스크와 연동합니다. 태스크 ID: $1

1. `get_task($1)`로 상세(제목/내용/상태+category/우선순위/유형/날짜/진행률/URL)를 가져옵니다.
2. `docs/requests/TEMPLATE.md` 형식으로 작성: 제목=태스크 제목, 메타표(날짜=오늘, 상태=`status_category` 매핑 done→done·in_progress→partial·그 외→partial, 유형/영역은 합리적으로), 요청 내용=description 정리, 작업 결과=진행 체크리스트.
   - 문서 맨 위 frontmatter에 `task_id: $1`, `task_url: <url>`을 기록해 **태스크와 연동**합니다.
3. 경로: `docs/requests/YYYY-MM/YYYYMMDD-HHmmss-<짧은-설명>.md` (타임스탬프는 `date` 명령).
4. `docs/INDEX.md` `## 이력`에 한 줄 추가. 5. 생성 경로와 task_id/URL을 보고합니다.
