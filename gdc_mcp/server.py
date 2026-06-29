"""gdc MCP 서버 (엔진 ① 독립형, stdio).

gdc-service REST API를 Claude Code의 MCP 도구로 노출한다. 인증은 브라우저 핸드오프 전용.
도구: gdc_login / get_context / set_context / list_workspaces / list_projects /
      get_project_enums / list_my_tasks / create_task / update_task / get_task /
      open_task / link_task_to_doc / sync_doc_progress / task_from_doc
"""

from __future__ import annotations

import datetime
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import Context, FastMCP

from . import tokens
from .client import GdcClient, NotAuthenticatedError
from .handoff import browser_handoff, open_in_chrome
from .doc_utils import (
    compute_phase_progress,
    extract_title,
    read_frontmatter,
    read_metadata_table,
    upsert_frontmatter,
)

load_dotenv()

mcp = FastMCP("gdc-local")
client = GdcClient()

_TASKS = "/api/tasks/tasks/"

# 사용자에게 보여줄 링크는 백엔드(API)가 아니라 프론트엔드(웹) 주소여야 한다.
_WEB_URL = os.environ.get("GDC_WEB_URL", "http://localhost:5173").rstrip("/")


def _task_url(task_id: int) -> str:
    return f"{_WEB_URL}/tasks/{task_id}"


# --- 레포(루트)별 컨텍스트 ------------------------------------------------------
# Claude Code(클라이언트)가 MCP roots로 알려주는 현재 워크스페이스 폴더를 키로
# 워크스페이스/프로젝트를 분리한다. roots를 못 받으면 글로벌 fallback을 쓴다.


async def _current_root(ctx: Context | None) -> str | None:
    """클라이언트가 알려준 현재 루트(레포 폴더) 경로. roots 미지원이면 None."""
    if ctx is None:
        return None
    try:
        roots = await ctx.list_roots()
    except Exception:
        return None
    if not roots:
        return None
    return tokens.normalize_root(str(roots[0].uri))


async def _resolve_context(ctx: Context | None) -> dict:
    """현재 루트의 워크스페이스/프로젝트 컨텍스트(없으면 글로벌 fallback)."""
    root = await _current_root(ctx)
    return tokens.load_context(root)


# 프론트 i18n(status.task / priority / taskType)과 동일한 한글 라벨.
# 백엔드는 기본값을 영문 코드로 저장하므로 선택지를 한글로 보여주기 위해 매핑한다.
# 사용자가 임의 추가한 커스텀 값(보통 한글 name)은 매핑에 없으면 name을 그대로 노출
# → 프론트의 t('...{name}', name) 폴백과 동일 동작. (i18n 키 변경 시 함께 갱신)
_STATUS_LABELS = {
    "open": "등록", "in_progress": "진행", "review": "검토",
    "resolved": "해결", "closed": "완료",
}
_PRIORITY_LABELS = {"low": "낮음", "medium": "보통", "high": "높음", "urgent": "긴급"}
_TASKTYPE_LABELS = {
    "internal_meeting": "내부 회의", "external_meeting": "외부 회의",
    "planning": "기획", "development": "개발", "design": "디자인",
    "cs": "CS", "other": "기타",
}

_me_cache: dict = {}


def _current_user_id() -> int | None:
    """로그인 사용자 id를 조회(캐시). 담당자 자동 등록 등에 사용."""
    if "id" not in _me_cache:
        try:
            _me_cache["id"] = client.get("/api/accounts/users/me/").json().get("id")
        except Exception:
            return None
    return _me_cache["id"]


@mcp.tool
async def gdc_login(ctx: Context) -> dict:
    """브라우저 핸드오프(A안)로 MCP 전용 토큰을 발급받고, 선택한 워크스페이스/프로젝트를
    **현재 레포(루트)별로** 저장한다.

    브라우저 창이 열리면 평소처럼 로그인(Google·로컬 모두 가능)한 뒤 '연결 허용'을 누른다.
    인증 토큰은 사용자 단위로 공유되고, 워크스페이스/프로젝트는 이 레포에만 적용된다.
    → 레포마다 한 번씩 gdc_login하면 레포별로 다른 프로젝트를 자동으로 쓴다.
    """
    handoff = browser_handoff(_WEB_URL)
    client.set_tokens(handoff["access"], handoff["refresh"])
    root = await _current_root(ctx)
    tokens.save_context(root, handoff.get("workspace_id"), handoff.get("project_id"))
    return {
        "logged_in": True,
        "base_url": client.base_url,
        "method": "browser-handoff",
        "root": root or "(roots 미수신 → 글로벌 컨텍스트로 저장)",
        "workspace_id": handoff.get("workspace_id"),
        "project_id": handoff.get("project_id"),
    }


@mcp.tool
async def get_context(ctx: Context) -> dict:
    """현재 레포(루트)에 적용되는 워크스페이스/프로젝트 컨텍스트를 반환한다.

    create_task/list 등에서 어떤 프로젝트가 쓰일지 확인하는 용도. roots 미지원 환경에서는
    글로벌 fallback 값을 반환한다.
    """
    root = await _current_root(ctx)
    c = tokens.load_context(root)
    project_name = None
    if c.get("project_id"):
        try:
            project_name = client.get(f"/api/projects/{c['project_id']}/").json().get("name")
        except Exception:
            project_name = None
    return {
        "root": root,
        "roots_supported": root is not None,
        "workspace_id": c.get("workspace_id"),
        "project_id": c.get("project_id"),
        "project_name": project_name,
    }


@mcp.tool
def list_workspaces() -> dict:
    """현재 사용자가 접근 가능한 워크스페이스 목록(전환용)."""
    data = client.get("/api/workspaces/").json()
    items = data.get("results", []) if isinstance(data, dict) else data
    return {"workspaces": [{"id": w["id"], "name": w.get("name")} for w in items]}


@mcp.tool
def list_projects(workspace_id: int) -> dict:
    """지정 워크스페이스의 프로젝트 목록(전환용)."""
    data = client.get("/api/projects/", params={"workspace": workspace_id, "page_size": 100}).json()
    items = data.get("results", []) if isinstance(data, dict) else data
    return {"projects": [{"id": p["id"], "name": p.get("name")} for p in items]}


