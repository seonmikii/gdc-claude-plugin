# list_customers 도구 추가 (고객사 목록 조회)

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | server/api |
| 날짜 | 2026-07-20 |
| 상태 | 구현 완료 (실사용 검증 대기 — 플러그인 재설치 후 확인) |
| 관련 | server, tokens |

## 요청 내용

`create_task`/`update_task`에서 `customer`를 이름으로 지정할 수 있게 됐으나, 고객사 **목록을 미리 조회하는 도구가 없어** 사용자가 정확한 이름을 모르면 웹 UI를 봐야 함. 현재 컨텍스트 워크스페이스의 고객사 목록을 반환하는 `list_customers`를 추가한다.

## 배경

- 기존 도구엔 `list_workspaces`/`list_projects`/`get_project_enums`(members)는 있으나 고객사 조회 수단 없음.
- 고객사 이름 해석은 `_resolve_customer` 내부 헬퍼로만 존재 — 모호/미존재 시 에러 메시지로만 후보 노출(사후적).
- 서버 목록 API: `GET /api/customers/customers/?workspace=<ws>&search=<opt>` (페이지네이션 `results`).
  - `CustomerListSerializer` 필드에 `id, name, primary_contact_name` 등 포함.
  - 권한(can_view_customers/OWNER) 없는 워크스페이스는 403이 아니라 **빈 결과**로 필터됨.

## 수행 계획

- [x] 1. `list_customers(search: str | None = None)` 도구 추가
  - 워크스페이스는 현재 레포 컨텍스트(`tokens.py`)에서 획득 — 없으면 안내 ValueError
  - `client.py` 경유로 `_CUSTOMERS` 조회, `id`·`name`·`primary_contact_name` 반환
  - 권한 없음/빈 결과 시 `count=0`와 함께 "미존재 또는 열람 권한 없음" 힌트 포함
  - docstring: customer 이름 지정 전 목록 확인 용도임을 명시
- [x] 2. `.claude-plugin/plugin.json` version 올리기 (0.2.0 → 0.2.1)
- [x] 3. `docs/INDEX.md` 이력 한 줄 추가

## 참고 사항

- 변경 파일: `gdc_mcp/server.py`, `.claude-plugin/plugin.json`, `docs/INDEX.md`
- gdc-service 본체 수정 없음.
- 슬래시 커맨드/프롬프트는 이번 범위 제외(조회 보조 도구 — 자연어 호출로 충분). 필요 시 후속.
