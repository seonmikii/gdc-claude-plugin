# AGENTS.md

gdc-claude-plugin 작업 시 에이전트가 따르는 관제탑 규칙. 상세 규칙은 References의 위임 파일을 참조한다.

## Operational Commands

- 의존성 동기화: `uv sync`
- 의존성 추가: `uv add <패키지>` (직접 `pip install` 금지)
- MCP 서버 단독 기동: `uv run --directory <플러그인 루트> gdc-mcp`
- 엔트리포인트: `gdc-mcp = gdc_mcp.server:main`
- 패키지 관리는 **uv 고정** (npm/pip/poetry 사용 금지)
- 자동화 테스트 없음 — 변경 검증은 MCP Inspector 또는 도구 직접 호출(자연어/프롬프트)로 수동 수행한다. 없는 테스트 명령을 지어내지 않는다.

## Golden Rules

### Immutable (절대 타협 불가)

- **gdc-service 본체(`../gdc/gdc-service`)를 이 레포에서 수정하지 않는다.** 서버 동작 변경이 필요하면 사용자에게 알리고 별도 처리한다. 이 레포는 클라이언트 브리지다.
- **인증은 브라우저 핸드오프 전용.** username/password 자동 로그인 변수를 추가하지 않는다.
- **토큰·시크릿을 커밋·로그·도구 응답에 노출하지 않는다.** 저장 파일(`~/.gdc-mcp/credentials.json`)·메모리로만 다룬다.
- 인증 콜백은 `127.0.0.1` loopback + 1회용 state로 한정한다.

### Do's & Don'ts

- 데이터 조회/생성 시 현재 레포에 저장된 **워크스페이스/프로젝트 컨텍스트(`tokens.py`)를 항상 적용**한다. 컨텍스트가 없으면 `gdc_login`/`set_context`로 안내한다.
- gdc-service REST 호출은 **반드시 `client.py`를 경유**한다. 직접 httpx 호출을 도구 코드에 흩뿌리지 않는다.
- 입력 검증(날짜 순서·미래 종료일 차단·멤버 소속 확인 등)은 **도구 레벨**에서 수행한다.
- 새 도구/프롬프트는 `server.py`에 FastMCP 데코레이터로 등록하고, 자연어 호출이 가능하도록 **구체적 docstring/파라미터 설명**을 작성한다.
- 슬래시 커맨드(`/gdc-*`)와 MCP 프롬프트는 **1:1 대응을 유지**한다 (Desktop은 슬래시 미지원 → 프롬프트로 동일 기능 제공).
- 불필요한 REST 왕복을 줄인다 — 목록은 조회 후 재사용, enum/멤버 메타는 한 번에 받아 재활용한다.

## Project Context

Claude Code/Desktop에서 GDC(gdc-service) REST API에 붙는 MCP 클라이언트 플러그인. 태스크 조회/생성/수정, 작업 요청 문서 연동, 진행률 자동 동기화를 제공한다.

Tech Stack: Python 3.13+, uv, fastmcp(>=2.3.0, stdio), httpx, python-dotenv, hatchling.

## Standards & References

- 커밋 메시지: Conventional Commits 접두어(`feat:`/`docs:`/`fix:` …) + 한글 본문.
- 작업 언어: **작업 수립은 영어, 최종 결과만 한글**로 작성한다.
- 사용자 노출 동작이 바뀌면 `.claude-plugin/plugin.json`의 `version`을 올린다.
- **Maintenance Policy:** 규칙과 코드의 괴리가 발생하면 그대로 두지 말고 업데이트를 제안하고, 재발 방지 규칙은 `.claude/rules/project.md`의 `# 프로젝트 규칙`에 추가한다.

위임 파일 (작업 영역별 상세 규칙):

- **[.claude/rules/project.md](.claude/rules/project.md)** — 프로젝트 개요·디렉터리 구조·인증/보안/MCP/배포 상세 규칙.
- **[.claude/rules/tasks.md](.claude/rules/tasks.md)** — 작업 요청 문서 우선 작성, `docs/requests/YYYY-MM/` 기록 규칙, `docs/INDEX.md` 이력 관리.
