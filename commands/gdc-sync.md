---
description: 문서 진행률을 연결된 태스크에 강제 동기화
argument-hint: "[path]"
---

`sync_doc_progress` 도구로 문서의 진행률을 연결된 태스크에 동기화하세요. 경로: $1 (생략 시 현재 `docs/requests` 문서).

이 커맨드는 **진행률·상태·실제 날짜 동기화 전용**입니다. 본문(description)에 추가 작업/내용 변경을 반영하려면 `sync_doc_progress`의 `description`으로 통째 넘기지 말고(본문 통째 교체는 인라인 이미지가 유실됨), `/gdc-reflect`로 최소 편집하세요.

동기화 후 progress(%)와 상태 전이(진행/완료), 실제 시작/종료일을 보고하세요.
