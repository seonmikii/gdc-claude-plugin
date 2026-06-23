# gdc-claude-plugin

**Claude Code**(및 **Claude Desktop**)에서 **GDC(gdc-service)** 를 쓰기 위한 플러그인이다. MCP 도구 + 슬래시 커맨드 + 진행률 자동 동기화 훅을 한 번에 설치한다. 기본 연결 대상은 **개발 서버 `http://se.gemiso.com:11521`**.

## 구성 요소

- **MCP 서버(`gdc-local`, stdio)** — 태스크 조회/생성/수정, 작업 요청 문서 연동, 진행률 동기화 등 **도구 15종**. (Claude Code·Desktop 공통)
- **슬래시 커맨드 9종** — `/gdc-login` `/gdc-switch` `/gdc-my-tasks` `/gdc-tasks` `/gdc-task-new` `/gdc-task-from-doc` `/gdc-doc-from-task` `/gdc-link-task` `/gdc-sync`. (**Claude Code 전용**)
- **PostToolUse 훅** — `docs/requests/**/*.md` 편집 시 연결된 태스크 진행률 자동 동기화. (**Claude Code 전용**)

## 전제조건

- **`uv`** 설치 (MCP 서버를 `uv run`으로 기동). https://docs.astral.sh/uv/
- Python 3.13+ (uv가 자동 관리).

---

## Claude Code에서 사용

### 설치 (각 사용자가 자기 PC에서 1회)

마켓플레이스 추가와 설치는 **사용자별 설정**(`~/.claude`)이라, 팀원 **모두 각자 한 번씩** 실행해야 한다.

```sh
# 1) 마켓플레이스 추가 (사용자당 1회)
/plugin marketplace add seonmikii/gdc-claude-plugin
# 2) 플러그인 설치
/plugin install gdc-claude-plugin@gdc-marketplace
# 3) 적용
/reload-plugins        # 또는 Claude Code 재시작
```

적용 후 `/mcp` 또는 `/plugin`에서 `gdc-local`이 `✓ Connected`로 뜨면 정상.

### 업데이트 (새 버전 반영)

플러그인이 갱신되면 마켓플레이스를 새로고침하고 재설치한다.

```sh
/plugin marketplace update gdc-marketplace     # 최신 버전 가져오기
/plugin install gdc-claude-plugin@gdc-marketplace
/reload-plugins
```

> 설치/업데이트가 `EBUSY: resource busy or locked` 로 막히면, 실행 중인 MCP 서버가 캐시 폴더를 점유한 것이다. `/plugin`에서 플러그인을 **Disable 후 재설치**하거나, Claude Code를 **완전 재시작**한 뒤 다시 설치한다.

### 인증 (브라우저 핸드오프)

```
/gdc-login
```

브라우저 창이 열리면 평소처럼 로그인(Google·로컬 모두 가능)하고 **워크스페이스/프로젝트를 선택**한 뒤 "연결 허용"을 누른다.

- 인증 토큰은 `~/.gdc-mcp/credentials.json` 에 저장된다(사용자 단위 공유, 커밋 금지).
- 선택한 **워크스페이스/프로젝트는 현재 레포(폴더)에만** 적용된다 → 레포마다 한 번씩 `/gdc-login` 하면 레포별로 다른 프로젝트를 쓴다.
- 콜백은 `127.0.0.1` loopback + 1회용 state로 한정된다.

### 슬래시 커맨드

| 커맨드 | 설명 |
|--------|------|
| `/gdc-login` | 브라우저 핸드오프 인증/재인증 (워크스페이스·프로젝트 선택) |
| `/gdc-switch` | 현재 레포의 워크스페이스/프로젝트 전환(재인증 없이) |
| `/gdc-my-tasks [--overdue] [--undated] [--all]` | 내 미해결 태스크 조회(선택 프로젝트 기준) |
| `/gdc-tasks <담당자> [--overdue] [--undated] [--all]` | 특정 담당자(이름 또는 id)의 태스크 조회 |
| `/gdc-task-new` | 새 태스크 생성(선택 목록·한글·담당자 자동) |
| `/gdc-task-from-doc <path>` | 작업 요청 문서로 태스크 생성 |
| `/gdc-doc-from-task <task_id>` | 태스크로 작업 요청 문서 생성·연동 |
| `/gdc-link-task <task_id> [doc]` | 기존 태스크를 기존 문서와 연동 |
| `/gdc-sync [path]` | 문서 진행률을 연결된 태스크에 강제 동기화 |

---

## Claude Desktop에서 사용

