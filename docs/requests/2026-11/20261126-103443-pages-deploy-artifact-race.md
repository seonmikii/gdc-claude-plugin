# 가이드 사이트 Pages 배포 간헐 실패 대응 (아티팩트 조회 경쟁 상태)

| 속성 | 값 |
|------|-----|
| 유형 | fix |
| 영역 | infra/.github/workflows |
| 날짜 | 2026-11-26 |
| 상태 | done |
| 관련 | 20261125-155048-site-tool-count-fix, 20261125-150000-release-notes-v2-11-6 |

## 요청 내용

`Deploy guide site`(`.github/workflows/pages.yml`) 워크플로가 11/25 오후부터 자주 실패한다. 원인을 확인하고 재발하지 않도록 조치한다.

## 배경

**증상**: 최근 7회 중 5회 실패(#23·#24·#25·#26·#28). 실패 시 오류는 모두 같다.

```
Found 0 artifact(s)
Error: No artifacts named "github-pages" were found for this workflow run.
```

**원인**: 업로드 직후 바로 조회해서 생기는 경쟁 상태(GitHub 측 반영 지연)이며, 워크플로·사이트 내용 문제가 아니다.

| run | 업로드 완료(finalized) | deploy 조회 | 간격 | 결과 |
|-----|-----------------------|------------|------|------|
| #22 | 06:46:09.60 | 06:46:10.14 | 0.5s | Found 1 → 성공 |
| #24 | 07:00:08.00 | 07:00:08.44 | 0.4s | Found 0 → 실패 |
| #25 | 07:00:58.79 | 07:00:59.32 | 0.5s | Found 0 → 실패 |
| #27 | 08:39:06.80 | 08:39:07.28 | 0.5s | Found 1 → 성공 |
| #28 | 00:41:01.91 | 00:41:02.57 | 0.7s | Found 0 → 실패 (재실행 시 성공) |

- 실패한 run에서도 `upload-pages-artifact`는 매번 성공했다("successfully finalized. Artifact ID …"). 화면의 Artifacts 1개가 그 결과다.
- 같은 job 안에서 업로드 후 1초도 안 되어 `deploy-pages`가 아티팩트 목록을 조회하는데, 목록 API에 아직 반영되지 않아 0개가 나온다.
- 같은 커밋 `31c4af9`가 #24~#26에서는 실패하고 #27에서 성공했다. 같은 코드가 타이밍에 따라 결과가 갈린다는 근거다.
- `deploy-pages` 최신 v5.0.1의 재시도(backoff)는 **배포 상태 polling**에만 적용된다. 아티팩트 조회 실패는 버전을 올려도 해결되지 않는다.

**부수 경고**: 현재 쓰는 액션들(checkout@v4·configure-pages@v5·upload-pages-artifact@v3·deploy-pages@v4)이 Node.js 20 대상이라 Node 24로 강제 실행된다는 경고가 나온다.

**즉시 조치 완료**: #28을 재실행해 성공했다(`Found 1 artifact(s)` → `Reported success!`). PR #36 내용은 사이트에 반영되었다.

## 수행 계획

1. **build / deploy 잡 분리** — GitHub 공식 Pages 시작 워크플로와 같은 구조로 바꾼다. 업로드는 `build` 잡에서, 배포는 `needs: build`로 연결한 `deploy` 잡에서 한다. 잡이 바뀌는 사이(새 runner 할당)에 수 초가 생겨 업로드와 조회 사이 간격이 벌어진다.
2. **액션 버전 상향** — Node 20 지원 종료 경고를 없앤다.
   - `actions/checkout` v4 → v7 (v7의 fork PR 차단 변경은 이 워크플로가 push·workflow_dispatch 전용이라 영향 없음)
   - `actions/configure-pages` v5 → v6 (Node 24 전환)
   - `actions/upload-pages-artifact` v3 → v5 (v4부터 dotfile을 제외하지만 `site/`에 dotfile이 없어 영향 없음)
   - `actions/deploy-pages` v4 → v5 (Node 24 전환)
3. **머지 전 검증** — 워크플로 YAML 구문과 잡 구조(`build` → `deploy`) 확인. 실제 배포 검증은 `github-pages` 환경이 `main`만 허용해 머지 전에는 불가하므로, 참고 사항의 '머지 후 확인 절차'로 진행한다.

변경 후 워크플로 골격:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/configure-pages@v6
      - uses: actions/upload-pages-artifact@v5
        with:
          path: site

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v5
```

`on`·`permissions`·`concurrency`(cancel-in-progress: false)와 상단 주석(site/만 업로드)은 그대로 둔다.

## 작업 결과

- [x] 원인 분석 (실패 run 5건 로그 대조)
- [x] #28 재실행으로 미반영 배포 복구
- [x] build / deploy 잡 분리
- [x] 액션 버전 상향
- [x] 워크플로 YAML 구문·잡 구조 확인 (`github-pages` 환경 배포 브랜치 정책이 `main` 한정임을 확인)

## 참고 사항

- 변경 파일: `.github/workflows/pages.yml` 1개. 사용자에게 보이는 플러그인 동작 변경이 없으므로 `plugin.json` version은 올리지 않는다.
- **머지 후 확인 절차**: main 머지로 트리거된 push run과 `workflow_dispatch` 3회가 모두 성공하는지, 각 run의 deploy 잡 로그에 `Found 1 artifact(s)`가 찍히는지 확인한다(경쟁 상태는 확률적으로 생기므로 여러 번 확인). 실패하면 이 문서를 다시 열어 원인과 추가 조치를 기록한다.
- MCP 도구/서버 동작과 무관하므로 `로컬 사전 검증`은 생략한다.
- 잡을 분리해도 GitHub 측 지연이 수 초를 넘으면 실패할 수 있다. 다시 실패하면 실패한 잡만 재실행(Re-run failed jobs)하면 되고, deploy 잡만 다시 돌므로 업로드는 반복하지 않는다.
- (별건) `site/build-artifact.py`(Artifact용 HTML 추출 스크립트)가 `site/` 전체 업로드에 포함되어 공개 사이트에 함께 배포되고 있다. 비밀 정보는 없지만 의도한 배포 대상이 아니면 위치 이동을 별도로 검토한다. 이번 작업 범위에는 넣지 않는다.
- 출처: 각 액션의 GitHub Releases — [checkout](https://github.com/actions/checkout/releases), [configure-pages](https://github.com/actions/configure-pages/releases), [upload-pages-artifact](https://github.com/actions/upload-pages-artifact/releases), [deploy-pages](https://github.com/actions/deploy-pages/releases)
