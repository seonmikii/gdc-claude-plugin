# 작업 이력 인덱스

> 새 세션 시작 시 이 파일을 읽어 과거 작업 맥락을 파악합니다.
> 작업 완료 시 파일 맨 끝 `## 이력` 섹션 아래에 한 줄 추가합니다. (merge=union 전략 — conflict 없이 자동 병합되며, union은 항상 파일 끝에 누적하므로 이력 섹션을 파일 맨 끝에 둡니다)


## 유형 범례

- `feat` — 신규 기능
- `fix` — 버그 수정
- `refactor` — 리팩토링
- `ui` — UI/UX 개선
- `infra` — 인프라/설정
- `schema` — DB 스키마 변경

## 영역 범례

- `server/*` — 백엔드 (auth, api, convert, audit, workflow, license, ...)
- `ui/*` — 프론트엔드 (panel, content, admin, review, archive, collection, search, settings, i18n, ...)
- `db/*` — 데이터베이스 (schema, migration, ...)
- `infra/*` — 인프라 (docker, deploy, ...)


## 이력

<!-- 포맷: 날짜 | 유형 | 영역 | 상태 | 파일명 | 제목 -->
<!-- 예) 2026-03-27 | fix | server/auth | done | 2026-03/20260327-100000-auth-fix.md | 인증 토큰 만료 버그 수정  -->
<!-- 이 섹션은 항상 파일의 마지막 섹션이어야 합니다 (merge=union append 위치). 새 항목은 맨 아래에 추가하세요. -->

