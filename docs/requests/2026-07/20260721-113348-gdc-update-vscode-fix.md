---
task_id:
task_url:
---

# /gdc-update VSCode 확장 대응 (claude CLI 미존재 환경 수정)

| 속성 | 값 |
|------|-----|
| 유형 | fix |
| 영역 | commands, docs |
| 날짜 | 2026-07-21 |
| 상태 | done |
| 관련 | ship-update-command, plugin-update |

## 요청 내용

다른 레포에서 `/gdc-update` 실행 시 `bash: line 3: claude: command not found` 오류 발생. VSCode 네이티브 확장 환경에서 `/gdc-update`가 동작하도록 수정한다.

## 배경 / 원인 분석

- `/gdc-update`는 `!`claude plugin marketplace update ... && claude plugin update ...`` 셸 자동실행에 의존.
- 사용자는 **VSCode 네이티브 확장**으로 Claude Code를 실행 중. 확장은 `claude` 바이너리를 셸 PATH에 올리지 않는다(전용 사본을 내부에만 번들). `command -v claude`·`which claude`·설치 경로 어디에도 없음을 확인 → `command not found`.
- 슬래시 커맨드의 `!` 프리픽스는 **셸만** 실행 → `/plugin` 같은 내장 슬래시 커맨드를 호출할 수 없음(공식 문서 확인).
- `/plugin marketplace update`는 **슬래시 전용**으로 CLI/셸 등가물이 없음 → 셸로 온전히 재현 불가.
- 결론: 기존 커맨드는 `claude` CLI가 PATH에 있는 **터미널 CLI 세션 전용**. VSCode 확장·CLI 미설치 환경에선 원리적으로 실패.

출처: https://code.claude.com/docs/en/vs-code.md (Run CLI in VS Code), https://code.claude.com/docs/en/discover-plugins.md (Manage marketplaces), https://code.claude.com/docs/en/plugins-reference.md (plugin update)

## 수행 계획

- [x] 1. `commands/gdc-update.md`를 환경 감지형 가이드로 재작성
  - `!` 자동실행 제거 → 모델이 `command -v claude`로 분기
  - CLI 있음(터미널): `claude plugin marketplace update` + `claude plugin update` 실행
  - CLI 없음(VSCode 확장 등): `/plugins`(복수) GUI → Marketplaces 탭 새로고침 → Plugins 탭 최신 확인 → 재시작 안내 (CLI용 `/plugin` 단수는 확장에 없음)
  - `allowed-tools`에 `Bash(command -v claude:*)` 추가
- [x] 2. README "업데이트" 섹션에 VSCode 확장 폴백(내장 `/plugin`) 추가
- [x] 3. `.claude-plugin/plugin.json` version 0.2.2 → 0.2.3
- [x] 4. `docs/INDEX.md` 이력 한 줄 추가

## 참고 사항

- gdc-service 본체 수정 없음. MCP 도구 변경 없음(커맨드/문서/버전만).
- 슬래시↔MCP 프롬프트 1:1 예외 유지: `gdc-update`는 플러그인 CLI 관리라 Desktop 대응 프롬프트 없음(정상).
