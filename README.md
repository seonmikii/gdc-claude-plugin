# gdc-claude-plugin

**Claude Code**(및 **Claude Desktop**)에서 **GDC(gdc-service)** 를 쓰기 위한 플러그인이다. MCP 도구 + 슬래시 커맨드 + 진행률 자동 동기화 훅을 한 번에 설치한다. 기본 연결 대상은 **운영 서버 `https://gdc.gemiso.com`**.

## 구성 요소

- **MCP 서버(`gdc-local`, stdio)** — 태스크 조회/생성/수정, 태스크 댓글, 작업 요청 문서 연동, 진행률 동기화 등 **도구 21종**. (Claude Code·Desktop 공통)
- **슬래시 커맨드 12종** — `/gdc-login` `/gdc-switch` `/gdc-my-tasks` `/gdc-tasks` `/gdc-task` `/gdc-task-new` `/gdc-task-from-doc` `/gdc-doc-from-task` `/gdc-link-task` `/gdc-apply` `/gdc-sync` `/gdc-update`. (**Claude Code 전용**)
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

플러그인 업데이트는 **터미널 CLI에서** 한다. CLI 세션에서는 `/gdc-update` 커맨드가 `claude`를 감지해 아래 두 명령을 대신 실행해준다.

```
/gdc-update
```

또는 두 명령을 직접 실행해도 된다(둘 다 CLI 전용). 실행 후 Claude Code를 재시작한다.

```sh
claude plugin marketplace update gdc-marketplace
claude plugin update gdc-claude-plugin@gdc-marketplace
```

> `/plugin install`은 이미 설치된 경우 새 버전으로 **승격되지 않으니**(`already installed`) 반드시 `update`를 쓴다.

