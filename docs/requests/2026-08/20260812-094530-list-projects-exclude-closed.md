---
task_id: 15783
task_url: https://gdc.gemiso.com/tasks/15783
---
# [GDC 로그인] 프로젝트 목록에 종료된 프로젝트 제외

| 속성 | 값 |
|------|-----|
| 유형 | fix |
| 영역 | server/gdc_mcp |
| 날짜 | 2026-08-12 |
| 상태 | done — 플러그인·gdc-service 양쪽 구현·검증 완료 |
| 관련 | gdc_mcp/server.py, README.md, site/index.html, .claude-plugin/plugin.json |

## 요청 내용

프로젝트 선택 목록에 **종료 선언된 프로젝트가 섞여 나오지 않게** 한다. 종료된 프로젝트는 더 이상 작업 대상이 아니므로 선택지에 올라올 이유가 없고, 이름이 비슷한 진행 프로젝트와 헷갈릴 여지만 만든다.

태스크(#479)는 description·댓글이 모두 비어 있어(`mention_count=0`) 제목만으로 범위를 잡았고, 코드 검토 후 아래와 같이 확정했다.

### 범위 — 이 레포는 `list_projects`만

제목의 "GDC 로그인" 화면(브라우저 핸드오프 `/mcp-auth`)의 프로젝트 드롭다운은 **gdc-service 프론트엔드**가 그린다(`frontend/src/pages/MCPAuthPage.tsx:64-66`). 이 레포는 클라이언트 브리지이므로 gdc-service 본체를 수정하지 않는다(Golden Rule). 따라서:

- **이 레포에서 구현**: MCP 도구 `list_projects` — 같은 목록 API를 호출하면서 종료 필터를 걸지 않고 있다.
- **별건 이관**: gdc-service `MCPAuthPage`의 드롭다운. 이 문서에는 참고 사항으로만 남기고 gdc-service 레포에서 별도 처리한다.

### 동작 — 무조건 제외

옵션(`include_closed` 같은 플래그) 없이 종료 프로젝트를 목록에서 뺀다. 목록에서 빠져도 `set_context(workspace_id, project_id)`는 id를 직접 받으므로, 종료 프로젝트로 돌아가야 하는 예외 상황이 막히지는 않는다.

## 배경 (현황 분석)

### 현재 코드

[gdc_mcp/server.py:249-253](../../../gdc_mcp/server.py#L249-L253):

```python
@mcp.tool
def list_projects(workspace_id: int) -> dict:
    """지정 워크스페이스의 프로젝트 목록(전환용)."""
    data = client.get("/api/projects/", params={"workspace": workspace_id, "page_size": 100}).json()
```

`closed` 파라미터가 없다. 서버 기본값이 "전체 반환"이므로 종료 프로젝트가 그대로 내려온다.

### 서버 계약 (gdc-service, 읽기만 함)

- 종료 판정은 **`closed_at is not null`** 하나로 통일돼 있다 — WBS·이슈관리 프리셋 공통(`backend/projects/models.py:94-97`, `Project.is_closed`). 과거 `status=completed/cancelled`였던 것도 마이그레이션 `0018`에서 `closed_at`으로 이관됐다.
- 목록 API가 이미 필터를 지원한다(`backend/projects/views.py:257-264`):

  | `closed` | 결과 |
  |---|---|
  | `true` | 종료된 것만 |
  | `false` | 종료 안 된 것만 |
  | 없음/기타 | 전체 (현재 동작) |

  이 필터는 `self.action == "list"` 안에서만 적용된다 → **상세 조회(`/api/projects/{id}/`)에는 영향이 없다.** `get_context`/`set_context`가 쓰는 `_project(project_id)`는 상세 조회라 종료 프로젝트여도 이름을 정상적으로 읽는다.
- 목록은 이미 `deleted_at`(삭제)·`is_archived`(숨김)를 기본 제외한다. `closed`만 빠져 있던 셈이라, 필터를 거는 쪽이 기존 규약과 일관된다.

### 영향 범위

`list_projects`를 쓰는 곳은 프로젝트 전환 흐름 두 개다 — 둘 다 "지금 작업할 프로젝트를 고른다"는 목적이라 종료 프로젝트가 후보에 있을 이유가 없다.

- `commands/gdc-switch.md:9` (`/gdc-switch`)
- `server.py:2522` (`gdc_switch` 프롬프트, Desktop용)

## 개발 계획

### 1단계 — 구현

- [x] `list_projects`의 요청 파라미터에 `"closed": "false"` 추가 (`server.py:249`)
- [x] docstring에 종료 제외 규칙 + 우회 경로(`set_context`에 id 직접 지정) 명시

### 2단계 — 로컬 사전 검증 (WS3 `[TEST] GDC 메인`)

- [x] 검증 대상 확보 — 워크스페이스별 `closed` 필터 실측: WS3 전체 7 / 진행중 6 / 종료 1(id=10 `헬스케어 데이터 분석 플랫폼`, `closed_at` 2026-02-19). 임시 데이터를 만들 필요 없이 기존 종료 프로젝트로 검증 가능
- [x] 갱신된 `list_projects(3)` 로컬 코드 직접 호출(세션 MCP 서버는 구버전이라 `uv run python`) → 6건 `[14, 7, 8, 45, 6, 46]`, 종료 id=10 **미포함**
- [x] 상세 조회 경로 무영향 확인 — `_project(10)`이 이름·`closed_at`을 정상 반환(필터가 `action=="list"`에만 걸림) → 종료 프로젝트로도 `set_context`/`get_context` 가능
- [x] 원복 불필요 — 읽기 전용 호출만 했고 임시 데이터 생성·컨텍스트 변경 없음(운영 컨텍스트 WS6/16 그대로)
- [x] pytest 회귀 — `207 passed` (신규 케이스 없음: 파라미터 한 줄이라 분리할 순수 로직 없음)

### 3단계 — 문서·배포

- [x] `README.md:123` 도구표에 "(종료된 프로젝트 제외)" 명시
- [x] `site/index.html:1967` 도구표 같은 행 갱신(한글 본문 + `data-en` 양쪽)
- [x] `.claude-plugin/plugin.json` version `0.8.0` → `0.8.1`, 안내서의 버전 표기 2곳(재현 화면 표·푸터)도 동기화
- [x] `docs/INDEX.md` `## 이력` 갱신

### 4단계 — gdc-service 이관 (이 레포 밖, 별도 진행)

- [x] gdc-service 레포에 작업 요청 문서 작성 — `docs/requests/2026-08/20260812-095356-mcp-auth-exclude-closed-projects.md`
- [x] `MCPAuthPage.tsx:65`에 `closed: 'false'` 추가 — gdc-service 레포 `fix/gdc-479-mcp-auth-exclude-closed-projects` 브랜치 `f59c7e4`. 브라우저 실증으로 워크스페이스 2곳(진행중 3/종료 1, 진행중 9/종료 3)에서 종료 프로젝트 미노출·전환 시에도 `closed=false` 유지 확인, tsc·lint 신규 0. 후보 1개일 때의 자동 선택만 해당 데이터가 없어 미실증(이번 변경에서 손대지 않은 기존 로직)

## 참고 사항

- **테스트**: 이번 변경은 파라미터 한 줄 추가라 분리할 순수 로직이 없다. pytest 신규 케이스 없이 위 로컬 사전 검증으로 갈음한다(억지로 헬퍼를 뽑아내지 않는다).
- **별건 이관 — gdc-service 로그인 화면**: `MCPAuthPage.tsx`의 `projectsApi.list({ workspace, page_size: 100 })`에도 `closed: 'false'`가 필요하다. `projectsApi.list`는 `Record<string, string | number | undefined>`를 그대로 넘기므로 타입 변경 없이 인자만 추가하면 된다(`frontend/src/services/projects.ts:32-33`). 작업 요청 문서는 gdc-service 레포에 작성해뒀고(`docs/requests/2026-08/20260812-095356-mcp-auth-exclude-closed-projects.md`), 조사 중 **프로젝트를 고르게 하는 다른 화면 5곳은 이미 종료 프로젝트를 제외하고 있고 MCP 인증 화면만 누락**임을 확인했다. **이 레포에서는 수정하지 않는다.**
- 이 태스크의 상위는 #292 「MCP 서버 기능 개선」(태스크 14957)이다.
