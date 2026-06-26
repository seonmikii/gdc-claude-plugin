# 프로젝트 개요

이 레포는 **gdc-claude-plugin** — **Claude Code / Claude Desktop**에서 **GDC(`../gdc/gdc-service`)** 를 쓰기 위한 **MCP 플러그인**이다. gdc-service 본체가 아니라, 그 REST API에 붙는 **클라이언트(브리지)** 다.

* **MCP 서버(`gdc-local`, stdio)** — gdc-service REST를 감싸 태스크 조회/생성/수정, 작업 요청 문서 연동, 진행률 동기화 도구 제공
* **슬래시 커맨드** (`commands/`) — Claude Code 전용
* **PostToolUse 훅** (`hooks/`) — `docs/requests/**/*.md` 편집 시 연결된 태스크 진행률 자동 동기화 (Claude Code 전용)
* **연결 대상 기본값**: 개발 서버 `http://se.gemiso.com:11521` (`.mcp.json`의 `env`)

# 기술 스택

* **Python 3.13+**, 패키지 관리는 **uv** 사용
* **fastmcp** (>=2.3.0): stdio MCP 서버 프레임워크
* **httpx**: gdc-service REST 호출
* **python-dotenv**: 로컬 override(`.env`) 로딩
* 빌드: **hatchling** / 엔트리포인트: `gdc-mcp = gdc_mcp.server:main`
* 실행(서버 단독): `uv run --directory <플러그인 루트> gdc-mcp`

# 디렉터리 구조

* `gdc_mcp/` — MCP 서버 코드
  * `server.py` — 도구·프롬프트 정의 (FastMCP)
  * `client.py` — gdc-service REST 클라이언트(httpx)
  * `handoff.py` — 브라우저 핸드오프 인증(loopback 콜백 + 1회용 state)
  * `tokens.py` — 토큰/컨텍스트 저장 (`~/.gdc-mcp/credentials.json`, 레포별 워크스페이스/프로젝트)
  * `doc_utils.py` — 작업 요청 문서 파싱·frontmatter 연동·진행률 계산
* `commands/` — 슬래시 커맨드 정의(`/gdc-*`)
* `hooks/` — `hooks.json` (PostToolUse 진행률 동기화)
* `.claude-plugin/` — `plugin.json`(버전), `marketplace.json`
* `.mcp.json` — MCP 서버 기동 정의(dev 도메인 `env`)

# 프로젝트 규칙

## 공통
* **gdc-service 본체 코드를 이 레포에서 수정하지 않는다.** 여기는 클라이언트 플러그인이다. 서버 동작 변경이 필요하면 사용자에게 알리고 `../gdc/gdc-service`에서 별도 처리한다.
* **워크스페이스/프로젝트 컨텍스트를 항상 적용**: 도구가 데이터를 조회/생성할 때 현재 레포에 저장된 워크스페이스/프로젝트 컨텍스트(`tokens.py`)를 기준으로 동작해야 한다. 컨텍스트가 없으면 `gdc_login`/`set_context`로 안내한다.
* **성능 최적화 고려**: 불필요한 REST 왕복을 줄이고(목록 조회 후 재사용), enum/멤버 등 자주 쓰는 메타는 한 번에 받아 재활용한다.

## 인증·보안 규칙
* **인증은 브라우저 핸드오프 전용**이다. username/password 자동 로그인 변수는 추가하지 않는다.
* 토큰/시크릿은 저장 파일(`~/.gdc-mcp/credentials.json`)·메모리로만 다루고, **커밋·로그·도구 응답에 노출하지 않는다.**
* 콜백은 `127.0.0.1` loopback + 1회용 state로 한정한다.
* dev는 현재 HTTP(평문) — 평문 전송 위험은 인지된 상태이며 별도 후속 대상이다.

## MCP 서버 규칙
* **uv로 Python 의존성 관리** (`pyproject.toml` + `uv.lock`). 의존성 추가 시 `uv add`.
* 새 도구/프롬프트 추가 시 `server.py`에 FastMCP 데코레이터로 등록하고, **명확한 docstring/스키마**(파라미터 설명)를 작성한다. 자연어 호출이 가능하도록 설명을 구체적으로 쓴다.
* 슬래시 커맨드(`/gdc-*`)와 MCP 프롬프트는 **대응 관계를 유지**한다(Desktop은 슬래시 커맨드 미지원 → 프롬프트로 동일 기능 제공).
* gdc-service REST 호출은 `client.py`를 통해서 하고, 입력 검증(날짜 순서·미래 종료일 차단, 멤버 소속 확인 등)을 도구 레벨에서 수행한다.

## 버전·배포 규칙
* 사용자 노출 동작이 바뀌면 `.claude-plugin/plugin.json`의 `version`을 올린다.
* 배포는 마켓플레이스 갱신(`/plugin marketplace update`) + 재설치로 반영된다.

# 작업중 프로젝트 주의사항 개선
* 오류 개선을 위한 내부 규칙이 추가되어야 하는 경우 project.md의 `# 프로젝트 규칙`에 추가하여 오류를 줄여야 함