> **⚠️ VSCode 확장에서는 업데이트가 안 된다.** 확장은 `claude` 바이너리를 셸 PATH에 올리지 않고(CLI 미존재), CLI용 `/plugin` 커맨드도 없으며, `/plugins` GUI의 마켓플레이스 새로고침은 캐시만 받을 뿐 설치 버전 포인터(`installed_plugins.json`)를 승격하지 않는다. 따라서 `/gdc-update` 커맨드도 확장에서는 실제 업데이트를 수행하지 못한다.
> **업데이트하려면 CLI를 쓴다** — [standalone CLI](https://code.claude.com/docs/en/setup)를 설치한 뒤 VSCode 통합 터미널(`` Ctrl+` ``)에서 위 두 명령을 실행하고 Claude Code를 재시작한다.

> 설치/업데이트가 `EBUSY: resource busy or locked` 로 막히면, 실행 중인 MCP 서버가 캐시 폴더를 점유한 것이다. 플러그인을 **Disable 후 재설치**하거나, Claude Code를 **완전 재시작**한 뒤 다시 실행한다.

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
| `/gdc-task <id\|제목>` | 태스크 상세 조회(하위·연관·상위 태스크 포함) |
| `/gdc-task-new` | 새 태스크 생성(선택 목록·한글·담당자 자동) |
| `/gdc-task-from-doc <path>` | 작업 요청 문서로 태스크 생성 |
| `/gdc-doc-from-task <task_id>` | 태스크로 작업 요청 문서 생성·연동 |
| `/gdc-link-task <task_id> [doc]` | 기존 태스크를 기존 문서와 연동 |
| `/gdc-apply [path]` | 문서 변경을 태스크 본문/댓글/하위 태스크에 반영(분류→라우팅) |
| `/gdc-sync [path]` | 문서 진행률을 연결된 태스크에 강제 동기화 |
| `/gdc-update` | gdc-marketplace 갱신 후 플러그인 최신 버전으로 승격 |

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
         "args": ["run", "--directory", "<클론 경로>/gdc-claude-plugin", "python", "-m", "gdc_mcp.server"],
         "env": {
           "GDC_BASE_URL": "https://gdc.gemiso.com",
           "GDC_WEB_URL": "https://gdc.gemiso.com"
         }
       }
     }
   }
   ```
3. Claude Desktop을 재시작한다. 인증은 대화창에서 **`gdc_login` 프롬프트**(입력창 "+" 메뉴)를 실행하거나 "gdc 로그인"이라고 요청한다.

> Desktop에서는 진행률 자동 동기화 훅과 `/gdc-*` 슬래시 커맨드는 동작하지 않는다. 동일 기능을 **MCP 프롬프트 11종**(`gdc_login`/`gdc_switch`/`gdc_my_tasks`/`gdc_tasks`/`gdc_task`/`gdc_task_new`/`gdc_task_from_doc`/`gdc_doc_from_task`/`gdc_link_task`/`gdc_apply`/`gdc_sync`)으로 "+" 메뉴에서 호출할 수 있고, 진행률 동기화는 `sync_doc_progress`(또는 `gdc_sync` 프롬프트)로 수동 실행한다.
>
> ※ `/gdc-update`는 플러그인 CLI(마켓플레이스) 관리 커맨드라 대응 MCP 프롬프트가 없다. Desktop은 플러그인 개념이 없어(MCP 서버를 직접 등록) `git pull`로 최신 코드를 받아 Desktop을 재시작하면 반영된다.

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
| `list_customers` | 프로젝트에 지정 가능한 고객사 목록 |
| `get_project_enums` | 프로젝트별 status/priority/task_type/members(담당자·관련자 후보) |
| `list_my_tasks` | 내(담당/작성/참여) 미해결 태스크 — `not_finished`/`overdue`/`undated` |
| `list_tasks` | 특정 담당자(이름 또는 id)의 태스크 — 동일 필터 |
| `create_task` | 태스크 생성(담당자 기본=본인, 날짜·멤버 입력 검증, 완료 상태면 진행률·실제 종료일 자동 보정) |
| `update_task` | 태스크 부분 수정(날짜 순서·미래·멤버 검증) |
| `edit_task_description` | 태스크 본문 최소 편집 — `append_work`(블렛 추가)·`replace_section`(라벨 섹션만 교체, 인라인 이미지 보존) |
| `get_task` | 태스크 상세 조회(하위·연관·상위 태스크 포함) |
| `open_task` | 태스크 웹 화면을 Chrome 새 탭으로 열기 |
| `task_from_doc` | 작업 요청 문서로 태스크 생성 + 문서 frontmatter에 연동 기록(완료 상태면 진행률·실제 종료일 자동 보정) |
| `link_task_to_doc` | 기존 태스크를 기존 문서와 연동(새로 만들지 않음) |
| `sync_doc_progress` | 문서의 Phase/체크박스 진척을 연결된 태스크 진행률·상태·날짜에 동기화(`description` 전달 시 태스크 본문도 함께 갱신) |
| `list_task_comments` | 태스크 댓글(Mention) 목록 조회 |
| `add_task_comment` | 태스크 댓글 작성(멘션 지원) |
| `update_task_comment` | 태스크 댓글 수정 |
| `delete_task_comment` | 태스크 댓글 삭제 |

**입력 규칙(참고)**: 담당자/관련자는 **user id 또는 멤버 이름**(자동 id 해석, 비멤버면 멤버 목록 안내). 날짜는 `YYYY-MM-DD`이며 예상/실제 시작일 ≤ 종료일, 실제 종료일은 미래 불가(미충족 시 안내·차단). **완료 계열 상태(category=='done')로 태스크를 생성하면 진행률 100%·실제 종료일=오늘이 자동 주입된다.**

---

## 로컬 개발 override

기본 연결은 운영 서버다. 로컬 gdc-service로 붙이려면 환경변수로 덮어쓴다(`.env.example` 참고). Code는 플러그인 `.mcp.json`의 `env`, Desktop은 위 설정의 `env`를 바꾸면 된다.

```sh
GDC_BASE_URL=http://localhost:8000
GDC_WEB_URL=http://localhost:5173
```

## 주의

- 인증은 **브라우저 핸드오프 전용**이다(username/password 자동 로그인 없음).
- 토큰·시크릿은 저장 파일·메모리로만 다루며 커밋·로그에 노출하지 않는다.
- 기본 연결(운영)은 HTTPS다. dev 서버(`http://se.gemiso.com:11521`)로 override 시 HTTP(평문) — 토큰 평문 전송 위험은 인지된 상태이며 별도 보완(후속) 대상이다.