2026-06-26 | feat | server/api,commands | done | 2026-06/20260626-171539-task-doc-flow-rules.md | 태스크·문서 플로우 규칙 5종(메타 단계 제외·본문 sync·코드검토 선행·완료 자동보정·유형 자동매칭)
2026-06-29 | fix | server/api,commands | done | 2026-06/20260629-181949-task-meta-step-filter.md | task_from_doc [작업 내용] 빌드·검증 메타 단계 코드 필터(_strip_meta_steps) 추가 + 프롬프트 강화
2026-07-06 | infra | infra/config | done | 2026-07/20260706-165536-prod-server-switch.md | 기본 연결 대상을 운영 서버(https://gdc.gemiso.com)로 변경 (.mcp.json·README·rules, v0.1.11)
2026-07-16 | fix | infra/mcp | done | 2026-07/20260716-151731-sac-block-fix.md | Windows SAC 차단 해결 — 서명 없는 gdc-mcp shim 대신 python -m gdc_mcp.server 기동으로 전환 (.mcp.json·hooks, v0.1.12)
2026-07-20 | feat | server/api | done | 2026-07/20260720-150845-update-task-full-edit-fields.md | create/update_task 편집 필드 UI 동등화 — weight(WBS 가드)·customer 이름 해석·clear_fields 해제·create 확장 (v0.2.0)
2026-07-20 | feat | server/api | done | 2026-07/20260720-161506-list-customers-tool.md | list_customers 도구 추가 — 현재 워크스페이스 고객사 목록 조회(검색 옵션), customer 이름 지정 보조 (v0.2.1)
2026-07-20 | feat | commands,infra/config | done | 2026-07/20260720-164556-ship-update-command.md | 플러그인 업데이트 커맨드 레포 내장(/gdc-update) — install 승격 버그 해결, README 업데이트 섹션 교체·수동 폴백 명시 (v0.2.2)
2026-07-21 | feat | server/task_from_doc,doc_utils,commands | partial | 2026-07/20260721-095435-task-from-doc-improvement.md | task_from_doc description를 GDC 리치텍스트(HTML)로 변환(라벨 볼드·블렛·섹션간격·이스케이프, description_to_html) + 생성 전 미리보기·단일 확인 게이트 — 1단계(파일럿), Phase 4(전체경로 통일) 후속 (v0.2.3)
2026-07-21 | fix | commands,docs | done | 2026-07/20260721-113348-gdc-update-vscode-fix.md | /gdc-update VSCode 확장 대응 — claude CLI 미존재(command not found) 시 command -v 감지 후 /plugins GUI 안내로 분기, README 폴백 추가 (v0.2.3)
2026-07-21 | refactor | server/create_task·update_task·sync,doc_utils | partial | 2026-07/20260721-112819-unify-html-description.md | description HTML 변환을 공통 레이어(normalize_description, HTML 자동 감지→통과/평문→변환)로 승격 — create/update_task·sync_doc_progress·task_from_doc 일관 적용, gdc_task_new 라벨 템플릿 확대, SKILL.md 삭제 대비 자립·delink (2단계, v0.2.4)
2026-07-22 | feat | server/api | done | 2026-07/20260722-151259-task-comment-tools.md | 태스크 댓글(Mention) MCP 도구 4종 추가 — list/add/update/delete_task_comment, @멘션 username 해석·본문 선두 주입, html_to_text 평문 변환, 본인만 수정·삭제(403→ValueError) (v0.2.5)
2026-07-22 | feat | commands/gdc-doc-from-task | done | 2026-07/20260722-172518-doc-from-task-comment-reflect.md | doc-from-task 문서 생성 시 태스크 댓글(list_task_comments) 조회·②기획 정리 반영 — 커맨드+MCP 프롬프트 1:1 동시 반영, 댓글 0개/20개초과 지침 명문화, 테스트 프로젝트로 소비 단계 E2E 검증 (v0.2.6)
2026-07-23 | fix | server/doc_utils,server | done | 2026-07/20260723-094319-progress-round-to-10.md | 진행률 10% 단위 반올림 동기화 — _round_progress 헬퍼 추가(도구·훅 공유 _apply_progress_sync 경계 반올림), raw>=100일 때만 완료·100 전송(95~99%→90% 조기완료 방지), 상태전이는 raw 기준, pytest+실서버 검증 (v0.2.7)
2026-07-23 | feat | server/get_task·api,commands | done | 2026-07/20260723-111007-subtask-related-task-query.md | 하위/연관 태스크 조회 기능(#346) — get_task에 parent·sub_tasks·related_tasks(방향 유지) 노출(_task_summary/_parent_summary/_related_tasks, 상세 API 1회 재사용·추가 왕복 0), task_id를 int|str로 확장해 제목 해석(_resolve_task, 현재 프로젝트 한정), /gdc-task 커맨드+gdc_task 프롬프트 추가, WS3/46 E2E 검증 PASS·원복 (v0.3.0)
2026-07-23 | feat | server/edit_task_description·doc_utils,commands | done | 2026-07/20260723-143718-task-edit-reflect-improvement.md | 문서 변경의 태스크 반영 개선(#345) — edit_task_description 신규도구(append_work/replace_section, get_task→최소편집→PATCH raw HTML로 인라인 이미지 보존), 라벨섹션 순수헬퍼(split_label_sections·append_work_bullets·replace_label_section·label_section_has_media)+pytest 19건, replace_section 이미지 유지/삭제 keep_media 분기(유지 시 섹션 끝 재삽입), /gdc-apply 커맨드+프롬프트(추가작업/내용변경 분류→질문→라우팅), 기존 sync_doc_progress full-replace 유도 프롬프트를 최소편집으로 리다이렉트, WS3/45 실서버 검증·원복 (v0.4.0)

2026-07-23 | chore | commands/gdc-apply,server | done | 2026-07/20260723-143718-task-edit-reflect-improvement.md | 커맨드/프롬프트명 변경 /gdc-reflect→/gdc-apply, gdc_reflect→gdc_apply (직관적 명칭, v0.4.1)
2026-07-24 | feat | server/gdc_mcp | partial | 2026-07/20260724-095833-task-hide-delete.md | 태스크 숨기기(archive 토글)·삭제(soft-delete 휴지통) MCP 도구 추가 계획 — 서버 API 조사(권한 can_manage_project/task_visibility·403 한글변환·WBS 연쇄), 범위 확정=숨기기+삭제(soft)+복구+휴지통목록(영구삭제·show_archived 제외) (문서 생성, #407)
2026-07-24 | feat | server/gdc_mcp | done | 2026-07/20260724-095833-task-hide-delete.md | 태스크 숨기기·삭제·복구·휴지통 MCP 도구 4종 추가(archive_task·delete_task·restore_task·list_trashed_tasks) — 세 동작 confirm 게이트(미리보기→재확인→실행), 제목 int|str 해석, 숨김해제·삭제는 _resolve_task(show_archived) 내부 보완, trash는 project 명시 스코프, 403/400(wbs_archive_disabled·parent_archived)/404 한글변환, WBS 복구=최상위 분리·하위 미복구 명시, WS3/45·46 E2E 검증·pytest 95 회귀없음 (v0.5.0)

2026-07-24 | feat | server/doc_utils | done | 2026-07/20260724-114402-html-autolink.md | HTML 변환시 URL 자동 연동(#409) — description_to_html에 _escape_and_linkify 추가(비-URL은 escape, http/https 맨 URL만 <a target=_blank rel=noopener href>로, 뒤 문장부호 제외), 블렛·일반줄에 적용→description·댓글(normalize_description 공유) 양쪽 반영, 라벨 [..]은 순수escape 유지. 태스크언급 #번호→id는 REST필요→(A)서버계층 후속분리. TDD 6건 추가 pytest 102통과, WS3/45 로컬코드 직접호출+실태스크 PATCH로 GDC <a>보존 검증(검증태스크 유지), v0.6.0

2026-07-28 | feat | server/doc_utils,server | done | 2026-07/20260728-102213-task-mention-autolink.md | 태스크 언급(#N) 자동 링크 연동(#409 후속) — _escape_and_linkify에 resolve_task 콜백+_MENTION_RE((?<![\w#])#(\d+)), 비-URL 구간만 처리해 URL프래그먼트 오탐 차단, #N만 링크+뒤에 (제목) 평문. 서버 _task_resolver: 번호 필터 부재(gdc-service TaskFilter/BM25 실증)→-number 목록 page_size=200·최대5p 스캔 매핑(미해결/상한/실패는 평문), 5개 normalize_description 호출부 연결·무언급 시 REST 0. TDD 9건 추가 pytest 111통과, WS45 실서버 댓글 라운드트립으로 #N 앵커·(제목)·미해결평문 보존 검증(댓글 42666 유지), v0.6.1

2026-07-28 | feat | commands/gdc-link-task,server | partial | 2026-07/20260728-112056-link-task-apply-integration.md | /gdc-link-task 연동 후 태스크 본문 반영 연결 계획(#410) — link_task_to_doc은 frontmatter만 기록(태스크 PATCH 없음) 확인, 반영은 비대화형 도구가 아닌 커맨드/프롬프트 오케스트레이션 계층에서 get_task 비교→질문→/gdc-apply 라우팅(반영 안 함 선택지 포함), 통째 덮어쓰기 금지·진행률은 /gdc-sync 유지 (문서 생성)

2026-07-28 | feat | commands/gdc-link-task,server | done | 2026-07/20260728-112056-link-task-apply-integration.md | /gdc-link-task 연동 후 문서 내용 반영 연결(#410) — 도구(link_task_to_doc)는 그대로 두고 커맨드/프롬프트 오케스트레이션에 3~4단계 추가(get_task 본문 확보→항목 단위 비교→미반영 시 2지선다 게이트 '지금 반영/연동만'→/gdc-apply 절차 위임), 반영 위치는 apply에서만 물어 중복 질문 제거. 절차 복사 대신 _apply_steps(include_fetch,prefix)+_APPLY_HEAD 공유 헬퍼로 gdc_apply·gdc_link_task 문구 단일화(4곳 드리프트 차단), 삽입 시 prefix="4-"로 바깥 1~5단계와 번호 충돌 방지, 빈 본문은 append_work 라벨 블록 신설·통째 덮어쓰기 금지·진행률은 /gdc-sync 유지 명시. pytest 112 회귀없음, WS3/45 임시 태스크(#15476)+임시 문서로 연동→append_work 반영(기존 항목 보존·진행률 0 유지) 검증·삭제·컨텍스트 WS6/16 복원, v0.6.2

2026-07-28 | feat | server/gdc_mcp | partial | 2026-07/20260728-141423-comment-mention-span.md | 댓글 멘션을 평문 대신 하이라이트 span(볼드+강조색, 배경 chip은 tag-mention 쪽 스타일)으로 삽입 계획 — 현재 _build_comment_html이 <p>@username</p> 평문으로 붙여 알림은 가나(백엔드가 @뒤 토큰을 username 컬럼과 매칭) 프론트가 멘션으로 재인식하지 않음(span[data-type=mention]만 .mention 렌더). 개선: _resolve_mention_usernames가 full_name까지 반환→prefix를 <span data-type=mention class=mention data-id=username data-label=full_name>@username</span>로 교체, 속성·내부 텍스트 html.escape. 이메일 username은 data-id 내부 @가 정규식에 추가 캡처되나 무해. server.py만 변경(서버·프론트 무변경). 구현·검증 대기 (문서 생성)

2026-07-28 | fix | server/gdc_mcp | partial | 2026-07/20260728-143355-html-detection-and-template-guidance.md | 본문 HTML 오판 수정 + 태스크 생성 도구 라벨 템플릿 안내 계획 — 평문 문장 속 리터럴 태그(예: `평문 <p>@user</p>만 붙는다`)가 _HTML_TAG_RE.search에 걸려 is_html=True→normalize_description이 변환을 건너뛰어 본문이 한 덩어리로 저장됨(#417 실측). is_html을 선두 앵커링(선행 공백 제거 후 match)으로 좁히고, 템플릿 안내가 없는 5곳(create_task·update_task·sync_doc_progress docstring, _apply_steps ③ 하위 태스크, gdc-apply.md)에 라벨 섹션 규격 명시. normalize 경유 5개 호출부 모두 태그로 시작하는 HTML만 넘겨 회귀 없음(기존 통과 테스트 3건 확인). 별건 이관 2건: append_work 블렛 자동링크 미적용, _strip_meta_steps가 task_from_doc 전용. 구현·검증 대기 (문서 생성)

2026-07-28 | fix | server/gdc_mcp | done | 2026-07/20260728-143355-html-detection-and-template-guidance.md | 본문 HTML 오판 수정 + 태스크 생성 도구 라벨 템플릿 안내(#417) — is_html을 `search`→**선두 앵커링**(`match(text.lstrip())`)으로 좁혀 문장 중간 리터럴 태그(`평문 <p>@user</p>만 붙는다`)가 변환을 건너뛰던 결함 해소(정규식 자체는 유지), normalize_description의 '오판 가능(희귀)' 주의문도 새 규칙으로 교체. 템플릿 안내 없던 5곳 보강 — create_task(템플릿 블록 전문)·update_task(요약+'통째 교체이므로 부분 수정은 edit_task_description' 경고)·sync_doc_progress docstring, _apply_steps ③ 하위 태스크 + commands/gdc-apply.md:15(gdc-doc-from-task.md:15 표현과 통일, /gdc-link-task는 프롬프트 헬퍼 공유+커맨드 위임으로 자동 반영·중복 문구 없음 확인). pytest 3건 추가(추가 직후 2건 실패 확인 후 구현) 115 passed 회귀0, WS3/45·46 양쪽 실서버 라운드트립으로 라벨 볼드+블렛 변환·태그 `&lt;p&gt;` 이스케이프 보존·태그로 시작하는 HTML 통과 확인, 임시 태스크 6건 삭제·잔존0·컨텍스트 WS6/16 복원, README 도구표 갱신, v0.6.3

2026-07-28 | feat | server/gdc_mcp | done | 2026-07/20260728-141423-comment-mention-span.md | 댓글 멘션을 하이라이트 span으로 삽입 — `_resolve_mention_usernames`가 `(username, full_name)` 쌍 반환(by_id·by_name 양쪽, full_name 없으면 username 폴백), `_mention_span` 신설로 `<span data-type="mention" class="mention" data-id data-label>@username</span>`을 `<p>` 문단에 선두 삽입(속성 순서 고정 — 웹훅 `_tiptap_to_plain`이 data-type→data-label 쌍따옴표 요구, 어긋나면 `@표시이름`→`@username` 열화). 속성·텍스트 `html.escape(quote=True)`, server.py에 `import html` 추가하며 지역변수 `html`→`body` 개명. 도구 docstring 3곳+모듈 주석도 평문→하이라이트 기준으로 수정. TDD 4건 추가(폴백·속성순서·escape·#N 공존) 119 passed, WS3/45 로컬코드 직접호출로 전송=저장 바이트 동일·`mentioned_users_detail` 1명(이메일 username의 @gmail.com 추가 캡처 무해 실증)·수정 경로 span 유지·평문 변환 회귀 확인, 임시 태스크·댓글 삭제 잔존0·컨텍스트 WS6/16 복원, v0.6.4

2026-07-28 | feat | server/gdc_mcp | done | 2026-07/20260728-164433-search-detail-mention-tools.md | 태스크 검색·상세 필드 보강·알림/멘션 조회 도구 추가(#419·#420·#421) — ① `search_tasks` 신설(키워드+상태/우선순위/유형/담당자/관련자/고객사/종료일 범위, 파라미터 조립은 순수 헬퍼 `_search_params`로 분리). 착수 전 서버 대조에서 7건 교정: BM25 관련도 정렬이 `TaskViewSet.ordering=["-number"]`에 항상 덮여 "관련도순 아님"(docstring 명시+`total_matched` 동봉), `query`+`root_only`는 매칭 하위 유실이라 배타 차단, `overdue`는 서버 필터(`planned_end_date_to`)로 옮기되 `not_finished`와 직교 유지, `undated`는 200건 선취, 컨텍스트 미설정 시 차단. 완료 포함이 기본(목록 도구와 반대 규약, docstring 명시). ② 프로젝트 상세 60초 TTL 캐시 `_project` 신설(+`set_context` 무효화)로 13개 GET 지점 통합 — `get_task`+`get_project_enums`x2가 프로젝트 상세 2회→1회. `get_task`에 누락 13종(실제 날짜·관련자·작성자·고객사·비중·고정·숨김·태그·댓글 수·생성/수정 시각) 추가(추가 왕복 0). 검증 중 서버가 `tag_ids`를 무시함을 확인(`TaskSerializer.create/update`가 pop 후 미사용, 태그는 `tagMention` 스캔으로만 동기화)해 `create_task`/`update_task`에서 파라미터 제거. ③ `list_my_notifications`(유형 7종 한글 라벨, 미읽음 필터, `unread-count` 동봉, 전 워크스페이스 혼재 명시)·`list_my_mentions`(컨텍스트 스코프, 20건 고정 페이지 순회, 잘린 HTML 꼬리 제거 후 평문화) 신설 — 읽음 처리는 미노출. pytest 50건 추가 167 passed 회귀0, WS3/45 실호출 검증(검색·캐시 왕복 0회·알림/멘션 조회, participants·tags는 임시 지정 후 전량 원복·잔존0, 컨텍스트 WS6/16 무변경), 커맨드/프롬프트는 신설 안 함(자연어 호출), v0.7.0