@mcp.tool
async def set_context(ctx: Context, workspace_id: int, project_id: int) -> dict:
    """현재 레포의 워크스페이스/프로젝트를 전환한다(재인증 없이, 토큰 유지).

    이미 로그인된 상태에서 작업 대상 프로젝트만 바꿀 때 사용한다.
    """
    root = await _current_root(ctx)
    tokens.save_context(root, workspace_id, project_id)
    project_name = None
    try:
        project_name = client.get(f"/api/projects/{project_id}/").json().get("name")
    except Exception:
        project_name = None
    return {
        "root": root or "(global)",
        "workspace_id": workspace_id,
        "project_id": project_id,
        "project_name": project_name,
    }


@mcp.tool
def get_project_enums(project_id: int) -> dict:
    """프로젝트별 커스텀 status/priority/task_type enum을 조회한다.

    status는 category(planned/in_progress/done)를 포함한다.
    완료 상태 = category=='done', 미완료 상태 = 그 보집합.
    태스크 생성/수정/필터 전에 유효한 값과 '미완료 집합'을 확인하는 용도.
    """
    p = client.get(f"/api/projects/{project_id}/").json()
    statuses = [
        {
            "name": s["name"],
            "label": _STATUS_LABELS.get(s["name"], s["name"]),
            "category": s.get("category"),
        }
        for s in p.get("task_statuses", [])
    ]
    return {
        "project_id": project_id,
        "project_name": p.get("name"),
        "workspace": p.get("workspace"),
        "statuses": statuses,
        "done_status_names": [s["name"] for s in statuses if s["category"] == "done"],
        "not_finished_status_names": [s["name"] for s in statuses if s["category"] != "done"],
        "priorities": [
            {"name": x["name"], "label": _PRIORITY_LABELS.get(x["name"], x["name"])}
            for x in p.get("task_priorities", [])
        ],
        "task_types": [
            {"name": x["name"], "label": _TASKTYPE_LABELS.get(x["name"], x["name"])}
            for x in p.get("task_types", [])
        ],
        "members": [
            {"id": m.get("user"), "name": m.get("full_name") or m.get("username")}
            for m in p.get("members", [])
        ],
    }


def _not_finished_names(project_id: int) -> list[str]:
    p = client.get(f"/api/projects/{project_id}/").json()
    return [s["name"] for s in p.get("task_statuses", []) if s.get("category") != "done"]


def _finalize_task_list(results: list[dict], overdue: bool, undated: bool, limit: int) -> dict:
    """태스크 목록에 overdue/undated 클라이언트 필터를 적용하고 표시용 형태로 정리한다."""
    if overdue:
        today = datetime.date.today().isoformat()
        results = [t for t in results if t.get("planned_end_date") and t["planned_end_date"] < today]
    if undated:
        results = [t for t in results if not t.get("planned_end_date")]
    results = results[:limit]
    return {
        "count": len(results),
        "tasks": [
            {
                "id": t["id"],
                "number": t.get("number"),
                "title": t.get("title"),
                "project_name": t.get("project_name"),
                "project": t.get("project"),
                "status": t.get("status"),
                "status_label": _STATUS_LABELS.get(t.get("status"), t.get("status")),
                "priority": t.get("priority"),
                "priority_label": _PRIORITY_LABELS.get(t.get("priority"), t.get("priority")),
                "progress": t.get("progress"),
                "planned_end_date": t.get("planned_end_date"),
                "assignee_name": t.get("assignee_name"),
                "url": _task_url(t["id"]),
            }
            for t in results
        ],
    }


@mcp.tool
async def list_my_tasks(
    ctx: Context,
    not_finished: bool = True,
    overdue: bool = False,
    undated: bool = False,
    limit: int = 20,
) -> dict:
    """현재 사용자(assignee/creator/participant)의 태스크 목록을 조회한다.

    조회 대상 프로젝트는 **현재 레포에서 gdc_login으로 선택한 프로젝트**(레포별 컨텍스트)로 고정된다.
    그 프로젝트의 미완료 집합으로 **서버측 필터링**하므로 정확하다.
    저장된 프로젝트가 없으면 부득이 mine 전체에서 클라이언트 필터링한다(첫 페이지만 보므로 누락 가능).
    - not_finished=True: 완료(category=='done')가 아닌 상태만
    - overdue=True: 계획 종료일이 지난 것만
    - undated=True: **계획 종료일이 없는(날짜 미정) 것만** (주간 싱크의 '날짜 미정'과 동일)
    """
    project_id = (await _resolve_context(ctx)).get("project_id")
    # overdue/undated는 클라이언트 필터라, 마감일순 첫 페이지에 묻히지 않도록 넉넉히 가져온다
    fetch_size = 200 if (overdue or undated) else limit
    params: dict[str, str | int] = {"mine": "true", "ordering": "planned_end_date", "page_size": fetch_size}
    if project_id is not None:
        params["project"] = project_id
        if not_finished:
            params["status"] = ",".join(_not_finished_names(project_id))

    results = client.get(_TASKS, params=params).json().get("results", [])

    if not_finished and project_id is None:
        cache: dict[int, set[str]] = {}
        kept = []
        for t in results:
            pid = t.get("project")
            if pid not in cache:
                cache[pid] = set(_not_finished_names(pid)) if pid else set()
            if t.get("status") in cache[pid]:
                kept.append(t)
        results = kept

    return _finalize_task_list(results, overdue, undated, limit)


@mcp.tool
async def list_tasks(
    ctx: Context,
    assignee: int | str,
    not_finished: bool = True,
    overdue: bool = False,
    undated: bool = False,
    limit: int = 20,
) -> dict:
    """특정 담당자의 태스크를 현재 레포 프로젝트에서 조회한다.

    assignee는 user id **또는 멤버 이름**(full_name/username) — 자동으로 id로 해석한다.
    조회 프로젝트는 현재 레포에서 gdc_login으로 저장한 프로젝트로 고정한다(미설정 시 오류).
    필터는 list_my_tasks와 동일: not_finished(미완료만)/overdue(마감 지남)/undated(날짜 미정).
    "내" 태스크는 list_my_tasks를, 특정 담당자는 이 도구를 쓴다.
    """
    project_id = (await _resolve_context(ctx)).get("project_id")
    if project_id is None:
        raise ValueError("프로젝트가 설정되지 않았습니다. gdc_login으로 프로젝트를 선택하세요.")
    assignee_id, _ = _resolve_members(project_id, assignee, None)
    fetch_size = 200 if (overdue or undated) else limit
    params: dict[str, str | int] = {
        "assignee": assignee_id,
        "project": project_id,
        "ordering": "planned_end_date",
        "page_size": fetch_size,
    }
    if not_finished:
        params["status"] = ",".join(_not_finished_names(project_id))
    results = client.get(_TASKS, params=params).json().get("results", [])
    return _finalize_task_list(results, overdue, undated, limit)


