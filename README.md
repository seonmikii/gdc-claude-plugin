# gdc-claude-plugin

Claude Code(및 Desktop)에서 **GDC(gdc-service)** 를 쓰기 위한 플러그인이다. MCP 도구 + 슬래시 커맨드 + 진행률 자동 동기화 훅을 한 번에 설치한다. 기본 연결 대상은 **개발 서버 `http://se.gemiso.com:11521`**.

## 구성 요소

- **MCP 서버(`gdc-local`, stdio)** — 태스크 조회/생성/수정, 작업 요청 문서 연동, 진행률 동기화 도구.
- **슬래시 커맨드 9종** — `/gdc-login` `/gdc-switch` `/gdc-my-tasks` `/gdc-tasks` `/gdc-task-new` `/gdc-task-from-doc` `/gdc-doc-from-task` `/gdc-link-task` `/gdc-sync`.
- **PostToolUse 훅** — `docs/requests/**/*.md` 편집 시, 연결된 태스크 진행률을 자동 동기화.

## 전제조건

- **`uv`** 설치 (MCP 서버를 `uv run`으로 기동). https://docs.astral.sh/uv/
- Python 3.13+ (uv가 자동 관리).

## 설치

```sh
# 1) 마켓플레이스 추가
/plugin marketplace add seonmikii/gdc-claude-plugin
# 2) 플러그인 설치
/plugin install gdc-claude-plugin@gdc-marketplace
```

설치 후 Claude Code를 재시작하면 MCP 서버가 `✓ Connected` 로 뜬다.

## 인증 (브라우저 핸드오프)

```
/gdc-login
```

브라우저 창이 열리면 평소처럼 로그인(Google·로컬 모두 가능)하고 **워크스페이스/프로젝트를 선택**한 뒤 "연결 허용"을 누른다.

- 인증 토큰은 `~/.gdc-mcp/credentials.json` 에 저장된다(사용자 단위 공유, 커밋 금지).
- 선택한 **워크스페이스/프로젝트는 현재 레포(폴더)에만** 적용된다 → 레포마다 한 번씩 `/gdc-login` 하면 레포별로 다른 프로젝트를 쓴다.
- 콜백은 `127.0.0.1` loopback + 1회용 state로 한정된다.

## 사용

| 커맨드 | 설명 |
|--------|------|
| `/gdc-my-tasks [--overdue] [--undated] [--all]` | 내 미해결 태스크 조회(선택 프로젝트 기준) |
| `/gdc-tasks <담당자> [--overdue] [--undated] [--all]` | 특정 담당자(이름 또는 id)의 태스크 조회 |
| `/gdc-task-new` | 새 태스크 생성(선택 목록·한글·담당자 자동) |
| `/gdc-task-from-doc <path>` | 작업 요청 문서로 태스크 생성 |
| `/gdc-doc-from-task <task_id>` | 태스크로 작업 요청 문서 생성·연동 |
| `/gdc-link-task <task_id> [doc]` | 기존 태스크를 기존 문서와 연동 |
| `/gdc-sync [path]` | 문서 진행률을 연결된 태스크에 강제 동기화 |
| `/gdc-switch` | 현재 레포의 워크스페이스/프로젝트 전환(재인증 없이) |

## 로컬 개발 override

기본 연결은 dev다. 로컬 gdc-service로 붙이려면 환경변수로 덮어쓴다(`.env.example` 참고):

```sh
GDC_BASE_URL=http://localhost:8000
GDC_WEB_URL=http://localhost:5173
```

## 주의

- 인증은 **브라우저 핸드오프 전용**이다(username/password 자동 로그인 없음).
- 토큰·시크릿은 저장 파일·메모리로만 다루며 커밋·로그에 노출하지 않는다.
- dev는 현재 HTTP(평문)다. 토큰 평문 전송 위험은 인지된 상태이며 별도 보완(후속) 대상이다.
