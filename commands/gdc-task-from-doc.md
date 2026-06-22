---
description: 작업 요청 문서로 태스크 생성
argument-hint: "<path>"
---

지정한 작업 요청 문서로 태스크를 생성합니다. 경로: $1 (생략 시 현재 작업 중인 `docs/requests` 문서).

1. **description**을 템플릿에 맞춰 작성: 첫 줄 = 문서 "요청 내용" 한 줄 요약, 다음 줄에 `[작업 내용]` 후 "작업 결과" 단계별 한 줄 요약.
2. `task_from_doc` 도구를 호출합니다. project는 현재 레포 컨텍스트(`/gdc-login` 저장값)에서 자동 결정됩니다.
   - 메타데이터 표의 `상태` 자동 매핑: **done → '완료'**, **partial → '진행'**.
3. 생성 결과(task_id / URL)와 문서 frontmatter 갱신 여부를 보고합니다.