# --- 입력 검증 (백엔드 차단 전 미리 안내) ---------------------------------------


def _parse_date(value: str, label: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError(f"{label}은(는) YYYY-MM-DD 형식이어야 합니다: {value!r}")


def _validate_dates(
    planned_start: str | None = None,
    planned_end: str | None = None,
    actual_start: str | None = None,
    actual_end: str | None = None,
) -> None:
    """날짜 순서·미래 제약 검증(전달된 값끼리만 비교; 미전달 항목은 백엔드가 저장값과 대조)."""
    if planned_start and planned_end and _parse_date(planned_start, "예상 시작일") > _parse_date(planned_end, "예상 종료일"):
        raise ValueError(f"예상 시작일({planned_start})은 예상 종료일({planned_end})보다 늦을 수 없습니다.")
    if actual_start and actual_end and _parse_date(actual_start, "실제 시작일") > _parse_date(actual_end, "실제 종료일"):
        raise ValueError(f"실제 시작일({actual_start})은 실제 종료일({actual_end})보다 늦을 수 없습니다.")
    if actual_end and _parse_date(actual_end, "실제 종료일") > datetime.date.today():
        raise ValueError(
            f"실제 종료일({actual_end})은 미래 날짜로 지정할 수 없습니다 (오늘: {datetime.date.today().isoformat()})."
        )


def _resolve_members(
    project_id: int, assignee: int | str | None, participant_ids: list[int | str] | None
) -> tuple[int | None, list[int] | None]:
    """담당자/관련자(user id 또는 이름)를 user id로 해석·검증한다.

    둘 다 없으면 조회를 생략하고 원본을 반환한다. 멤버가 아니거나 못 찾으면 ValueError로 안내.
    """
    if assignee is None and not participant_ids:
        return assignee, participant_ids

    members = client.get(f"/api/projects/{project_id}/").json().get("members", [])
    ids = {m.get("user") for m in members}
    by_name: dict[str, int] = {}
    for m in members:
        for nm in (m.get("full_name"), m.get("username")):
            if nm:
                by_name[str(nm).strip().lower()] = m.get("user")

    def resolve(value: int | str, label: str) -> int:
        # 정수(또는 정수 문자열) → id, 그 외 문자열 → 이름으로 매칭
        if not isinstance(value, bool) and (isinstance(value, int) or str(value).strip().isdigit()):
            uid = int(value)
            if uid in ids:
                return uid
        else:
            uid = by_name.get(str(value).strip().lower())
            if uid is not None:
                return uid
        valid = ", ".join(
            f"{(m.get('full_name') or m.get('username'))}(id={m.get('user')})" for m in members
        )
        raise ValueError(
            f"{label} '{value}'은(는) 이 프로젝트의 멤버가 아닙니다. 가능한 멤버: {valid or '(없음)'}"
        )

    r_assignee = resolve(assignee, "담당자") if assignee is not None else None
    r_parts = [resolve(p, "관련자") for p in participant_ids] if participant_ids else participant_ids
    return r_assignee, r_parts


@mcp.tool
def create_task(
    project: int,
    title: str,
    status: str | None = None,
    priority: str | None = None,
    task_type: str | None = None,
    assignee: int | str | None = None,
    description: str | None = None,
    planned_start_date: str | None = None,
    planned_end_date: str | None = None,
    participant_ids: list[int | str] | None = None,
) -> dict:
    """태스크를 생성한다. 필수: project(프로젝트 ID), title.

    [입력 수집 권장 흐름 — Desktop·Code 공통]
    호출 전에 사용자에게 컬럼을 **선택지로 하나씩 물어보고** 고른 값을 넘긴다:
    1) get_context로 현재 프로젝트 확인 → get_project_enums로 status/priority/task_type/members 조회.
    2) 제목·내용(description)·예상 시작/종료일만 **자유 입력**으로 받는다.
    3) status/priority/task_type/관련자는 **선택 질문(AskUserQuestion)**으로 제시 — 보기는 한글 label,
       각 질문에 반드시 "건너뛰기" 포함(실제 값 최대 3개, 나머지는 "기타"로). 고른 값의 name(관련자는 user id)을 넘긴다.
    4) 담당자(assignee)는 묻지 않는다(생략 시 로그인 사용자로 자동 등록 = 작성자와 동일).

    값 형식: status/priority/task_type은 해당 프로젝트 enum의 'name', 날짜는 'YYYY-MM-DD'.
    assignee·participant_ids는 user id **또는 멤버 이름**(full_name/username)을 넘기면 자동으로 id로 해석한다.

    제약(미충족 시 호출 전 ValueError로 안내·차단): 예상 시작일 ≤ 예상 종료일,
    담당자/관련자는 해당 프로젝트 멤버만 지정 가능.

    완료 보정: status가 완료 계열(category=='done')이면 progress=100·실제 종료일=오늘을 자동 주입한다.
    """
    _validate_dates(planned_start_date, planned_end_date)
    assignee, participant_ids = _resolve_members(project, assignee, participant_ids)  # id 또는 이름
    if assignee is None:
        assignee = _current_user_id()
    fields: dict = {
        "project": project,
        "title": title,
        "status": status,
        "priority": priority,
        "task_type": task_type,
        "assignee": assignee,
        "description": description,
        "planned_start_date": planned_start_date,
        "planned_end_date": planned_end_date,
        "participant_ids": participant_ids,
    }
    # 완료 상태로 생성 시 진행률/실제 종료일 자동 보정
    if status and _status_category(project, status) == "done":
        fields["progress"] = 100
        fields["actual_end_date"] = datetime.date.today().isoformat()
    payload = {k: v for k, v in fields.items() if v is not None}
    t = client.request("POST", _TASKS, json=payload).json()
    return {
        "id": t["id"],
        "number": t.get("number"),
        "title": t.get("title"),
        "project_name": t.get("project_name"),
        "status": t.get("status"),
        "status_label": _STATUS_LABELS.get(t.get("status"), t.get("status")),
        "url": _task_url(t["id"]),
    }


@mcp.tool
def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    task_type: str | None = None,
    assignee: int | str | None = None,
    progress: int | None = None,
    planned_start_date: str | None = None,
    planned_end_date: str | None = None,
    actual_start_date: str | None = None,
    actual_end_date: str | None = None,
    customer: int | None = None,
    parent: int | None = None,
    is_pinned: bool | None = None,
    tag_ids: list[int] | None = None,
    participant_ids: list[int | str] | None = None,
) -> dict:
    """태스크를 부분 수정(PATCH)한다. 전달한 필드만 갱신된다.

    사용자가 수정 권한을 가진 모든 편집 필드를 노출한다(읽기전용 id/number/creator 제외).
    status/priority/task_type은 해당 프로젝트 enum 'name'(get_project_enums로 확인),
    날짜는 'YYYY-MM-DD', customer/parent는 ID, tag_ids는 ID 리스트.
    assignee·participant_ids는 user id **또는 멤버 이름**(full_name/username)을 넘기면 자동으로 id로 해석한다.
    완료 상태(category=='done')로 전환하면 백엔드가 progress=100·actual_end_date를 자동 보정할 수 있다.

    제약(미충족 시 ValueError로 안내·차단): 예상/실제 시작일 ≤ 종료일, 실제 종료일은 미래 불가,
    담당자/관련자는 해당 프로젝트 멤버만 지정 가능.
    """
    _validate_dates(planned_start_date, planned_end_date, actual_start_date, actual_end_date)
    if assignee is not None or participant_ids:
        project_id = client.get(f"{_TASKS}{task_id}/").json().get("project")
        assignee, participant_ids = _resolve_members(project_id, assignee, participant_ids)  # id 또는 이름
    payload = {
        k: v
        for k, v in {
            "title": title,
            "description": description,
            "status": status,
            "priority": priority,
            "task_type": task_type,
            "assignee": assignee,
            "progress": progress,
            "planned_start_date": planned_start_date,
            "planned_end_date": planned_end_date,
            "actual_start_date": actual_start_date,
            "actual_end_date": actual_end_date,
            "customer": customer,
            "parent": parent,
            "is_pinned": is_pinned,
            "tag_ids": tag_ids,
            "participant_ids": participant_ids,
        }.items()
        if v is not None
    }
    if not payload:
        raise ValueError("수정할 필드를 하나 이상 전달하세요.")
    t = client.request("PATCH", f"{_TASKS}{task_id}/", json=payload).json()
    return {
        "id": t["id"],
        "title": t.get("title"),
        "project_name": t.get("project_name"),
        "status": t.get("status"),
        "status_label": _STATUS_LABELS.get(t.get("status"), t.get("status")),
        "progress": t.get("progress"),
        "actual_end_date": t.get("actual_end_date"),
        "url": _task_url(t["id"]),
    }


