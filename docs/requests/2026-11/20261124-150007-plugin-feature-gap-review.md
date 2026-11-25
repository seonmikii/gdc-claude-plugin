# GDC 플러그인 미지원 기능 검토 및 보강 (#850)

| 속성 | 값 |
|------|-----|
| 유형 | feat / fix |
| 영역 | server/gdc_mcp |
| 날짜 | 2026-11-24 |
| 상태 | done |
| 관련 | [#850](https://gdc.gemiso.com/tasks/19608) |

## 요청 내용

새로 추가된 GDC 기능 중 플러그인에서 빠진 것(하위 태스크 연결, 태그 추가 등)을 꼼꼼히 검토하고, 필요한 부분을 구현한다.

## 배경 — 검토 방법

- 기준: gdc-service `develop`(94b283e6) — `backend/tasks`·`projects`·`suggestions`의 URL/뷰/시리얼라이저, 프론트 `src/services/*.ts`의 실제 호출, 2026-08 이후 feat 커밋
- 대조: 플러그인 v0.9.1 `gdc_mcp/server.py` 전 도구의 REST 호출·전송 필드

## 검토 결과

### A. 기존 도구의 버그·서버와 어긋난 부분 (정정 필요)

| # | 항목 | 현상 | 근거 |
|---|------|------|------|
| A1 | **태그 지정 불가 + 안내문 오류** | create/update_task 안내문에 "태그 id를 보내도 무시된다"고 되어 있으나, 서버는 2026-08-24(645056cb)부터 `tag_ids`를 받아 수동 부착을 지원한다. 웹의 TaskTagSelect도 `tag_ids`를 쓴다. 플러그인은 태그를 읽기만 가능 | `tasks/serializers.py:939,1288-1297,1414-1420` |
| A2 | **고정(is_pinned) 상한 우회** | update_task가 `is_pinned`를 PATCH로 직접 보낸다. 서버의 고정 규칙(프로젝트당 최대 5개, 숨긴 태스크 고정 불가)은 `pin` 액션에만 있어 PATCH로는 6개 이상·숨긴 태스크도 고정된다 | `tasks/views.py:1817-1844`, perform_update에 가드 없음 |
| A3 | **건의 상태 '답변완료' 누락** | 서버에 `answered`(답변완료, #787) 추가됨. 플러그인 라벨표에 없어 목록에 영문 코드로 보이고 상태로 거를 수 없다 | `suggestions/models.py:20`, `server.py:2539` |
| A4 | **프로젝트 고객사 자동 지정 미적용** | #838 '태스크 고객사 자동 지정'은 웹 생성 창에서만 처리된다(서버 기본값 아님). MCP로 만든 태스크에는 고객사가 비어 웹과 결과가 다르다 | `TaskCreateDialog.tsx:585-600`, `projects/models.py:56` |
| A5 | **태스크 번호와 id 혼동** | 숫자를 넘기면 항상 내부 id로 본다. "850번"을 `850`으로 넘기면 #850(id 19608)이 아닌 id 850의 다른 태스크를 연다. `#850`은 서버 번호 검색(#793)에 우연히 걸려 동작할 뿐 안내가 없다 | `server.py:727-730`, `tasks/search.py:13-24` |

### B. 미지원 기본 기능

| # | 기능 | 현재 | 서버 API |
|---|------|------|----------|
| B1 | **하위 태스크 연결/해제** (기존 태스크를 상위 아래로) | update_task(parent=) 단건만 가능, 안내 없음. 여러 개 한 번에 연결·해제 불가 | PATCH `parent` / `bulk_update` (멤버도 상·하위 지정 가능, #718) |
| B2 | **연관 태스크 연결/해제** (관련·차단·차단됨) | 읽기만 가능 | `/api/tasks/links/`, `links/bulk_create/` (같은 워크스페이스 다른 프로젝트 가능, #784) |
| B3 | **태그 추가·빼기 / 태그로 검색** | 없음 (A1과 짝) | `tag_ids`, `bulk_update.add_tags/remove_tags`(#836), 목록 `tags` 필터 |
| B4 | **주간 회의 공유·VDC 공유·영문 제목** | 생성·수정·조회 모두 없음 | 필드 `is_report_task`(#672·#829), `needs_vdc_share`, `title_en` |
| B5 | **검색 범위 지정** (전체·제목+내용·댓글·번호) | 없음 | `search_scope`(#825) |
| B6 | 프로젝트 이동 | 없음 | `move_project`, `move_preview` |
| B7 | 일괄 변경 (여러 태스크 상태·담당자 등) | 없음 | `bulk_update` |
| B8 | 첨부파일 조회·업로드 | 없음 | `tasks/{id}/attachments/` |
| B9 | 알림 구독(지켜보기)·끄기 | 없음 | `tasks/{id}/watch/` |
| B10 | 변경 이력 조회 | 없음 | `/api/tasks/histories/` |
| B11 | 댓글 반응(이모지) | 없음 | `reactions/toggle/` |
| B12 | 커스텀 필드 값 | 없음 | `/api/tasks/custom-fields/` |
| B13 | 고객 접수 / 건의→태스크 등록(#728) | 없음 | `customers/*`, suggestions |
| B14 | GitHub 이슈 발행·연결 | PR 연결만 있음 | `tasks/{id}/github-issue/` (POST·PATCH) |
| B15 | 댓글 수정 이력 조회·되돌리기 | 없음 | `mentions/{id}/history/`, `restore/{history_id}/` |
| B16 | 휴지통 영구 삭제·일괄 복구 | 단건 복구만 | `permanent-delete/`, `bulk-restore/`, `bulk-permanent-delete/` |
| B17 | 엑셀 내보내기 | 없음 | `tasks/export/` |

### C. 태스크 밖 기능 (2차 전수조사 — 백엔드 14개 앱 · 프론트 화면 전체 대조)

플러그인이 다루는 범위는 태스크·댓글·휴지통·PR 연결·알림/멘션 조회·건의(제출·조회)·고객사 이름 해석뿐이다. 아래는 모두 **미지원**.

| # | 기능 (화면) | 서버 API | 비고 |
|---|-------------|----------|------|
| C1 | **주간 업무** (weekly-sync, 한눈에 보기) | `dashboard/weekly-sync/`(`view=buckets`, `start_date`, `my_projects_only`), `weekly-activity/` | weekly-sync는 워크스페이스 관리자 이상만. 저번주/이번주/리스크/날짜 미정 버킷(#741) |
| C2 | **캘린더** (통합 보기) | `dashboard/calendar/` | 태스크·고객 이슈(계획 종료일) + 일정·예약(기간)을 날짜별로 |
| C3 | **일정** 조회·등록·수정·삭제 | `/api/schedules/` | 워크스페이스 단위, 종일/시각·참석자·프로젝트 연결 |
| C4 | **리소스 예약** 조회·예약·변경·취소 | `/api/reservations/`, `resources/` | 과거·12주 초과 불가, 수량·참석자 |
| C5 | 대시보드 요약 | `dashboard/summary/`, `overview/`, `task-trends/` | 집계 조회 |
| C6 | 공지사항 조회·읽음 | `/api/announcements/`, `unread-count/`, `read/`, `mark-read/` | |
| C7 | 알림 읽음 처리 | `notifications/{id}/read/`, `read-all/` | 플러그인은 조회만 |
| C8 | 건의 댓글·수정·삭제 | `suggestions/comments/`, PATCH/DELETE | 플러그인은 제출·조회만 |
| C9 | 고객 접수 조회·등록·태스크 전환 | `customers/issues/`, `customers/{id}/issues/…/convert/` | B13과 동일 |
| C10 | AI 요약 조회·생성 | `ai/summaries/tasks/{id}/` | |

제외(관리자·설정 화면이라 MCP 대상 아님): 시스템 설정·백업·삭제 파일, 워크스페이스/프로젝트 설정(상태·우선순위·태그 정의·권한·멤버·초대·웹훅·사이드바·분류), GitHub 설치, 회원가입·비밀번호 찾기.

## 수행 계획 (제안 — 범위 확인 필요)

**1차 (권장)**: A1~A5 + B1~B5

1. A1·B3 태그
   - get_project_enums에 프로젝트 태그 목록 추가 (프로젝트 상세에 이미 포함 → 추가 호출 없음)
   - create_task `tags`(이름 또는 id), update_task `tags`(통째 교체)·`add_tags`·`remove_tags` → 현재 태그와 합쳐 `tag_ids` 전송. 다른 프로젝트 태그·없는 이름은 호출 전 차단
   - search_tasks `tags` 필터, 잘못된 안내문 정정
2. A2 고정: is_pinned는 현재 값과 다를 때만 `pin` 액션 호출 (서버 상한·숨김 규칙 적용)
3. A3 건의 라벨에 `answered: 답변완료` 추가
4. A4 create_task: customer를 안 넘기면 웹과 같은 조건(비WBS·자동 지정 켬·고객사 보임)에서 프로젝트 고객사 지정
5. A5 `#850` 형식을 번호로 명시 해석 (현재 프로젝트 기준), 안내문에 id/번호 구분 기재
6. B1 `link_subtasks(parent, children)` / 해제 — 여러 건은 bulk_update 1회 호출
7. B2 `link_tasks(source, targets, link_type)` / `unlink_task` — bulk_create 1회 호출, 해제는 get_task의 연관 목록에서 link id 확인
8. B4 create/update/get에 `is_report_task`·`needs_vdc_share`·`title_en` 노출
9. B5 search_tasks에 `search_scope` 추가
10. pytest(순수 로직: 태그 이름 해석·병합, 번호 해석, 고객사 자동 지정 판정) + README 도구표·plugin.json 버전 갱신
11. (보완) 태스크 생성 경로가 2곳이다 — `task_from_doc`도 직접 POST하므로 A4 고객사 자동 지정을 공용 헬퍼로 두 경로에 함께 적용
12. (보완) 목록·검색 결과 요약(`_task_summary`)에 태그·주간 회의 공유 표시 추가 — 없으면 태그로 검색해도 결과에 태그가 안 보인다
13. (보완) 프롬프트·커맨드 정합 — `gdc-apply` ③ 하위 태스크는 지금 "새로 만들기"만 안내하므로 기존 태스크를 하위로 붙이는 경로(B1) 안내 추가, `gdc-task-new` 등에 태그 지정 안내(사용자가 말할 때만)
14. (보완) WBS 하위 연결 검증 — 상위 변경 시 서버의 비중 초기화·진행률 롤업·형제 비중 합 100 규칙이 일괄 변경(bulk_update) 경로에서도 같은지 46 WBS 테스트에서 확인

**최종 검토 반영 (2026-11-25, 서버 코드 대조)**
- B1 해제: 일괄 변경은 `parent=null`을 거부한다(`BulkUpdateFieldsSerializer.parent` null 불가) → 연결은 bulk_update 1회, **해제는 하위마다 PATCH `parent: null`** (상위만 바꾸는 요청은 멤버도 허용, #718)
- A1 태그: 단건 수정은 bulk의 add_tags 대신 현재 `tag_list`와 합쳐 `tag_ids`를 **같은 PATCH에** 실어 보낸다(다른 필드와 한 번에·추가/빼기 동시 가능)
- A2 고정: `pin` 액션은 하위 태스크·숨긴 태스크·5개 초과를 400으로 막는다 → 서버 문구를 그대로 안내. is_pinned만 바꾸면 PATCH는 생략
- A5 번호: `#N`은 현재 프로젝트에서 `search=#N`(번호 정확 일치)로 해석. update_task도 `#N`·제목을 받도록 확장(숫자만 넘겨 엉뚱한 태스크를 고치는 사고 방지)
- B4: 웹과 같이 VDC 공유·영문 제목은 **WBS 프로젝트에서 차단**

**2차**: C1 주간 업무 → C2·C3 캘린더/일정 → C4 리소스 예약 → B6 프로젝트 이동 · B7 일괄 변경 · B13/C9 고객 접수

**2차 설계 (2026-11-25, 서버 코드 대조)**

| 기능 | 도구 | 서버 API · 주의점 |
|------|------|------------------|
| 주간 업무 | `get_weekly_sync` | `dashboard/weekly-sync/?view=buckets` — **워크스페이스 관리자 이상 전용**(403 안내). 기본은 현재 프로젝트만 추려 표시, `all_projects`로 전체. 담당자 필터는 클라이언트 |
| 캘린더 | `get_calendar` | `dashboard/calendar/` — 응답이 날짜별로 펼쳐져 있어 항목(key) 단위로 접어 기간 표시. sources(태스크·고객 이슈·일정·예약) |
| 일정 | `create_schedule` / `update_schedule` / `delete_schedule` | `/api/schedules/` — 종류(외근·휴가·외부 일정), 종일/시각, 참석자는 **워크스페이스 멤버** 이름 해석. 삭제는 confirm 게이트 |
| 리소스 예약 | `list_resources` / `list_reservations` / `create_reservation` / `update_reservation` / `cancel_reservation` | `/api/reservations/` — 과거·12주 초과 불가, 409 충돌 목록, 반복(매일·매주·2주·매월), 반복 건 수정·취소 범위(one/series). 서버 오류 코드(past·too_far·inactive·disabled·ended)를 한글 안내로 |
| 프로젝트 이동 | `move_task_project` | `move_preview` + `move_project` — 번호 재발급·태그 전부 제거·비멤버 담당자 해제·없는 상태값은 기본값. WBS는 출발·도착 모두 불가. **confirm 게이트**(미리보기에 영향 표시) |
| 일괄 변경 | `bulk_update_tasks` | `bulk_update`(task_ids+fields, 최대 100) — 태그는 이름으로 add/remove, 태스크별 부분 적용(updated/failed) |
| 고객 접수 | `list_customer_issues` / `get_customer_issue` / `create_customer_issue` / `convert_issue_to_task` | `customers/issues/`(워크스페이스 전체, `#N` 번호 검색) · `customers/{id}/issues/` · `…/convert/`(새 태스크 또는 기존 태스크 연결, replace). 유형·상태·우선순위는 워크스페이스 설정 코드(`issue-types` 등)로 해석 |

슬래시 커맨드·프롬프트는 신설하지 않는다(자연어 호출 도구 — 기존 관례).

**제외 (사용자 결정 2026-11-25)**: B8 첨부파일, B9 알림 구독, B10 변경 이력, B11 댓글 반응, B12 커스텀 필드, B13 중 건의→태스크 등록, B14 GitHub 이슈, B15 댓글 수정 이력, B16 휴지통 영구 삭제·일괄 복구, B17 엑셀 내보내기, C5 대시보드, C6 공지, C7 알림 읽음 처리, C8 건의 댓글, C10 AI 요약

## 작업 결과

- [x] 1. 태그 지정·검색 (A1·B3)
- [x] 2. 고정 pin 액션 경유 (A2)
- [x] 3. 건의 '답변완료' 라벨 (A3)
- [x] 4. 고객사 자동 지정 (A4)
- [x] 5. 태스크 번호 해석 (A5)
- [x] 6. 하위 태스크 연결/해제 (B1)
- [x] 7. 연관 태스크 연결/해제 (B2)
- [x] 8. 주간 회의 공유·VDC 공유·영문 제목 필드 (B4)
- [x] 9. 검색 범위 (B5)
- [x] 10. pytest·README·버전 — 신규 52건 포함 285 passed, README 도구표, v0.10.0
- [x] 11. task_from_doc 고객사 자동 지정
- [x] 12. 목록·검색 결과에 태그·주간 회의 공유 표시
- [x] 13. 프롬프트·커맨드 안내 보강
- [x] 14. WBS 하위 연결 규칙 확인 — 일괄 연결 시 하위 비중 초기화·롤업 재계산 서버 처리 확인. 비중 합 0이면 상위 진행률 0(서버 정책, `tasks/wbs.py`) → 비중 재지정 시 롤업 정상(40%), 도구 안내문에 반영
- [x] 2차-1. 주간 업무 조회 (C1) — `get_weekly_sync`
- [x] 2차-2. 캘린더 조회·일정 등록/수정/삭제 (C2·C3) — `get_calendar`, `create/update/delete_schedule`
- [x] 2차-3. 리소스 예약 조회·예약/변경/취소 (C4) — `list_resources`, `list/create/update/cancel_reservation`
- [x] 2차-4. 프로젝트 이동 (B6) — `move_task_project`
- [x] 2차-5. 일괄 변경 (B7) — `bulk_update_tasks`
- [x] 2차-6. 고객 접수 조회·등록·태스크 전환 (B13/C9) — `list/get/create_customer_issue`, `convert_issue_to_task`
- [x] 2차 pytest — 36건 추가(321 passed)
- [x] 2차 로컬 사전 검증 — 운영 WS3(123·78) 31항목: 주간 업무(담당자·주 지정), 일정 생성·수정·종일/시각 차단·삭제 게이트, 예약(리소스 이름·참석자·충돌 안내·지난 시각 차단·매주 반복·수정·반복 전체 취소), 일괄 변경(#번호·한글 상태·주간 회의 공유·태그 추가/빼기·없는 태그 failed·담당자 비우기), 이동 차단(WBS·같은 프로젝트), 고객 접수(등록·검색·상세·WBS 차단·전환·재전환 차단). 29 PASS + **실제 결함 2건 발견·수정 후 재검증 PASS**: ① 캘린더 서버 key가 날짜마다 달라 여러 날 일정이 중복 → (종류, id)로 묶음 ② **고객 접수 번호는 고객사마다 따로**(#1이 고객사 3곳) — `#N`만으로 엉뚱한 접수를 고를 수 있어 여럿이면 customer 지정 요구. 정리: 임시 태스크·태그·일정·접수·리소스 삭제, 잔존 0. WS3 예약 기능은 검증 중에만 켰다가 원래 값(꺼짐)으로 복원. 일정·리소스는 서버가 소프트 삭제만 제공
- [x] 이동 성공 경로 추가 검증 — WS3에 임시 이슈관리 프로젝트를 만들어 10항목 PASS: 미리보기(확인 게이트·하위 1건·태그 제거 안내, 이동 안 함), 확정 이동(새 번호·하위 함께·상위 연결 유지·태그 제거), 상위 있으면 parent_action 요구, detach(단독 이동·상위 해제), keep_together(트리째 이동). 정리: 임시 태스크·태그 삭제, 임시 프로젝트 소프트 삭제 후 영구 삭제, 잔존 0
- [x] 로컬 사전 검증 — 운영 서버 WS3 테스트 워크스페이스(123 이슈관리·78 WBS, 사용자 승인). 읽기 전용 스모크 + 쓰기 29항목: 태그 지정·추가·빼기·교체·검색, 주간 회의 공유·VDC·영문 제목 저장/해제, 하위 연결(#번호·id 혼용)·순환 차단·해제, 연관 연결(차단)·중복 차단·양방향 끊기, 고정 pin 액션(하위 차단·멱등·해제), WBS VDC 차단·비중 초기화 — 28 PASS + 1건은 기대값 오류(WBS 롤업, 14번 참고) 후 재검증 PASS. 임시 태스크 7건·태그 2개 영구 삭제, 잔존 0. 저장 컨텍스트(WS6/30) 무변경(프로세스 내 지정)
- [x] 추가: 휴지통 복구(restore_task)도 `#N` 해석

## 참고 사항

- 서버 정책상 주간 업무는 워크스페이스 관리자 이상만 조회 가능 — 권한이 없으면 서버 문구로 안내된다

- **규칙과 실제 환경 불일치**: tasks.md의 검증 대상 'WS3([TEST] GDC 메인) 45·46'은 현재 인증된 운영 서버(gdc.gemiso.com)에 없다(404). 운영 WS3은 '[TEST] GDC 테스트용 워크스페이스'(78 WBS·123 이슈관리). 규칙 갱신 필요

- gdc-service 본체 변경 없음 (모두 기존 API로 가능)
- A2 관련: 서버 PATCH에 고정 상한 검사가 없는 것은 서버 쪽 결함이기도 하다 — 웹 외 다른 경로로도 우회 가능하므로 gdc-service에 별도 보고 필요
- update_task의 `tag_ids`는 서버에서 **통째 교체**다. 같은 요청에 본문 변경이 있으면 본문의 tagMention이 그 위에 더해진다
