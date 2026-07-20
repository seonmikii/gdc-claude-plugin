---
description: gdc-marketplace 갱신 후 gdc-claude-plugin을 최신 버전으로 승격
allowed-tools: Bash(claude plugin marketplace update:*), Bash(claude plugin update:*)
---

gdc 마켓플레이스를 최신으로 갱신하고 플러그인을 최신 버전으로 업데이트합니다.

!`claude plugin marketplace update gdc-marketplace && claude plugin update gdc-claude-plugin@gdc-marketplace --scope user`

위 명령 결과를 확인하고, 업데이트가 완료되면 변경된 플러그인은 다음 Claude Code 세션 시작 시 자동 적용된다는 점을 사용자에게 알려주세요.

참고: `claude plugin install`은 이미 설치된 플러그인을 새 버전으로 승격하지 않습니다("already installed"로 끝남). 반드시 `claude plugin update`를 사용해야 활성 버전 포인터가 최신으로 올라갑니다.