@mcp.tool
def open_task(task_id: int) -> dict:
    """태스크 웹 화면을 Chrome 새 탭으로 연다.

    목록에 표시되는 URL을 클릭하면 VSCode 내장 브라우저로 열릴 수 있으므로,
    이 도구는 chrome.exe를 직접 실행해 항상 Chrome으로 연다(미설치 시 기본 브라우저).
    """
    url = _task_url(task_id)
    opened = open_in_chrome(url)
    return {"opened": opened, "url": url, "browser": "chrome" if opened else "default"}


def _status_category(project_id: int | None, status_name: str | None) -> str | None:
    """프로젝트에서 status name의 category(planned/in_progress/done)를 찾는다."""
    if not project_id or not status_name:
        return None
    for s in client.get(f"/api/projects/{project_id}/").json().get("task_statuses", []):
        if s.get("name") == status_name:
            return s.get("category")
    return None


@mcp.tool
def get_task(task_id: int) -> dict:
    """태스크 상세를 조회한다(작업 요청 문서 생성·연동용).

    제목/내용/상태/우선순위/유형/날짜/진행률/담당자 등 문서 작성에 필요한 필드를 반환한다.
    """
    t = client.get(f"{_TASKS}{task_id}/").json()
    return {
        "id": t["id"],
        "number": t.get("number"),
        "title": t.get("title"),
        "description": t.get("description"),
        "project": t.get("project"),
        "project_name": t.get("project_name"),
        "status": t.get("status"),
        "status_label": _STATUS_LABELS.get(t.get("status"), t.get("status")),
        "status_category": _status_category(t.get("project"), t.get("status")),
        "priority": t.get("priority"),
        "priority_label": _PRIORITY_LABELS.get(t.get("priority"), t.get("priority")),
        "task_type": t.get("task_type"),
        "task_type_label": _TASKTYPE_LABELS.get(t.get("task_type"), t.get("task_type")),
        "progress": t.get("progress"),
        "planned_start_date": t.get("planned_start_date"),
        "planned_end_date": t.get("planned_end_date"),
        "assignee_name": t.get("assignee_name"),
        "url": _task_url(t["id"]),
    }


@mcp.tool
def link_task_to_doc(doc_path: str, task_id: int) -> dict:
    """기존 태스크를 기존 작업 요청 문서와 연동한다.

    문서 frontmatter에 task_id/task_url을 기록(upsert)하므로, 이후 sync_doc_progress·훅이
    이 문서의 Phase/체크박스 진행률을 해당 태스크에 동기화한다. (새 태스크를 만들지 않음)
    """
    t = client.get(f"{_TASKS}{task_id}/").json()  # 존재 확인
    path = Path(doc_path)
    text = path.read_text(encoding="utf-8")
    url = _task_url(task_id)
    new_text = upsert_frontmatter(text, {"task_id": str(task_id), "task_url": url})
    path.write_text(new_text, encoding="utf-8")
    return {
        "linked": True,
        "task_id": task_id,
        "title": t.get("title"),
        "url": url,
        "doc": str(path),
    }