Claude Desktop은 **플러그인/마켓플레이스/슬래시 커맨드/훅을 지원하지 않는다.** 대신 **MCP 서버를 직접 등록**하면 아래 도구와 프롬프트(슬래시 커맨드 대응)를 모두 쓸 수 있다.

1. 레포를 로컬에 클론한다.
   ```sh
   git clone https://github.com/seonmikii/gdc-claude-plugin
   ```
2. Claude Desktop 설정 파일에 MCP 서버를 추가한다.
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   ```json
   {
     "mcpServers": {
       "gdc-local": {
         "command": "uv",
         "args": ["run", "--directory", "<클론 경로>/gdc-claude-plugin", "gdc-mcp"],
         "env": {
           "GDC_BASE_URL": "http://se.gemiso.com:11521",
           "GDC_WEB_URL": "http://se.gemiso.com:11521"
         }
       }
     }
   }
   ```
3. Claude Desktop을 재시작한다. 인증은 대화창에서 **`gdc_login` 프롬프트**(입력창 "+" 메뉴)를 실행하거나 "gdc 로그인"이라고 요청한다.

> Desktop에서는 진행률 자동 동기화 훅과 `/gdc-*` 슬래시 커맨드는 동작하지 않는다. 동일 기능을 **MCP 프롬프트 9종**(`gdc_login`/`gdc_switch`/`gdc_my_tasks`/`gdc_tasks`/`gdc_task_new`/`gdc_task_from_doc`/`gdc_doc_from_task`/`gdc_link_task`/`gdc_sync`)으로 "+" 메뉴에서 호출할 수 있고, 진행률 동기화는 `sync_doc_progress`(또는 `gdc_sync` 프롬프트)로 수동 실행한다.

---

## MCP 도구 (Code·Desktop 공통)

자연어로 요청하면 Claude가 아래 도구를 호출한다("내 태스크 보여줘", "김철수 담당 태스크 조회해줘" 등).

| 도구 | 설명 |
|------|------|
| `gdc_login` | 브라우저 핸드오프로 MCP 전용 토큰 발급, 워크스페이스/프로젝트를 레포별 저장 |
| `get_context` | 현재 레포에 적용되는 워크스페이스/프로젝트 확인 |
| `set_context` | 현재 레포의 워크스페이스/프로젝트 전환(재인증 없이) |
| `list_workspaces` | 접근 가능한 워크스페이스 목록 |
| `list_projects` | 지정 워크스페이스의 프로젝트 목록 |
| `get_project_enums` | 프로젝트별 status/priority/task_type/members(담당자·관련자 후보) |
| `list_my_tasks` | 내(담당/작성/참여) 미해결 태스크 — `not_finished`/`overdue`/`undated` |
| `list_tasks` | 특정 담당자(이름 또는 id)의 태스크 — 동일 필터 |
| `create_task` | 태스크 생성(담당자 기본=본인, 날짜·멤버 입력 검증) |
| `update_task` | 태스크 부분 수정(날짜 순서·미래·멤버 검증) |
| `get_task` | 태스크 상세 조회 |
| `open_task` | 태스크 웹 화면을 Chrome 새 탭으로 열기 |
| `task_from_doc` | 작업 요청 문서로 태스크 생성 + 문서 frontmatter에 연동 기록 |
| `link_task_to_doc` | 기존 태스크를 기존 문서와 연동(새로 만들지 않음) |
| `sync_doc_progress` | 문서의 Phase/체크박스 진척을 연결된 태스크 진행률·상태·날짜에 동기화 |

**입력 규칙(참고)**: 담당자/관련자는 **user id 또는 멤버 이름**(자동 id 해석, 비멤버면 멤버 목록 안내). 날짜는 `YYYY-MM-DD`이며 예상/실제 시작일 ≤ 종료일, 실제 종료일은 미래 불가(미충족 시 안내·차단).

---

## 로컬 개발 override

기본 연결은 dev다. 로컬 gdc-service로 붙이려면 환경변수로 덮어쓴다(`.env.example` 참고). Code는 플러그인 `.mcp.json`의 `env`, Desktop은 위 설정의 `env`를 바꾸면 된다.

```sh
GDC_BASE_URL=http://localhost:8000
GDC_WEB_URL=http://localhost:5173
```

## 주의

- 인증은 **브라우저 핸드오프 전용**이다(username/password 자동 로그인 없음).
- 토큰·시크릿은 저장 파일·메모리로만 다루며 커밋·로그에 노출하지 않는다.
- dev는 현재 HTTP(평문)다. 토큰 평문 전송 위험은 인지된 상태이며 별도 보완(후속) 대상이다.
