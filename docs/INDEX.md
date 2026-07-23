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