def _apply_progress_sync(task_id: int, new_progress: int, description: str | None = None) -> dict:
    """진행률을 PATCH하면서 상태/실제 날짜 전이를 함께 적용한다.

    - 최초 진행(0 → 0 초과): 상태를 '진행'(in_progress, planned→만)으로, 실제 시작일을 오늘로(미설정 시).
    - 100% 달성: 상태를 '완료'(done 계열)로, 실제 종료일을 오늘로(미설정 시).
    - description 전달 시: 같은 PATCH에 태스크 본문(description)도 함께 반영(명시 sync 전용; 훅은 미전달).
    프로젝트 상태 목록은 한 번만 조회해 재사용한다.
    """
    cur = client.get(f"{_TASKS}{task_id}/").json()
    project_id = cur.get("project")
    statuses = client.get(f"/api/projects/{project_id}/").json().get("task_statuses", [])
    cat_of = {s["name"]: s.get("category") for s in statuses}

    def _pick(category: str, preferred: tuple[str, ...]) -> str | None:
        cand = [s for s in statuses if s.get("category") == category]
        for s in cand:
            if s["name"].lower().replace(" ", "") in preferred:
                return s["name"]
        return cand[0]["name"] if cand else None

    old_progress = cur.get("progress") or 0
    cur_cat = cat_of.get(cur.get("status"))
    today = datetime.date.today().isoformat()
    payload: dict = {"progress": new_progress}
    if description is not None:
        payload["description"] = description

    if old_progress == 0 and new_progress > 0 and not cur.get("actual_start_date"):
        payload["actual_start_date"] = today

    if new_progress >= 100:
        done = _pick("done", ("완료", "완료됨", "completed", "done", "closed", "종료"))
        if done and cur.get("status") != done:
            payload["status"] = done
        if not cur.get("actual_end_date"):
            payload["actual_end_date"] = today
    elif new_progress > 0 and cur_cat not in ("in_progress", "done"):
        ip = _pick("in_progress", ("inprogress", "진행", "진행중"))
        if ip:
            payload["status"] = ip

    return client.request("PATCH", f"{_TASKS}{task_id}/", json=payload).json()


@mcp.tool
def sync_doc_progress(doc_path: str, task_id: int | None = None, description: str | None = None) -> dict:
    """작업 요청 문서의 Phase 진척을 읽어 연결된 태스크 진행률·상태·실제 날짜를 동기화한다.

    progress = 완료 Phase 수 / 전체 Phase 수 × 100 (한 Phase는 하위 체크박스가
    전부 [x]일 때 완료). task_id 생략 시 문서 frontmatter의 task_id를 사용한다.
    최초 진행 시 '진행'+실제 시작일, 100% 시 '완료'+실제 종료일로 자동 전이된다.
    description 전달 시 진행률 PATCH에 태스크 본문(description)도 함께 반영한다 —
    문서 본문이 수정됐을 때 호출 에이전트가 '[작업 내용]' 요약을 재생성해 넘기는 용도(자동 훅은 진행률 전용).
    """
    text = Path(doc_path).read_text(encoding="utf-8")
    if task_id is None:
        fm = read_frontmatter(text)
        if not fm.get("task_id"):
            raise ValueError("task_id가 없습니다. 인자로 전달하거나 문서 frontmatter에 task_id를 기록하세요.")
        task_id = int(fm["task_id"])

    result = compute_phase_progress(text)
    t = _apply_progress_sync(task_id, result["progress"], description)
    out = {
        "task_id": task_id,
        "mode": result["mode"],
        "progress": t.get("progress"),
        "status": t.get("status"),
        "status_label": _STATUS_LABELS.get(t.get("status"), t.get("status")),
        "actual_start_date": t.get("actual_start_date"),
        "actual_end_date": t.get("actual_end_date"),
        "url": _task_url(task_id),
    }
    if result["mode"] == "phase":
        out["done_phases"] = result["done_phases"]
        out["total_phases"] = result["total_phases"]
        out["phases"] = [{"title": p["title"], "done": p["done"]} for p in result["phases"]]
    else:
        out["checked_checkboxes"] = result["checked_checkboxes"]
        out["total_checkboxes"] = result["total_checkboxes"]
    return out


def _done_status_name(project_id: int) -> str | None:
    """프로젝트의 '완료' 상태 name을 찾는다.

    category=='done' 중 name이 '완료'/'completed'/'done'/'closed'/'종료' 등
    완료 계열인 것을 우선('해결'/resolved보다 우선), 없으면 첫 done 상태.
    문서 메타데이터 상태가 done일 때 매핑 대상.
    """
    statuses = client.get(f"/api/projects/{project_id}/").json().get("task_statuses", [])
    done = [s for s in statuses if s.get("category") == "done"]
    preferred = ("완료", "완료됨", "completed", "done", "closed", "종료")
    for s in done:
        if s["name"].lower().replace(" ", "") in preferred:
            return s["name"]
    return done[0]["name"] if done else None


def _in_progress_status_name(project_id: int) -> str | None:
    """프로젝트의 '진행'(진행 중) 상태 name을 찾는다.

    category=='in_progress' 중 name이 '진행'/'진행중'/'in progress'인 것을 우선,
    없으면 첫 in_progress 상태. 문서 메타데이터 상태가 partial일 때 매핑 대상.
    """
    statuses = client.get(f"/api/projects/{project_id}/").json().get("task_statuses", [])
    inprog = [s for s in statuses if s.get("category") == "in_progress"]
    for s in inprog:
        if s["name"].lower().replace(" ", "") in ("inprogress", "진행", "진행중"):
            return s["name"]
    return inprog[0]["name"] if inprog else None


# [작업 내용] 블렛에서 걸러낼 프로세스 메타 단계 키워드(빌드·검증·테스트·이력 등).
# 에이전트가 프롬프트 지침을 어기고 메타 단계를 넣어도 도구 레벨에서 제거한다.
_META_STEP_RE = re.compile(
    r"빌드|build|타입\s*체크|type\s*check|\btsc\b|검증|verif|"
    r"테스트|\btest|lint|린트|커밋|\bcommit|푸시|\bpush|"
    r"index\.md|이력\s*추가|동작\s*확인|정상\s*동작|npm\s+run",
    re.IGNORECASE,
)


