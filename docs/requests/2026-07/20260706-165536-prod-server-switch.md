# 연결 대상 기본값을 운영 서버(https://gdc.gemiso.com)로 변경

| 속성 | 값 |
|------|-----|
| 유형 | infra |
| 영역 | infra/config |
| 날짜 | 2026-07-06 |
| 상태 | done |
| 관련 | .mcp, README, project |

## 요청 내용

플러그인의 기본 연결 대상을 개발 서버(`http://se.gemiso.com:11521`)에서 운영 서버(`https://gdc.gemiso.com`)로 변경.

## 작업 결과

- [x] `.mcp.json` — `GDC_BASE_URL`/`GDC_WEB_URL`을 `https://gdc.gemiso.com`으로 변경
- [x] `README.md` — 기본 연결 대상 설명·Desktop 설정 예시·로컬 override 문구·`주의`의 평문(HTTP) 문구 갱신
- [x] `.claude/rules/project.md` — 연결 대상 기본값·평문 전송 규칙 문구 갱신
- [x] `.env.example` — 기본값 주석을 운영 도메인 기준으로 갱신
- [x] `.claude-plugin/plugin.json` — version 0.1.10 → 0.1.11

## 참고 사항

- 기존에 dev 서버로 발급받은 토큰(`~/.gdc-mcp/credentials.json`)은 운영 서버에서 유효하지 않으므로, 변경 반영 후 `gdc_login` 재인증이 필요하다.
- 반영 절차: 마켓플레이스 갱신(`/plugin marketplace update`) + 재설치, Desktop은 설정 파일의 `env` 직접 수정.
- 로컬 개발 시에는 기존과 동일하게 `.env`/`env`로 override 가능.
