# 작업 이력 인덱스

> 새 세션 시작 시 이 파일을 읽어 과거 작업 맥락을 파악합니다.
> 작업 완료 시 파일 맨 끝 `## 이력` 섹션 아래에 한 줄 추가합니다. (merge=union 전략 — conflict 없이 자동 병합되며, union은 항상 파일 끝에 누적하므로 이력 섹션을 파일 맨 끝에 둡니다)


## 유형 범례

- `feat` — 신규 기능
- `fix` — 버그 수정
- `refactor` — 리팩토링
- `ui` — UI/UX 개선
- `infra` — 인프라/설정
- `schema` — DB 스키마 변경

## 영역 범례

- `server/*` — 백엔드 (auth, api, convert, audit, workflow, license, ...)
- `ui/*` — 프론트엔드 (panel, content, admin, review, archive, collection, search, settings, i18n, ...)
- `db/*` — 데이터베이스 (schema, migration, ...)
- `infra/*` — 인프라 (docker, deploy, ...)


## 이력

<!-- 포맷: 날짜 | 유형 | 영역 | 상태 | 파일명 | 제목 -->
<!-- 예) 2026-03-27 | fix | server/auth | done | 2026-03/20260327-100000-auth-fix.md | 인증 토큰 만료 버그 수정  -->
<!-- 이 섹션은 항상 파일의 마지막 섹션이어야 합니다 (merge=union append 위치). 새 항목은 맨 아래에 추가하세요. -->