def _strip_meta_steps(description: str) -> str:
    """description의 '[작업 내용]' 블렛 중 프로세스 메타 단계를 제거한다.

    '[작업 내용]' 헤더 이후의 `-`/`*` 블렛만 검사하며, 메타 키워드(빌드/검증/테스트/
    lint/커밋/이력 추가/동작 확인 등)에 걸리는 줄을 드롭한다. 그 외 줄(요약·실제 산출물
    단계)은 그대로 둔다. 진행 상태는 태스크 progress 필드가 담당하므로 메타는 본문에서 뺀다.
    """
    in_work = False
    out: list[str] = []
    for line in description.splitlines():
        if line.strip().startswith("[작업 내용]"):
            in_work = True
            out.append(line)
            continue
        if in_work and re.match(r"^\s*[-*]\s+", line):
            content = re.sub(r"^\s*[-*]\s+", "", line)
            if _META_STEP_RE.search(content):
                continue  # 메타 단계 블렛 제거
        out.append(line)
    return "\n".join(out)


@mcp.tool
async def task_from_doc(
    ctx: Context,
    doc_path: str,
    description: str,
    project: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    task_type: str | None = None,
) -> dict:
    """작업 요청 문서로 태스크를 생성하고, 문서 frontmatter에 task_id/task_url을 기록한다.

    - 제목: 문서의 첫 '# ' 헤딩에서 추출.
    - description(필수): 호출하는 에이전트가 아래 템플릿으로 작성해 전달한다(태스크 본문으로 저장):
        작업 문서의 "요청 내용" 한 줄 요약

        [작업 내용]
        - 작업 결과 단계를 블렛(`-`)으로 간단히 요약 (각 단계 한 줄)
        ※ 체크박스 표시(`[ ]`/`[x]`)는 넣지 않는다. 진행 상태는 태스크 progress 필드가 담당한다.
        ※ 빌드·타입체크·검증·테스트·lint·커밋·배포/동작 확인·'INDEX.md 이력 추가' 같은
          프로세스 메타 단계는 넣지 않는다(실제 산출물 단계만). 넣더라도 도구가 자동 제거한다.
    - status: 생략 시 문서 메타데이터 표의 `상태`를 보고 매핑한다 —
      **done → '완료'(완료/closed 계열)**, **partial → '진행'(in_progress)**.
      그 외 값은 자동 매핑하지 않고 기본 상태로 둔다. status 인자를 주면 그 값이 우선한다.
    - 완료 보정: 최종 status가 완료 계열(category=='done')이면 progress=100·실제 종료일=오늘을 자동 주입한다.
    - task_type: 호출하는 에이전트가 문서 유형/본문을 근거로 프로젝트 enum에 맞춰 매칭해 전달한다(get_project_enums 참고).
    - project: 생략 시 현재 레포에서 gdc_login으로 저장한 프로젝트(레포별 컨텍스트)를 사용.
    - 담당자(assignee): 항상 로그인 사용자로 자동 등록(create_task와 동일).
    """
    path = Path(doc_path)
    text = path.read_text(encoding="utf-8")

    fm = read_frontmatter(text)
    if fm.get("task_id"):
        return {
            "already_linked": True,
            "task_id": int(fm["task_id"]),
            "url": fm.get("task_url") or _task_url(int(fm["task_id"])),
        }

    description = _strip_meta_steps(description)  # 메타 단계 블렛 방어적 제거

    title = extract_title(text)
    if not title:
        raise ValueError("문서에서 제목(첫 '# ' 헤딩)을 찾지 못했습니다.")

    if project is None:
        project = (await _resolve_context(ctx)).get("project_id")
    if project is None:
        raise ValueError(
            "project를 결정할 수 없습니다. gdc_login으로 프로젝트를 선택해 저장하거나 project 인자를 전달하세요."
        )

    # 문서 상태 매핑 (status 인자가 없을 때만): done→해결, partial→진행
    if status is None:
        doc_status = read_metadata_table(text).get("상태", "").strip().lower()
        if doc_status == "done":
            status = _done_status_name(project)
        elif doc_status in ("partial", "in_progress", "in progress", "진행", "진행중"):
            status = _in_progress_status_name(project)

    fields: dict = {
        "project": project,
        "title": title,
        "description": description,
        "status": status,
        "priority": priority,
        "task_type": task_type,
        "assignee": _current_user_id(),  # 기본 담당자 = 로그인 사용자
    }
    # 완료 상태로 생성 시 진행률/실제 종료일 자동 보정
    if status and _status_category(project, status) == "done":
        fields["progress"] = 100
        fields["actual_end_date"] = datetime.date.today().isoformat()
    payload = {k: v for k, v in fields.items() if v is not None}
    t = client.request("POST", _TASKS, json=payload).json()
    url = _task_url(t["id"])
    new_text = upsert_frontmatter(text, {"task_id": str(t["id"]), "task_url": url})
    path.write_text(new_text, encoding="utf-8")
    return {
        "id": t["id"],
        "number": t.get("number"),
        "title": t.get("title"),
        "status": t.get("status"),
        "url": url,
        "doc_updated": True,
    }


# --- 프롬프트(슬래시 커맨드) — Claude Desktop·Code 양쪽에서 사용 -------------------
# Claude Code에서는 /mcp__gdc-local__gdc_* 로, Desktop에서는 "+" 메뉴로 노출된다.


@mcp.prompt
def gdc_login() -> str:
    """GDC 브라우저 핸드오프 인증/재인증 (워크스페이스·프로젝트 선택)."""
    return (
        "`gdc_login` 도구를 호출해 브라우저 핸드오프 인증을 실행하세요. "
        "브라우저 창이 열리면 평소처럼 로그인(Google/로컬) 후 워크스페이스·프로젝트를 선택하고 "
        "'연결 허용'을 누릅니다. 완료되면 인증 성공 여부와 base_url, 이 레포에 저장된 "
        "워크스페이스/프로젝트를 보고하세요.\n\n"
        "참고: 인증(계정)은 모든 레포에서 공유되지만, 선택한 워크스페이스/프로젝트는 현재 레포에만 "
        "적용됩니다. 레포마다 다른 프로젝트를 쓰려면 각 레포에서 한 번씩 실행하세요. "
        "(응답의 root가 비어 있으면 클라이언트가 roots 미지원이라 글로벌로 저장된 것입니다.)"
    )


