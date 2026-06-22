---
description: 기존 태스크를 기존 작업 요청 문서와 연동
argument-hint: "<task_id> [doc_path]"
---

기존 태스크(ID $1)를 이미 있는 작업 요청 문서와 연동합니다(새로 만들지 않음). 문서: $2 (생략 시 현재 `docs/requests` 문서).

1. 문서 경로를 확정합니다($2 없으면 현재 열려 있거나 최근 다룬 `docs/requests/...md`).
2. `link_task_to_doc(doc_path, $1)`를 호출 → 문서 frontmatter에 `task_id`/`task_url` 기록.
3. 연동 결과(task_id, 제목, URL, 문서 경로)를 보고합니다. 진행률을 바로 맞추려면 `/gdc-sync`를 실행하세요.
