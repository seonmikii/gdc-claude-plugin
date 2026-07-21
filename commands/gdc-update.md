---
description: gdc-marketplace 갱신 후 gdc-claude-plugin을 최신 버전으로 승격
allowed-tools: Bash(command -v claude:*), Bash(claude plugin marketplace update:*), Bash(claude plugin update:*)
---

gdc-claude-plugin을 최신 버전으로 업데이트합니다. 실행 환경에 따라 방법이 다르므로 아래 순서를 그대로 따르세요.

## 1단계 — `claude` CLI가 셸에 있는지 확인

`command -v claude` 를 실행합니다.

## 2단계 — 분기

**(A) `claude` 경로가 출력되면** (터미널 CLI 세션): 아래 두 명령을 실행하고 결과를 확인합니다.

```sh
claude plugin marketplace update gdc-marketplace && claude plugin update gdc-claude-plugin@gdc-marketplace --scope user
```

**(B) `command not found` 등으로 아무것도 안 나오면** (VSCode 확장 등 — `claude` 바이너리가 PATH에 없음): 셸로는 업데이트할 수 없습니다. VSCode 확장에는 CLI용 `/plugin`(단수) 커맨드가 없고 **`/plugins`(복수) GUI 관리자**가 있습니다. 사용자에게 아래를 직접 하도록 안내하세요(당신이 대신 실행할 수 없음):

1. 프롬프트 박스에 **`/plugins`**(복수) 입력 → **Manage plugins** 창 열기
2. **Marketplaces** 탭 → `gdc-marketplace` 옆 **새로고침(refresh) 아이콘** 클릭 (마켓플레이스 목록 최신화)
3. **Plugins** 탭에서 `gdc-claude-plugin`이 최신 버전으로 갱신됨을 확인
4. 하단 배너의 **restart Claude Code** 안내대로 재시작 시 반영

## 3단계 — 마무리 안내

업데이트가 완료되면, 변경된 플러그인은 **다음 Claude Code 세션 시작 시 자동 적용**된다는 점을 사용자에게 알려주세요.

참고: `claude plugin install`은 이미 설치된 플러그인을 새 버전으로 승격하지 않습니다("already installed"로 끝남). 반드시 `claude plugin update`(CLI) 또는 `/plugin` Installed 탭(내장)을 사용해야 활성 버전 포인터가 최신으로 올라갑니다.