@mcp.prompt
def gdc_switch() -> str:
    """현재 레포의 워크스페이스/프로젝트 전환 (재인증 없이)."""
    return (
        "현재 레포의 작업 대상 워크스페이스/프로젝트를 전환합니다(브라우저 재인증 없음, 토큰 유지).\n"
        "1. `list_workspaces`로 워크스페이스 목록을 가져와 선택 질문으로 고르게 합니다. "
        "보기는 4개까지이므로 초과 시 대표 3개 + '기타'(Other)로 나머지를 입력하게 합니다.\n"
        "2. 고른 워크스페이스로 `list_projects(workspace_id)`를 호출해 프로젝트를 선택 질문으로 고릅니다(동일 규칙).\n"
        "3. `set_context(workspace_id, project_id)`로 현재 레포 컨텍스트를 갱신합니다.\n"
        "4. 전환된 워크스페이스/프로젝트(이름)와 적용 레포(root)를 보고합니다."
    )


@mcp.prompt
def gdc_my_tasks(flags: str = "") -> str:
    """내 미해결 태스크 조회. flags 예: '--overdue', '--undated', '--all'."""
    return (
        f"`list_my_tasks` 도구로 내 미해결 태스크를 마감 임박순으로 조회하세요. 옵션: {flags or '(없음)'}\n"
        "- `--overdue`→overdue=true(마감 지난 것), `--undated`→undated=true(날짜 미정: 계획 종료일 없는 것), "
        "`--all`→not_finished=false(완료 포함).\n"
        "조회 프로젝트는 현재 레포에 저장된 프로젝트로 고정됩니다.\n"
        "결과는 번호/제목/상태/마감일/URL 표로 보여주되, 상태·우선순위는 응답의 `status_label`·`priority_label`(한글), "
        "프로젝트는 `project_name`(ID 대신)을 씁니다. 특정 태스크를 열어달라고 하면 `open_task(task_id)`로 Chrome 새 탭에 엽니다."
    )


@mcp.prompt
def gdc_tasks(assignee: str = "", flags: str = "") -> str:
    """특정 담당자의 태스크 조회. assignee=이름 또는 user id, flags 예: '--overdue' '--undated' '--all'."""
    return (
        f"`list_tasks` 도구로 특정 담당자의 태스크를 마감 임박순으로 조회하세요. 담당자: {assignee or '(필수: 이름 또는 user id)'} / 옵션: {flags or '(없음)'}\n"
        "- assignee 인자에 멤버 이름(예: 김철수) 또는 user id를 그대로 넘기면 도구가 자동으로 id로 해석합니다.\n"
        "- `--overdue`→overdue=true, `--undated`→undated=true, `--all`→not_finished=false(완료 포함).\n"
        "조회 프로젝트는 현재 레포에 저장된 프로젝트로 고정됩니다. 비멤버 이름이면 도구가 가능한 멤버 목록을 안내합니다.\n"
        "결과 표기는 list_my_tasks와 동일(번호/제목/상태/마감일/URL, 한글 label·project_name). 특정 태스크는 `open_task`로 엽니다."
    )


@mcp.prompt
def gdc_task_new(request: str = "") -> str:
    """새 태스크 생성 (선택 목록·한글·담당자 자동)."""
    return (
        f"새 태스크를 생성합니다. 사용자 입력: {request or '(없음)'}\n\n"
        "원칙:\n"
        "- 자유 입력은 제목·내용(description)·예상 시작일·예상 종료일 뿐. 상태/우선순위/업무유형/관련자는 선택 목록으로 고릅니다.\n"
        "- 담당자는 묻지 않습니다(로그인 사용자로 자동 등록).\n"
        "- ⚠️ 모든 선택 질문에 반드시 '건너뛰기' 보기를 포함(생략 금지). 실제 값 보기는 최대 3개, 나머지는 '기타(Other)'로.\n\n"
        "절차:\n"
        "1. `get_context`로 현재 레포의 project_id 확인(없으면 gdc_login 안내).\n"
        "2. `get_project_enums(project_id)`로 status/priority/task_type/members(관련자 후보 id·name) 조회. "
        "보기는 한글 `label`, create_task에 넘길 값은 `name`. 목록은 프로젝트별 동적(커스텀 포함).\n"
        "3. 제목·내용을 입력에서 받거나 한 번 물어봅니다(자유 입력).\n"
        "4. status/priority/task_type/관련자를 선택 질문(AskUserQuestion)으로 한 호출에 함께 묻습니다. "
        "각 질문은 실제 값 최대 3개 + '건너뛰기', 나머지 값은 설명에 나열하고 '기타'로 입력하게 합니다. "
        "새 태스크는 미완료 상태(등록/진행/검토)를 우선 노출하고 완료 계열은 기타로. "
        "관련자는 members 이름으로 다중 선택 후 user id로 환산해 participant_ids로 넘깁니다.\n"
        "5. 예상 시작일/종료일은 자유 입력(YYYY-MM-DD, 생략 가능) → planned_start_date/planned_end_date.\n"
        "6. 건너뛴 항목은 생략하고 `create_task`로 생성, task_id·프로젝트명·URL을 보고합니다. "
        "완료 계열 상태(category=='done')를 고른 경우 progress=100·실제 종료일=오늘이 자동 보정되므로 별도 입력은 불필요합니다."
    )


@mcp.prompt
def gdc_task_from_doc(path: str = "") -> str:
    """작업 요청 문서로 태스크 생성."""
    return (
        f"지정한 작업 요청 문서로 태스크를 생성합니다. 경로: {path or '(생략 시 현재 docs/requests 문서)'}\n"
        "1. description을 템플릿에 맞춰 작성: 첫 줄 = 문서 '요청 내용' 한 줄 요약, 다음 '[작업 내용]' 아래 '작업 결과' 단계를 "
        "블렛(`-`)으로 간단히 요약(각 단계 한 줄). **체크박스 표시(`[ ]`/`[x]`)는 넣지 말 것** — 진행 상태는 progress 필드 담당. "
        "**빌드·타입체크·검증·테스트·lint·커밋·배포/동작 확인·'INDEX.md 이력 추가' 같은 프로세스 메타 단계는 본문에 넣지 말 것**"
        "(실제 산출물 단계만; 원본 문서 '작업 결과'에 그런 단계가 있어도 옮기지 않는다). 넣더라도 도구가 자동 제거한다.\n"
        "2. `get_project_enums(project_id)`로 `task_type` 목록을 조회해, 문서 메타표 `유형`+본문 내용에 가장 맞는 enum name을 "
        "`task_type` 인자로 넘깁니다(확실하지 않으면 생략).\n"
        "3. `task_from_doc` 도구 호출. project는 현재 레포 컨텍스트(gdc_login 저장값)에서 자동 결정됩니다. "
        "메타데이터 표의 `상태`는 자동 매핑: done→'완료', partial→'진행'. 완료 매핑 시 progress=100·실제 종료일=오늘이 자동 주입됩니다.\n"
        "4. 생성 결과(task_id/URL)와 문서 frontmatter 갱신 여부를 보고합니다."
    )


