# 플러그인 업데이트 커맨드 레포 내장 (/gdc-update)

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 영역 | commands, infra/config |
| 날짜 | 2026-07-20 |
| 상태 | done |
| 관련 | plugin-update, list-customers-tool, README |

## 요청 내용

지금까지 플러그인 업데이트는 개인 커맨드(`~/.claude/commands/plugin-update.md`)로만 존재해 각 사용자가 개별 관리해야 했다. 이를 **플러그인 레포의 `commands/`에 내장**해, 설치한 모든 사용자가 `/gdc-claude-plugin:gdc-update` 한 번으로 마켓플레이스 갱신 + 최신 버전 승격을 하도록 배포한다.

## 배경

- 이번 세션에서 개인 커맨드가 `claude plugin **install**`을 호출 → 이미 설치된 경우 "already installed"로 끝나 **새 버전으로 승격되지 않는 버그** 발견. 그 결과 마켓플레이스/캐시는 0.2.1이었으나 활성 포인터가 0.2.0에 고정되어 `list_customers`가 로드되지 않았다.
- 올바른 CLI 프리미티브는 `claude plugin **update** <plugin>` ("Update a plugin to the latest version"). 개인 커맨드는 이미 이 방식으로 수정 완료.
- **부트스트랩 함정**: "자기 자신을 업데이트하는 커맨드"라, 구버전에 버그 있는 업데이터가 들어있으면 그 커맨드로는 스스로를 고칠 수 없다. 버그 있는 업데이터를 넘어서는 최초 1회는 반드시 수동 `claude plugin update`가 필요 → README에 폴백 명시 필요.
- 레포 커맨드는 `/gdc-claude-plugin:<name>` 네임스페이스로 노출되므로, 기존 gdc 커맨드군과 일관되게 `gdc-update`로 명명.

## 수행 계획

- [x] 1. `commands/gdc-update.md` 추가
  - `!`claude plugin marketplace update gdc-marketplace && claude plugin update gdc-claude-plugin@gdc-marketplace --scope user``
  - `allowed-tools`: `Bash(claude plugin marketplace update:*)`, `Bash(claude plugin update:*)`
  - 실행 후 "다음 세션에서 자동 적용" 안내 문구 포함
- [x] 2. README "업데이트(새 버전 반영)" 섹션 **교체** (단순 추가 아님)
  - 현재 섹션은 승격 안 되는 버그난 `/plugin install`을 안내 중 → `/gdc-update` 커맨드 우선 안내로 교체
  - 구버전에서 올라올 때 **수동 폴백**: `claude plugin update gdc-claude-plugin@gdc-marketplace` (부트스트랩 함정 대응)
- [x] 3. README 커맨드 개수·목록 갱신
  - "슬래시 커맨드 9종" → "10종", 상단 나열(L8)에 `/gdc-update` 추가
  - 슬래시 커맨드 표에 `/gdc-update` 행 추가
- [x] 4. `.claude-plugin/plugin.json` version 올리기 (0.2.1 → 0.2.2)
- [x] 5. `docs/INDEX.md` 이력 한 줄 추가

## 참고 사항

- 변경 파일(예정): `commands/gdc-update.md`, `README.md`, `.claude-plugin/plugin.json`, `docs/INDEX.md`
- **슬래시↔MCP 프롬프트 1:1 규칙의 의도적 예외**: `gdc-update`는 플러그인 CLI 관리라 Desktop(플러그인 개념 없음)엔 대응 프롬프트가 불가능 → MCP 프롬프트 미추가가 정상. 문서에 예외로 명시.
- 개인 커맨드 `~/.claude/commands/plugin-update.md`는 레포 밖 산출물 — 레포판 배포 후 중복이므로 **삭제 또는 유지 택1**(사용자 결정). 이 문서 범위에는 포함하지 않음.
- gdc-service 본체 수정 없음. MCP 도구 변경 없음(커맨드/문서/버전만).
- 명명은 `gdc-update`로 제안 — 기존 `gdc-login`/`gdc-switch` 등과 일관. 대안: `gdc-plugin-update`.