@mcp.prompt
def gdc_doc_from_task(task_id: str = "") -> str:
    """태스크 기반으로 작업 요청 문서 생성·연동."""
    return (
        f"태스크 ID {task_id or '(필수)'}를 기반으로 작업 요청 문서를 생성하고 그 태스크와 연동합니다.\n"
        f"1. `get_task({task_id})`로 상세(제목/내용/상태+category/우선순위/유형/날짜/진행률/URL)를 가져옵니다.\n"
        "2. **태스크 description을 그대로 옮기지 말 것.** 다음 순서로 작성합니다: "
        "①관련 코드 검토(태스크 내용에 해당하는 실제 코드/파일을 읽어 현황 파악) → ②기획 정리(요구사항·배경 명확화) → "
        "③개발 계획 수립(단계별 작업 항목) → ④문서 반영.\n"
        "3. `docs/requests/TEMPLATE.md` 형식으로 작성: 제목=태스크 제목, 메타표(날짜=오늘, 상태=status_category 매핑 "
        "done→done·in_progress→partial·그 외→partial, 유형/영역은 합리적으로), 요청 내용=②기획 정리 결과, 작업 결과=③개발 계획 체크리스트.\n"
        f"   문서 맨 위 frontmatter에 `task_id: {task_id}`, `task_url: <url>`을 기록해 연동합니다.\n"
        "4. 경로: `docs/requests/YYYY-MM/YYYYMMDD-HHmmss-<짧은설명>.md` (타임스탬프는 date 명령).\n"
        "5. `docs/INDEX.md` `## 이력`에 한 줄 추가. 6. 생성 경로와 task_id/URL을 보고합니다."
    )


@mcp.prompt
def gdc_link_task(task_id: str = "", doc_path: str = "") -> str:
    """기존 태스크를 기존 작업 요청 문서와 연동."""
    return (
        f"기존 태스크(ID {task_id or '(필수)'})를 이미 있는 작업 요청 문서와 연동합니다(새로 만들지 않음). "
        f"문서: {doc_path or '(생략 시 현재 docs/requests 문서)'}\n"
        "1. 문서 경로를 확정합니다.\n"
        f"2. `link_task_to_doc(doc_path, {task_id})`를 호출 → 문서 frontmatter에 task_id/task_url 기록.\n"
        "3. 연동 결과(task_id, 제목, URL, 문서 경로)를 보고합니다. 진행률을 바로 맞추려면 gdc_sync를 실행하세요."
    )


@mcp.prompt
def gdc_sync(path: str = "") -> str:
    """문서 진행률을 연결된 태스크에 강제 동기화."""
    return (
        f"`sync_doc_progress` 도구로 문서의 진행률을 연결된 태스크에 동기화하세요. "
        f"경로: {path or '(생략 시 현재 docs/requests 문서)'}\n"
        "문서 본문(요청 내용/작업 결과 단계)이 수정됐다면, '[작업 내용]' 요약(첫 줄 요청 요약 + 단계별 블렛, 체크박스 없이)을 "
        "재생성해 `sync_doc_progress`의 `description` 인자로 함께 넘겨 태스크 본문도 갱신하세요(진행률만 맞출 때는 생략).\n"
        "동기화 후 progress(%)와 상태 전이(진행/완료), 실제 시작/종료일을 보고하세요."
    )


def _cli_sync_doc(doc_path: str) -> None:
    """훅에서 호출되는 CLI 동기화. 미연결·미인증·오류 시 조용히 종료(exit 0).

    훅 에러 스팸을 막기 위해 어떤 실패도 stderr/예외로 전파하지 않는다.
    """
    try:
        text = Path(doc_path).read_text(encoding="utf-8")
    except OSError:
        return
    fm = read_frontmatter(text)
    task_id = fm.get("task_id")
    if not task_id:
        return  # 태스크에 연결되지 않은 문서 → 무동작
    try:
        result = compute_phase_progress(text)
        t = _apply_progress_sync(int(task_id), result["progress"])
        print(f"synced task {task_id}: progress={result['progress']}% status={t.get('status')}")
    except NotAuthenticatedError:
        return  # 미인증 → 조용히 종료
    except Exception:
        return  # 네트워크/HTTP 오류도 훅에서는 조용히


def _cli_hook_sync() -> None:
    """PostToolUse 훅 진입점. stdin의 훅 JSON에서 편집 파일을 읽어 조건부 동기화.

    docs/requests/**/*.md 만 대상으로 하고, 그 외/오류는 모두 조용히 종료(exit 0).
    """
    import json
    import sys

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return
    norm = str(file_path).replace("\\", "/")
    if "/docs/requests/" not in norm or not norm.endswith(".md"):
        return
    _cli_sync_doc(file_path)


def main() -> None:
    import sys

    argv = sys.argv[1:]
    if argv and argv[0] == "sync-doc":
        if len(argv) >= 2:
            _cli_sync_doc(argv[1])
        return
    if argv and argv[0] == "hook-sync":
        _cli_hook_sync()
        return
    if argv and argv[0] == "gdc-login":
        handoff = browser_handoff(_WEB_URL)
        client.set_tokens(handoff["access"], handoff["refresh"])
        # CLI는 루트를 모르므로 글로벌 컨텍스트로 저장(MCP 도구 gdc_login은 레포별 저장)
        tokens.save_context(None, handoff.get("workspace_id"), handoff.get("project_id"))
        print(
            f"authenticated (base_url={client.base_url}, "
            f"workspace_id={handoff.get('workspace_id')}, project_id={handoff.get('project_id')})"
        )
        return
    mcp.run()


if __name__ == "__main__":
    main()
