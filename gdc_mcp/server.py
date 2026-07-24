"""gdc MCP 서버 (엔진 ① 독립형, stdio).

gdc-service REST API를 Claude Code의 MCP 도구로 노출한다. 인증은 브라우저 핸드오프 전용.
도구: gdc_login / get_context / set_context / list_workspaces / list_projects /
      list_customers / get_project_enums / list_my_tasks / create_task / update_task /
      get_task / open_task / link_task_to_doc / sync_doc_progress / task_from_doc
"""

from __future__ import annotations

import datetime
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastmcp import Context, FastMCP

from . import tokens
from .client import GdcClient, NotAuthenticatedError
from .handoff import browser_handoff, open_in_chrome
from .doc_utils import (
    append_work_bullets,
    compute_phase_progress,
    extract_title,
    html_to_text,
    label_section_has_media,
    normalize_description,
    read_frontmatter,
    read_metadata_table,
    replace_label_section,
    upsert_frontmatter,
)

load_dotenv()

mcp = FastMCP("gdc-local")
client = GdcClient()

_TASKS = "/api/tasks/tasks/"
_MENTIONS = "/api/tasks/mentions/"

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
async def list_customers(ctx: Context, search: str | None = None) -> dict:
    """현재 레포 컨텍스트 워크스페이스의 고객사 목록을 조회한다.

    create_task/update_task의 customer를 이름으로 지정하기 전에 후보를 확인하는 용도.
    search를 주면 이름·대표자·담당자 이름으로 부분 검색한다(생략 시 전체).
    반환된 id 또는 name을 customer 인자로 넘기면 된다.

    권한(고객사 열람) 없는 워크스페이스는 서버가 빈 목록을 주므로 count=0이면
    고객사가 없거나 열람 권한이 없는 것이다.
    """
    workspace_id = (await _resolve_context(ctx)).get("workspace_id")
    if workspace_id is None:
        raise ValueError(
            "워크스페이스 컨텍스트가 없습니다. gdc_login 또는 set_context로 워크스페이스를 선택하세요."
        )
    params: dict[str, str | int] = {"workspace": workspace_id, "page_size": 100}
    if search:
        params["search"] = search
    data = client.get(_CUSTOMERS, params=params).json()
    items = data.get("results", []) if isinstance(data, dict) else data
    return {
        "workspace_id": workspace_id,
        "count": len(items),
        "customers": [
            {
                "id": c["id"],
                "name": c.get("name"),
                "primary_contact_name": c.get("primary_contact_name") or None,
            }
            for c in items
        ],
        "hint": None if items else "결과 없음 — 고객사 미존재이거나 이 워크스페이스 고객사 열람 권한이 없습니다.",
    }


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


def _task_summary(t: dict) -> dict:
    """태스크(목록/하위/연관 항목)를 표시용 요약 dict로 압축한다.

    list_tasks·get_task의 하위/연관 태스크 등 여러 곳에서 동일한 요약 형태를 재사용한다.
    입력은 TaskListSerializer 계열 필드(id·number·title·project*·status·priority·progress
    ·planned_end_date·assignee_name)를 가진 dict를 가정한다.
    """
    return {
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
        "tasks": [_task_summary(t) for t in results],
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
    project_id: int,
    assignee: int | str | None,
    participant_ids: list[int | str] | None,
    project: dict | None = None,
) -> tuple[int | None, list[int] | None]:
    """담당자/관련자(user id 또는 이름)를 user id로 해석·검증한다.

    둘 다 없으면 조회를 생략하고 원본을 반환한다. 멤버가 아니거나 못 찾으면 ValueError로 안내.
    project에 프로젝트 상세 응답을 넘기면 재조회 없이 재사용한다.
    """
    if assignee is None and not participant_ids:
        return assignee, participant_ids

    if project is None:
        project = client.get(f"/api/projects/{project_id}/").json()
    members = project.get("members", [])
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


# config/urls.py의 `api/customers/` prefix 아래에 router가 `customers`를 재등록해 경로가 중복된다.
_CUSTOMERS = "/api/customers/customers/"


def _ensure_wbs_weight(project: dict) -> None:
    """비중(weight)은 WBS 프리셋 프로젝트 전용 — 서버 왕복 전에 차단한다."""
    if project.get("preset") != "wbs":
        raise ValueError(
            f"비중(weight)은 WBS 프로젝트에서만 설정할 수 있습니다. "
            f"'{project.get('name')}' 프로젝트의 preset은 '{project.get('preset')}'입니다."
        )


def _resolve_customer(workspace_id: int | None, customer: int | str) -> int:
    """고객사(id 또는 이름)를 id로 해석한다.

    search는 대표자·담당자 이름도 매칭하므로 고객사 이름 정확 일치(대소문자 무시)만
    자동 채택하고 그 외는 후보 목록으로 안내한다. 열람 권한(can_view_customers)이 없는
    워크스페이스는 서버가 403 대신 빈 결과를 주므로 0건은 권한 부재 가능성을 함께 안내한다.
    """
    if not isinstance(customer, bool) and (isinstance(customer, int) or str(customer).strip().isdigit()):
        return int(customer)
    name = str(customer).strip()
    if workspace_id is None:
        raise ValueError(
            "고객사 이름 해석에는 워크스페이스 컨텍스트가 필요합니다. "
            "gdc_login 또는 set_context 후 다시 시도하거나, 고객사 id로 직접 지정하세요."
        )
    data = client.get(
        _CUSTOMERS, params={"workspace": workspace_id, "search": name, "page_size": 100}
    ).json()
    items = data.get("results", []) if isinstance(data, dict) else data
    exact = [c for c in items if str(c.get("name", "")).strip().lower() == name.lower()]
    if len(exact) == 1:
        return exact[0]["id"]
    candidates = exact or items
    if candidates:
        listing = ", ".join(f"{c.get('name')}(id={c['id']})" for c in candidates)
        raise ValueError(
            f"고객사 '{name}'이(가) 하나로 특정되지 않습니다. 후보: {listing} "
            f"— 이름을 정확히 쓰거나 id로 지정하세요."
        )
    raise ValueError(
        f"고객사 '{name}'을(를) 찾을 수 없습니다(미존재 또는 열람 권한 없음). "
        f"고객사 id로 직접 지정할 수 있습니다."
    )


async def _resolve_task(
    ctx: Context | None, id_or_title: int | str, show_archived: bool = False
) -> int:
    """태스크 식별자(id 또는 제목)를 태스크 id로 해석한다.

    - 정수 또는 정수 문자열 → 그대로 태스크 id.
    - 그 외 문자열 → 현재 레포 프로젝트에서 search로 조회. 제목 정확 일치(대소문자 무시)가
      1건이면 채택, 그 외 다수면 후보 목록으로 안내(ValueError), 0건이면 오류(ValueError).
    제목 검색 범위는 현재 프로젝트로 한정한다(멤버/고객사 해석과 동일 UX).
    show_archived=True면 숨긴 태스크도 검색 대상에 포함한다(숨김 해제·삭제 대상 해석용) —
    list는 기본적으로 숨긴 태스크를 제외하므로, 숨긴 태스크를 제목으로 지정하려면 필요하다.
    """
    if not isinstance(id_or_title, bool) and (
        isinstance(id_or_title, int) or str(id_or_title).strip().isdigit()
    ):
        return int(id_or_title)
    title = str(id_or_title).strip()
    if not title:
        raise ValueError("조회할 태스크의 id 또는 제목을 입력하세요.")
    project_id = (await _resolve_context(ctx)).get("project_id")
    if project_id is None:
        raise ValueError(
            "프로젝트가 설정되지 않았습니다. 제목으로 조회하려면 "
            "gdc_login 또는 set_context로 프로젝트를 선택하세요."
        )
    params: dict[str, str | int] = {"project": project_id, "search": title, "page_size": 20}
    if show_archived:
        params["show_archived"] = "true"
    results = client.get(_TASKS, params=params).json().get("results", [])
    if not results:
        raise ValueError(
            f"제목 '{title}'에 해당하는 태스크를 현재 프로젝트에서 찾을 수 없습니다. "
            f"제목을 확인하거나 태스크 id로 지정하세요."
        )
    exact = [r for r in results if str(r.get("title", "")).strip().lower() == title.lower()]
    candidates = exact or results
    if len(candidates) == 1:
        return candidates[0]["id"]
    listing = ", ".join(
        f"#{r.get('number')} {r.get('title')}({_task_url(r['id'])})" for r in candidates[:10]
    )
    raise ValueError(
        f"제목 '{title}'이(가) 하나로 특정되지 않습니다. 후보: {listing} "
        f"— 제목을 더 정확히 쓰거나 태스크 id로 지정하세요."
    )


@mcp.tool
async def create_task(
    ctx: Context,
    project: int,
    title: str,
    status: str | None = None,
    priority: str | None = None,
    task_type: str | None = None,
    assignee: int | str | None = None,
    description: str | None = None,
    planned_start_date: str | None = None,
    planned_end_date: str | None = None,
    actual_start_date: str | None = None,
    actual_end_date: str | None = None,
    progress: int | None = None,
    parent: int | None = None,
    customer: int | str | None = None,
    weight: int | None = None,
    tag_ids: list[int] | None = None,
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

    확장 필드(사용자가 명시할 때만 전달 — 질문으로 강요하지 않음):
    parent(상위 태스크 id), customer(고객사 id **또는 이름** — 이름은 현재 워크스페이스에서
    자동 해석, 모호하면 후보 안내), actual_start_date/actual_end_date, progress(0~100),
    tag_ids(태그 id 리스트), weight(비중 % — **WBS 프로젝트 전용**, 비WBS는 호출 전 차단.
    형제 그룹 비중 합 100 초과는 서버가 검증).

    제약(미충족 시 호출 전 ValueError로 안내·차단): 예상/실제 시작일 ≤ 종료일, 실제 종료일 미래 불가,
    담당자/관련자는 해당 프로젝트 멤버만 지정 가능.

    완료 보정: status가 완료 계열(category=='done')이면 progress=100·실제 종료일=오늘을 자동 주입한다
    (progress/actual_end_date를 직접 전달한 경우 그 값이 우선).
    """
    _validate_dates(planned_start_date, planned_end_date, actual_start_date, actual_end_date)
    # 프로젝트 상세는 멤버 해석·WBS 가드·완료 카테고리 판정에 공용 — 필요할 때 1회만 조회
    project_json = (
        client.get(f"/api/projects/{project}/").json()
        if (weight is not None or assignee is not None or participant_ids or status)
        else None
    )
    if weight is not None:
        _ensure_wbs_weight(project_json)
    assignee, participant_ids = _resolve_members(
        project, assignee, participant_ids, project=project_json
    )  # id 또는 이름
    if assignee is None:
        assignee = _current_user_id()
    if customer is not None:
        customer = _resolve_customer((await _resolve_context(ctx)).get("workspace_id"), customer)
    description = normalize_description(description)  # 평문→HTML 변환(이미 HTML이면 통과)
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
        "actual_start_date": actual_start_date,
        "actual_end_date": actual_end_date,
        "progress": progress,
        "parent": parent,
        "customer": customer,
        "weight": weight,
        "tag_ids": tag_ids,
        "participant_ids": participant_ids,
    }
    # 완료 상태로 생성 시 진행률/실제 종료일 자동 보정 (명시 전달값 우선)
    if status and _status_category(project, status, project=project_json) == "done":
        if progress is None:
            fields["progress"] = 100
        if actual_end_date is None:
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


# UI 수정 폼에서 비울 수 있는(nullable) 필드와 동일한 해제 허용 목록
_CLEARABLE_FIELDS = {
    "parent",
    "assignee",
    "customer",
    "planned_start_date",
    "planned_end_date",
    "actual_start_date",
    "actual_end_date",
    "weight",
}


@mcp.tool
async def update_task(
    ctx: Context,
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
    customer: int | str | None = None,
    parent: int | None = None,
    weight: int | None = None,
    is_pinned: bool | None = None,
    tag_ids: list[int] | None = None,
    participant_ids: list[int | str] | None = None,
    clear_fields: list[str] | None = None,
) -> dict:
    """태스크를 부분 수정(PATCH)한다. 전달한 필드만 갱신된다.

    사용자가 수정 권한을 가진 모든 편집 필드를 노출한다(읽기전용 id/number/creator 제외).
    status/priority/task_type은 해당 프로젝트 enum 'name'(get_project_enums로 확인),
    날짜는 'YYYY-MM-DD', parent는 ID, tag_ids는 ID 리스트.
    assignee·participant_ids는 user id **또는 멤버 이름**(full_name/username)을 넘기면 자동으로 id로 해석한다.
    customer는 고객사 id **또는 이름** — 이름은 현재 워크스페이스에서 검색해 정확 일치를 자동 채택,
    모호하면 후보 목록으로 안내한다.
    weight(비중 %)는 **WBS 프로젝트 전용** — 비WBS 태스크에 전달하면 호출 전 차단.
    parent 변경 시 서버가 weight를 자동 초기화한다(weight를 함께 전달하면 그 값 적용).
    완료 상태(category=='done')로 전환하면 백엔드가 progress=100·actual_end_date를 자동 보정할 수 있다.

    필드 해제(비우기): clear_fields에 필드명 리스트를 전달 — 가능: parent, assignee, customer,
    planned_start_date, planned_end_date, actual_start_date, actual_end_date, weight.
    예) 실제 종료일 비우기 → clear_fields=["actual_end_date"], 고객사 해제 → clear_fields=["customer"].
    같은 필드에 값과 해제를 동시에 전달하면 오류. 관련자 전체 해제는 participant_ids=[].

    제약(미충족 시 ValueError로 안내·차단): 예상/실제 시작일 ≤ 종료일, 실제 종료일은 미래 불가,
    담당자/관련자는 해당 프로젝트 멤버만 지정 가능.
    """
    _validate_dates(planned_start_date, planned_end_date, actual_start_date, actual_end_date)
    if weight is not None or assignee is not None or participant_ids:
        project_id = client.get(f"{_TASKS}{task_id}/").json().get("project")
        project_json = client.get(f"/api/projects/{project_id}/").json()
        if weight is not None:
            _ensure_wbs_weight(project_json)
        assignee, participant_ids = _resolve_members(
            project_id, assignee, participant_ids, project=project_json
        )  # id 또는 이름
    if customer is not None:
        customer = _resolve_customer((await _resolve_context(ctx)).get("workspace_id"), customer)
    description = normalize_description(description)  # 평문→HTML 변환(이미 HTML이면 통과)
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
            "weight": weight,
            "is_pinned": is_pinned,
            "tag_ids": tag_ids,
            "participant_ids": participant_ids,
        }.items()
        if v is not None
    }
    if clear_fields:
        unknown = [f for f in clear_fields if f not in _CLEARABLE_FIELDS]
        if unknown:
            raise ValueError(
                f"해제(null)할 수 없는 필드: {', '.join(unknown)}. "
                f"가능한 필드: {', '.join(sorted(_CLEARABLE_FIELDS))}"
            )
        conflict = [f for f in clear_fields if f in payload]
        if conflict:
            raise ValueError(f"같은 필드에 값과 해제를 동시에 전달할 수 없습니다: {', '.join(conflict)}")
        for f in clear_fields:
            payload[f] = None
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
async def edit_task_description(
    ctx: Context,
    task_id: int | str,
    mode: str,
    bullets: list[str] | None = None,
    label: str = "작업 내용",
    new_body_html: str | None = None,
    keep_media: bool = True,
) -> dict:
    """태스크 본문(description)을 통째 덮어쓰지 않고 최소 편집한다(인라인 이미지 보존).

    본문을 재구성해 통째로 PATCH하면 `<img data-attachment-id>` 인라인 이미지가 유실된다.
    이 도구는 현재 본문 HTML을 받아 필요한 부분만 편집해 PATCH하므로 편집 대상 밖 이미지가
    자동 보존된다. 반영(문서→태스크) 흐름에서 **추가 작업/내용 변경**을 본문에 적용할 때 쓴다.

    mode:
    - "append_work": `[label]`(기본 '작업 내용') 섹션 목록에 bullets를 `<li>`로 추가한다
      (섹션/목록이 없으면 신설). 기존 내용·이미지 100% 보존. bullets 필수.
    - "replace_section": `[label]` 섹션 **본문만** new_body_html로 교체한다(라벨 문단·타 섹션 보존).
      섹션에 인라인 이미지가 있으면 keep_media=True(기본)는 이미지를 섹션 끝으로 옮겨 보존,
      keep_media=False는 함께 삭제. new_body_html 필수(라벨 문단 제외한 본문 HTML).

    task_id는 id(정수) 또는 제목(문자열). 편집 결과가 현재와 같으면 PATCH하지 않고 그대로 반환.
    """
    resolved_id = await _resolve_task(ctx, task_id)
    cur = client.get(f"{_TASKS}{resolved_id}/").json()
    current_html = cur.get("description") or ""
    media_warning = None

    if mode == "append_work":
        if not bullets or not [b for b in bullets if b and b.strip()]:
            raise ValueError("append_work 모드는 추가할 bullets가 필요합니다.")
        new_html = append_work_bullets(current_html, bullets, label=label)
    elif mode == "replace_section":
        if not new_body_html:
            raise ValueError("replace_section 모드는 new_body_html이 필요합니다.")
        if keep_media and label_section_has_media(current_html, label):
            media_warning = (
                f"'[{label}]' 섹션의 인라인 이미지를 섹션 끝으로 옮겨 보존했습니다"
                "(문단 위치가 섹션 하단으로 이동). 삭제하려면 keep_media=False로 다시 호출하세요."
            )
        new_html = replace_label_section(
            current_html, label, new_body_html, keep_media=keep_media
        )
    else:
        raise ValueError("mode는 'append_work' 또는 'replace_section'이어야 합니다.")

    if new_html == current_html:
        return {
            "id": resolved_id,
            "changed": False,
            "url": _task_url(resolved_id),
            "note": "변경 사항이 없어 PATCH하지 않았습니다.",
        }

    t = client.request(
        "PATCH", f"{_TASKS}{resolved_id}/", json={"description": new_html}
    ).json()
    result = {
        "id": t["id"],
        "changed": True,
        "mode": mode,
        "title": t.get("title"),
        "url": _task_url(t["id"]),
    }
    if media_warning:
        result["media_warning"] = media_warning
    return result


@mcp.tool
def open_task(task_id: int) -> dict:
    """태스크 웹 화면을 Chrome 새 탭으로 연다.

    목록에 표시되는 URL을 클릭하면 VSCode 내장 브라우저로 열릴 수 있으므로,
    이 도구는 chrome.exe를 직접 실행해 항상 Chrome으로 연다(미설치 시 기본 브라우저).
    """
    url = _task_url(task_id)
    opened = open_in_chrome(url)
    return {"opened": opened, "url": url, "browser": "chrome" if opened else "default"}


def _status_category(
    project_id: int | None, status_name: str | None, project: dict | None = None
) -> str | None:
    """프로젝트에서 status name의 category(planned/in_progress/done)를 찾는다.

    project에 프로젝트 상세 응답을 넘기면 재조회 없이 재사용한다.
    """
    if not project_id or not status_name:
        return None
    if project is None:
        project = client.get(f"/api/projects/{project_id}/").json()
    for s in project.get("task_statuses", []):
        if s.get("name") == status_name:
            return s.get("category")
    return None


def _parent_summary(t: dict) -> dict | None:
    """상세 응답의 ancestors(최상위→직속 순)에서 직속 상위 태스크 요약을 만든다.

    ancestors는 상세 API가 이미 반환하므로 추가 왕복이 없다. 상위가 없으면 None.
    """
    ancestors = t.get("ancestors") or []
    if not ancestors:
        return None
    p = ancestors[-1]  # 직속 상위(경로 마지막)
    return {
        "id": p.get("id"),
        "number": p.get("number"),
        "title": p.get("title"),
        "url": _task_url(p["id"]) if p.get("id") else None,
    }


def _related_tasks(t: dict) -> list[dict]:
    """outgoing/incoming 링크를 방향 유지로 통합한 연관 태스크 목록.

    각 항목은 {direction, link_type, task}. direction은 이 태스크 기준:
    - outgoing: 이 태스크 → 대상(target). `blocks`면 "대상을 차단함".
    - incoming: 원본(source) → 이 태스크. `blocks`면 "원본에게 차단됨".
    link_type(related/blocks/…)은 조회 주체에 따라 의미가 반대이므로 방향과 함께 그대로 노출한다.
    """
    related: list[dict] = []
    for link in t.get("outgoing_links", []) or []:
        tid = link.get("target_task")
        related.append({
            "direction": "outgoing",
            "link_type": link.get("link_type"),
            "task": {
                "id": tid,
                "number": link.get("target_task_number"),
                "title": link.get("target_task_title"),
                "url": _task_url(tid) if tid else None,
            },
        })
    for link in t.get("incoming_links", []) or []:
        sid = link.get("source_task")
        related.append({
            "direction": "incoming",
            "link_type": link.get("link_type"),
            "task": {
                "id": sid,
                "number": link.get("source_task_number"),
                "title": link.get("source_task_title"),
                "url": _task_url(sid) if sid else None,
            },
        })
    return related


@mcp.tool
async def get_task(ctx: Context, task_id: int | str) -> dict:
    """태스크 상세를 조회한다(작업 요청 문서 생성·연동용).

    task_id는 태스크 id(정수) **또는 제목(문자열)** — 제목이면 현재 프로젝트에서 검색해
    해석한다(정확 1건이면 채택, 다수면 후보 안내, 0건이면 오류).

    제목/내용/상태/우선순위/유형/날짜/진행률/담당자 등 문서 작성에 필요한 필드와 함께
    **상위 태스크(parent)·하위 태스크(sub_tasks)·연관 태스크(related_tasks)** 를 반환한다.
    - sub_tasks: 이 태스크의 하위 태스크 요약 목록(휴지통 제외, 서버 가시성 필터 적용).
    - related_tasks: outgoing/incoming 링크를 방향 유지로 통합({direction, link_type, task}).
    - parent: 직속 상위 태스크 요약(없으면 null).
    상세 API 1회 호출로 모두 받으므로 추가 왕복이 없다(제목 해석 시 검색 1회 추가).
    """
    resolved_id = await _resolve_task(ctx, task_id)
    t = client.get(f"{_TASKS}{resolved_id}/").json()
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
        "parent": _parent_summary(t),
        "sub_tasks": [_task_summary(s) for s in (t.get("sub_tasks") or [])],
        "related_tasks": _related_tasks(t),
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


def _round_progress(raw: int) -> int:
    """전송 진행률을 10% 단위로 반올림한다.

    GDC UI는 태스크 진행률을 10% 단위로만 수정할 수 있어, 문서 진척으로 산출된
    비(非)10단위 값(예: 33%)이 저장되면 이후 UI 수정 시 오류가 난다. 여기서 서버로
    나가는 값을 항상 10단위로 맞춘다.

    - `round(raw / 10) * 10` (Python 기본 은행가 반올림: 5로 끝나는 값은 짝수 쪽).
    - 단 `raw >= 100`(모든 Phase 완료)일 때만 100을 반환하고, 그 미만은 최대 90으로
      캡핑한다. `round(95/10)*10 == 100`이 95~99% 태스크를 조기 '완료' 전이시키는 것을 막기 위함.
    """
    if raw >= 100:
        return 100
    return min(round(raw / 10) * 10, 90)


def _apply_progress_sync(task_id: int, new_progress: int, description: str | None = None) -> dict:
    """진행률을 PATCH하면서 상태/실제 날짜 전이를 함께 적용한다.

    - 전송 진행률은 `_round_progress`로 10% 단위 반올림한다(UI 수정 제약 회피).
    - 상태/실제 날짜 전이는 반올림 전 raw 값 기준으로 판단한다(5% 미만 진척도 '진행'으로 전이).
    - 최초 진행(0 → raw>0): 상태를 '진행'(in_progress, planned→만)으로, 실제 시작일을 오늘로(미설정 시).
    - 100% 달성(raw>=100): 상태를 '완료'(done 계열)로, 실제 종료일을 오늘로(미설정 시).
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
    raw = new_progress
    payload: dict = {"progress": _round_progress(raw)}
    if description is not None:
        payload["description"] = normalize_description(description)  # 평문→HTML(이미 HTML이면 통과)

    if old_progress == 0 and raw > 0 and not cur.get("actual_start_date"):
        payload["actual_start_date"] = today

    if raw >= 100:
        done = _pick("done", ("완료", "완료됨", "completed", "done", "closed", "종료"))
        if done and cur.get("status") != done:
            payload["status"] = done
        if not cur.get("actual_end_date"):
            payload["actual_end_date"] = today
    elif raw > 0 and cur_cat not in ("in_progress", "done"):
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
    - description(필수): 호출하는 에이전트가 아래 라벨 섹션 템플릿(평문)으로 작성해 전달한다.
      도구가 GDC 리치텍스트(HTML)로 변환해 저장한다(라벨→문단, 블렛→목록, 섹션 사이 빈 문단).
        [요약]
        문서 "요청 내용" 한두 줄 요약

        [AS-IS]        ← 선택(TO-BE와 짝): '요청 내용'·'배경'에서 구현 전 상황이 실제로 드러날 때만
        구현 전 상황

        [TO-BE]        ← 선택(AS-IS와 짝)
        구현 후 상황

        [작업 내용]
        - 작업 결과 단계를 블렛(`-`)으로 간단히 요약 (각 단계 한 줄)
      ※ [요약]·[작업 내용]=필수, [AS-IS]/[TO-BE]=선택(짝). 전/후 상황이 불명확하면 생략(추측·빈말 금지) —
        신규 기능·문서 작업엔 보통 빠진다.
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
    description = normalize_description(description)  # 라벨 템플릿 → GDC 리치텍스트(HTML)(공통 진입점)

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


# --- 태스크 댓글(Mention) -------------------------------------------------------
# gdc-service의 댓글은 Mention 모델(/api/tasks/mentions/). content는 리치텍스트(HTML)이고,
# 서버가 content의 `@username`을 파싱해 멘션 알림(task_commented)을 발송한다. 수정/삭제는
# 작성자 본인만 가능(403). 이 레포는 클라이언트 — 서버는 미수정.


def _resolve_mention_usernames(
    project_id: int,
    mentions: list[int | str] | None,
    project: dict | None = None,
) -> list[str]:
    """멘션 대상(멤버 이름 또는 user id)을 프로젝트 멤버의 username 리스트로 해석한다.

    비멤버는 _resolve_members와 동일하게 가능한 멤버 목록과 함께 ValueError로 안내한다.
    project에 프로젝트 상세 응답을 넘기면 재조회 없이 재사용한다.
    """
    if not mentions:
        return []
    if project is None:
        project = client.get(f"/api/projects/{project_id}/").json()
    members = project.get("members", [])
    by_id: dict[int, str | None] = {}
    by_name: dict[str, str | None] = {}
    for m in members:
        uname = m.get("username")
        if m.get("user") is not None:
            by_id[m["user"]] = uname
        for nm in (m.get("full_name"), m.get("username")):
            if nm:
                by_name[str(nm).strip().lower()] = uname

    resolved: list[str] = []
    for value in mentions:
        if not isinstance(value, bool) and (isinstance(value, int) or str(value).strip().isdigit()):
            uname = by_id.get(int(value))
        else:
            uname = by_name.get(str(value).strip().lower())
        if not uname:
            valid = ", ".join(
                f"{(m.get('full_name') or m.get('username'))}(id={m.get('user')})" for m in members
            )
            raise ValueError(
                f"멘션 대상 '{value}'은(는) 이 프로젝트의 멤버가 아닙니다. 가능한 멤버: {valid or '(없음)'}"
            )
        resolved.append(uname)
    return resolved


def _build_comment_html(content: str, usernames: list[str]) -> str:
    """본문을 GDC 리치텍스트(HTML)로 변환하고, 멘션이 있으면 `@user…` 문단을 선두에 붙인다.

    서버가 content의 `@username`을 파싱하므로, HTML 문단으로 감싸도 정규식이 사용자명을 찾는다.
    """
    html = normalize_description(content) or ""
    if usernames:
        prefix = " ".join(f"@{u}" for u in usernames)
        html = f"<p>{prefix}</p>{html}"
    return html


@mcp.tool
def list_task_comments(task_id: int, limit: int = 20) -> dict:
    """태스크의 댓글(멘션) 목록을 조회한다. 최신순 상위 limit개를 시간순(오래된→최신)으로 반환.

    서버 페이지네이션(PAGE_SIZE=20, page_size 미지원)상 **한 요청으로 최대 20개**만 받는다 —
    limit>20을 줘도 20개까지만 반환된다(가장 최근 댓글 우선). count는 태스크의 전체 댓글 수.

    각 댓글: id, author_name(작성자 실명), text(HTML을 벗긴 평문), is_edited(수정됨 여부), created_at.
    """
    data = client.get(_MENTIONS, params={"task": task_id, "ordering": "-created_at"}).json()
    if isinstance(data, dict):
        page = data.get("results", [])
        total = data.get("count", len(page))
    else:  # 페이지네이션 비활성(리스트) 방어
        page = data
        total = len(page)
    recent = list(reversed(page[:limit]))  # 최신 limit개를 시간순으로 표시
    comments = [
        {
            "id": c["id"],
            "author_name": c.get("author_name"),
            "text": html_to_text(c.get("content")),
            "is_edited": c.get("is_edited"),
            "created_at": c.get("created_at"),
        }
        for c in recent
    ]
    return {"count": total, "shown": len(comments), "comments": comments}


@mcp.tool
def add_task_comment(
    task_id: int, content: str, mentions: list[int | str] | None = None
) -> dict:
    """태스크에 댓글(멘션)을 작성한다. 필수: task_id, content(본문).

    content는 평문으로 넘기면 GDC 리치텍스트(HTML)로 변환해 저장한다(이미 HTML이면 통과).
    mentions에 멤버 이름 또는 user id 리스트를 주면 각 멤버의 username으로 해석해
    본문 맨 앞에 `@user1 @user2` 한 줄을 붙인다 → 서버가 이를 파싱해 멘션 알림을 발송한다.
    (멘션은 본문 선두에만 배치되며, 본문 중간 커서 위치 삽입은 지원하지 않는다.)
    비멤버를 멘션하면 가능한 멤버 목록과 함께 오류로 안내한다.
    """
    usernames: list[str] = []
    if mentions:
        project_id = client.get(f"{_TASKS}{task_id}/").json().get("project")
        usernames = _resolve_mention_usernames(project_id, mentions)
    content_html = _build_comment_html(content, usernames)
    m = client.request(
        "POST", _MENTIONS, json={"task": task_id, "content": content_html}
    ).json()
    return {
        "id": m["id"],
        "author_name": m.get("author_name"),
        "created_at": m.get("created_at"),
    }


@mcp.tool
def update_task_comment(
    comment_id: int, content: str, mentions: list[int | str] | None = None
) -> dict:
    """댓글(멘션) 본문을 수정한다. **본인이 작성한 댓글만 수정 가능**(아니면 오류).

    주의: 서버가 새 content로 멘션을 **다시 파싱해 덮어쓴다**. 기존 멘션을 유지하려면
    mentions 인자로 함께 넘겨야 하며, mentions 없이 수정하면 이전 멘션 알림 대상이 사라진다.
    content는 평문→HTML 자동 변환(이미 HTML이면 통과).
    """
    usernames: list[str] = []
    if mentions:
        task_id = client.get(f"{_MENTIONS}{comment_id}/").json().get("task")
        project_id = client.get(f"{_TASKS}{task_id}/").json().get("project")
        usernames = _resolve_mention_usernames(project_id, mentions)
    content_html = _build_comment_html(content, usernames)
    try:
        m = client.request(
            "PATCH", f"{_MENTIONS}{comment_id}/", json={"content": content_html}
        ).json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            raise ValueError("본인이 작성한 댓글만 수정할 수 있습니다.") from e
        raise
    return {
        "id": m["id"],
        "is_edited": m.get("is_edited"),
        "updated_at": m.get("updated_at"),
    }


@mcp.tool
def delete_task_comment(comment_id: int) -> dict:
    """댓글(멘션)을 삭제한다. **본인이 작성한 댓글만 삭제 가능**(아니면 오류)."""
    try:
        client.request("DELETE", f"{_MENTIONS}{comment_id}/")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            raise ValueError("본인이 작성한 댓글만 삭제할 수 있습니다.") from e
        raise
    return {"deleted": True, "comment_id": comment_id}


# --- 태스크 숨기기·삭제·복구 ----------------------------------------------------
# 서버가 토큰 권한으로 강제하므로(403), 도구는 권한 판정 없이 실행하고 403을 한글로 변환한다.
# 파괴적/부작용 동작(숨기기·삭제·복구)은 confirm 게이트: confirm=False면 미리보기만 반환한다.


async def _trashed_items(ctx: Context) -> tuple[int, list[dict], int]:
    """현재 프로젝트 휴지통(soft-deleted) 목록을 조회한다. (project_id, items, total) 반환.

    trash는 자동으로 현재 프로젝트로 스코프되지 않으므로 project를 명시 전송한다(미전송 시
    관리 권한 있는 전 프로젝트 휴지통이 섞임). 삭제 태스크는 일반 search에서 빠지므로 제목
    해석·복구 대상 확인에 이 목록을 쓴다.
    """
    project_id = (await _resolve_context(ctx)).get("project_id")
    if project_id is None:
        raise ValueError(
            "프로젝트가 설정되지 않았습니다. gdc_login 또는 set_context로 프로젝트를 선택하세요."
        )
    data = client.get(f"{_TASKS}trash/", params={"project": project_id, "page_size": 100}).json()
    if isinstance(data, dict):
        return project_id, data.get("results", []), data.get("count", 0)
    return project_id, data, len(data)


def _find_trashed(items: list[dict], id_or_title: int | str) -> tuple[int, dict | None]:
    """휴지통 항목에서 id 또는 제목으로 대상을 찾아 (id, item) 반환. 모호/부재면 ValueError.

    id는 목록에 없어도 그대로 통과시킨다(다른 프로젝트 소속 등 — 서버가 최종 판정).
    """
    if not isinstance(id_or_title, bool) and (
        isinstance(id_or_title, int) or str(id_or_title).strip().isdigit()
    ):
        tid = int(id_or_title)
        return tid, next((r for r in items if r.get("id") == tid), None)
    title = str(id_or_title).strip()
    if not title:
        raise ValueError("복구할 태스크의 id 또는 제목을 입력하세요.")
    exact = [r for r in items if str(r.get("title", "")).strip().lower() == title.lower()]
    candidates = exact or [
        r for r in items if title.lower() in str(r.get("title", "")).strip().lower()
    ]
    if len(candidates) == 1:
        return candidates[0]["id"], candidates[0]
    if not candidates:
        raise ValueError(
            f"제목 '{title}'에 해당하는 삭제된 태스크를 현재 프로젝트 휴지통에서 찾을 수 없습니다. "
            f"list_trashed_tasks로 확인하거나 태스크 id로 지정하세요."
        )
    listing = ", ".join(f"#{r.get('number')} {r.get('title')}(id={r['id']})" for r in candidates[:10])
    raise ValueError(
        f"제목 '{title}'이(가) 하나로 특정되지 않습니다. 후보: {listing} — 태스크 id로 지정하세요."
    )


@mcp.tool
async def archive_task(
    ctx: Context, task_id: int | str, archived: bool = True, confirm: bool = False
) -> dict:
    """태스크를 숨기거나(archived=True) 숨김 해제한다(archived=False). 토글 API를 멱등 래핑한다.

    task_id는 태스크 id(정수) **또는 제목(문자열)** — 제목이면 현재 프로젝트에서 검색해 해석한다.
    숨기면 **모든 하위 태스크가 함께 숨김**되고 고정(pin)은 자동 해제된다. WBS 프로젝트는 숨김
    기능을 지원하지 않는다(안내). 숨김 해제는 상위가 숨김 상태면 막힌다(먼저 상위 숨김 해제).

    **확인 게이트**: confirm=False(기본)면 대상과 현재/목표 상태만 미리보기로 반환하고 실행하지
    않는다. confirm=True로 다시 호출해야 실제로 토글한다. 이미 원하는 상태면 호출 없이 그대로 둔다(멱등).
    """
    # 숨김 해제 대상은 이미 숨겨져 list에서 빠지므로 제목 해석에 숨긴 태스크도 포함한다.
    resolved_id = await _resolve_task(ctx, task_id, show_archived=True)
    t = client.get(f"{_TASKS}{resolved_id}/").json()
    current = bool(t.get("is_archived"))
    target = bool(archived)
    action = "숨기기" if target else "숨김 해제"
    info = {
        "id": t["id"],
        "number": t.get("number"),
        "title": t.get("title"),
        "current_archived": current,
        "target_archived": target,
        "action": action,
        "sub_task_count": len(t.get("sub_tasks") or []),
        "url": _task_url(t["id"]),
    }
    if current == target:
        return {"changed": False, "reason": f"이미 {action} 상태입니다.", **info}
    if not confirm:
        return {
            "confirm_required": True,
            "message": (
                f"#{t.get('number')} '{t.get('title')}'을(를) {action}합니다. "
                f"하위 태스크도 함께 처리됩니다. confirm=true로 다시 호출하세요."
            ),
            **info,
        }
    try:
        client.request("POST", f"{_TASKS}{resolved_id}/archive/")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            raise ValueError("태스크 숨기기 권한이 없습니다.") from e
        if e.response.status_code == 400:
            code = (e.response.json() or {}).get("code")
            if code == "wbs_archive_disabled":
                raise ValueError("WBS 프로젝트에서는 숨김 기능을 지원하지 않습니다.") from e
            if code == "parent_archived":
                raise ValueError(
                    "상위 태스크가 숨김 상태입니다. 최상위 태스크의 숨김을 먼저 해제하세요."
                ) from e
        raise
    return {"changed": True, **info}


@mcp.tool
async def delete_task(ctx: Context, task_id: int | str, confirm: bool = False) -> dict:
    """태스크를 삭제한다(**소프트 삭제 → 휴지통 이동, 복구 가능**). 관리자 이상 권한 필요.

    task_id는 태스크 id(정수) **또는 제목(문자열)** — 제목이면 현재 프로젝트에서 검색해 해석한다.
    하위 태스크 처리: **WBS 프로젝트는 하위 전체 연쇄 삭제**, 비WBS는 직속 하위를 최상위로 승격
    후 본체만 삭제한다(손자는 승격된 부모 밑 유지). 복구는 restore_task, 목록은 list_trashed_tasks.

    **확인 게이트**: confirm=False(기본)면 삭제 대상과 하위 영향만 미리보기로 반환하고 삭제하지
    않는다. confirm=True로 다시 호출해야 실제 삭제한다.
    """
    # 숨긴 태스크도 삭제 대상이 될 수 있으므로 제목 해석에 포함한다.
    resolved_id = await _resolve_task(ctx, task_id, show_archived=True)
    t = client.get(f"{_TASKS}{resolved_id}/").json()
    sub_count = len(t.get("sub_tasks") or [])
    info = {
        "id": t["id"],
        "number": t.get("number"),
        "title": t.get("title"),
        "sub_task_count": sub_count,
        "url": _task_url(t["id"]),
    }
    if not confirm:
        return {
            "confirm_required": True,
            "message": (
                f"#{t.get('number')} '{t.get('title')}'을(를) 삭제(휴지통 이동)합니다. "
                f"하위 {sub_count}개는 프로젝트 유형에 따라 연쇄 삭제(WBS) 또는 최상위 승격(비WBS)됩니다. "
                f"복구 가능. confirm=true로 다시 호출하세요."
            ),
            **info,
        }
    try:
        client.request("DELETE", f"{_TASKS}{resolved_id}/")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            raise ValueError("태스크 삭제 권한이 없습니다 (관리자 이상).") from e
        raise
    return {"deleted": True, **info}


@mcp.tool
async def restore_task(ctx: Context, task_id: int | str, confirm: bool = False) -> dict:
    """휴지통의 삭제된 태스크를 복구한다. 관리자 이상 권한 필요.

    task_id는 태스크 id(정수) **또는 제목(문자열)** — 삭제 태스크는 일반 검색에서 빠지므로
    **현재 프로젝트 휴지통에서 제목을 매칭**한다. 존재하지 않거나 삭제되지 않은 태스크는 안내한다.

    **주의**: 첨부 파일은 함께 복구되지만 **연쇄 삭제된 하위 태스크는 복구되지 않고 휴지통에 남는다**
    (단건 + 자기 첨부만 복구). **WBS 태스크는 원래 부모 밑이 아니라 최상위로 분리되고 비중(weight)이
    해제된 상태로 복구**된다.

    **확인 게이트**: confirm=False(기본)면 대상·부작용만 미리보기로 반환하고 복구하지 않는다.
    confirm=True로 다시 호출해야 실제 복구한다.
    """
    _, items, _ = await _trashed_items(ctx)
    resolved_id, item = _find_trashed(items, task_id)
    if not confirm:
        info: dict = {"id": resolved_id}
        if item:
            info.update({
                "number": item.get("number"),
                "title": item.get("title"),
                "deleted_at": item.get("deleted_at"),
                "deleted_by": item.get("deleted_by_name"),
            })
        return {
            "confirm_required": True,
            "message": (
                "이 태스크를 복구합니다. 첨부는 함께 복구되지만 연쇄 삭제된 하위는 복구되지 않으며, "
                "WBS면 최상위로 분리(weight 해제)됩니다. confirm=true로 다시 호출하세요."
            ),
            **info,
        }
    try:
        t = client.request("POST", f"{_TASKS}{resolved_id}/restore/").json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            raise ValueError("태스크 복구 권한이 없습니다 (관리자 이상).") from e
        if e.response.status_code == 404:
            raise ValueError(
                "복구할 태스크를 찾을 수 없습니다(삭제되지 않았거나 존재하지 않음)."
            ) from e
        raise
    return {
        "restored": True,
        "id": t.get("id"),
        "number": t.get("number"),
        "title": t.get("title"),
        "url": _task_url(t["id"]) if t.get("id") else None,
    }


@mcp.tool
async def list_trashed_tasks(ctx: Context, limit: int = 20) -> dict:
    """현재 프로젝트 휴지통(삭제된 태스크) 목록을 조회한다. 복구(restore_task) 대상 식별용.

    삭제된 태스크는 일반 조회(list_my_tasks/get_task)에서 빠지므로, 복구하려면 이 목록에서
    id/제목을 확인한다. 각 항목에 삭제 시각(deleted_at)·삭제자(deleted_by)를 포함한다.
    현재 레포 프로젝트로 스코프되며(project 명시 전송), 관리자 이상만 유효한 결과를 받는다.
    한 요청으로 최대 100개까지 받아 최신 삭제순 상위 limit개를 반환한다(count는 전체 삭제 수).
    """
    project_id, items, total = await _trashed_items(ctx)
    trimmed = items[:limit]
    return {
        "project_id": project_id,
        "count": total,
        "shown": len(trimmed),
        "tasks": [
            {
                "id": r["id"],
                "number": r.get("number"),
                "title": r.get("title"),
                "deleted_at": r.get("deleted_at"),
                "deleted_by": r.get("deleted_by_name"),
                "url": _task_url(r["id"]),
            }
            for r in trimmed
        ],
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
def gdc_task(task: str = "") -> str:
    """태스크 상세 조회 (id 또는 제목, 하위·연관·상위 태스크 포함)."""
    return (
        f"`get_task` 도구로 태스크 상세를 조회하세요. 대상: {task or '(필수: 태스크 id 또는 제목)'}\n"
        "- 인자는 태스크 id(정수) 또는 제목(문자열). 제목이면 도구가 현재 프로젝트에서 검색해 해석합니다"
        "(정확 1건이면 채택, 다수면 후보 안내, 0건이면 오류).\n"
        "- 상태·우선순위·유형은 응답의 `status_label`·`priority_label`·`task_type_label`(한글), 프로젝트는 `project_name`을 씁니다.\n"
        "- 상위(parent)는 있으면 번호·제목·URL 한 줄로, 하위(sub_tasks)는 번호/제목/상태/진행률/URL 표로 보여줍니다.\n"
        "- 연관(related_tasks)은 각 항목의 `direction`(outgoing=대상으로, incoming=원본에서)·`link_type`과 대상/원본 "
        "번호·제목·URL을 함께 표기합니다. `blocks`/`blocked_by`는 방향에 따라 의미가 반대이므로 방향을 명시합니다.\n"
        "조회 프로젝트는 현재 레포 컨텍스트로 고정됩니다. 특정 태스크를 열어달라고 하면 `open_task(task_id)`로 Chrome 새 탭에 엽니다."
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
        "3. 제목·내용(description)을 입력에서 받거나 한 번 물어봅니다. 내용은 **라벨 섹션 템플릿(평문)**으로 "
        "정리하면 도구가 GDC 리치텍스트(HTML)로 변환합니다 — `[요약]` 한두 줄 요약 → (선택·짝) `[AS-IS]`/`[TO-BE]` → "
        "`[작업 내용]` 아래 `-` 블렛(각 한 줄). 이미 HTML로 작성하면 그대로 전송됩니다(이중 변환 없음).\n"
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
        "1. description을 **라벨 섹션 템플릿(평문)**으로 작성합니다(도구가 GDC 리치텍스트(HTML)로 변환):\n"
        "   `[요약]` 문서 '요청 내용' 한두 줄 요약 → `[AS-IS]`/`[TO-BE]`(선택·짝: '요청 내용'·'배경'에서 전/후 상황이 "
        "실제로 드러날 때만; 불명확하면 생략) → `[작업 내용]` 아래 '작업 결과' 단계를 블렛(`-`)으로 요약(각 단계 한 줄).\n"
        "   **체크박스(`[ ]`/`[x]`)는 넣지 말 것**(진행 상태는 progress 필드 담당). "
        "**빌드·타입체크·검증·테스트·lint·커밋·배포/동작 확인·'INDEX.md 이력 추가' 같은 프로세스 메타 단계는 넣지 말 것**"
        "(실제 산출물 단계만; 원본 '작업 결과'에 있어도 옮기지 않는다). 넣더라도 도구가 자동 제거한다.\n"
        "2. `get_project_enums(project_id)`로 `task_type` 목록을 조회해, 문서 메타표 `유형`+본문 내용에 가장 맞는 enum name을 "
        "`task_type` 인자로 정합니다(확실하지 않으면 생략).\n"
        "3. **생성 전 미리보기 + 단일 확인(항상)**: 태스크 생성 직전에 아래를 표로 보여주고 **한 번 확인**받습니다 — "
        "제목 / 렌더링될 본문(요약·AS-IS/TO-BE·작업 내용) / 상태 / 유형 / **우선순위**(priority; 기본 미지정). "
        "사용자가 원하는 항목(특히 우선순위)을 그 자리에서 바꿔 요청하면 반영해 다시 확인합니다.\n"
        "4. 확인 후 `task_from_doc` 도구 호출(변경된 우선순위/유형이 있으면 `priority`/`task_type` 인자로 전달). "
        "project는 현재 레포 컨텍스트(gdc_login 저장값)에서 자동 결정됩니다. "
        "메타데이터 표의 `상태`는 자동 매핑: done→'완료', partial→'진행'. 완료 매핑 시 progress=100·실제 종료일=오늘이 자동 주입됩니다.\n"
        "5. 생성 결과(task_id/URL)와 문서 frontmatter 갱신 여부를 보고합니다."
    )


@mcp.prompt
def gdc_doc_from_task(task_id: str = "") -> str:
    """태스크 기반으로 작업 요청 문서 생성·연동."""
    return (
        f"태스크 ID {task_id or '(필수)'}를 기반으로 작업 요청 문서를 생성하고 그 태스크와 연동합니다.\n"
        f"1. `get_task({task_id})`로 상세(제목/내용/상태+category/우선순위/유형/날짜/진행률/URL)를 가져오고, "
        f"**함께 `list_task_comments({task_id})`로 댓글(멘션)도 조회**합니다. 댓글에 요구사항·의사결정 맥락이 담긴 경우가 "
        "많습니다(특히 description이 빈 태스크). 댓글이 0개면 기존과 동일하게 description 기반으로만 진행합니다. "
        "`count`가 20을 넘으면 최신 20개만 조회됨을 문서에 언급합니다.\n"
        "2. **태스크 description을 그대로 옮기지 말 것.** 다음 순서로 작성합니다: "
        "①관련 코드 검토(태스크 내용에 해당하는 실제 코드/파일을 읽어 현황 파악) → ②기획 정리(요구사항·배경 명확화 — "
        "**description과 댓글 내용을 통합**하고, 둘이 상충하면 그 사실을 문서에 드러냄) → "
        "③개발 계획 수립(단계별 작업 항목) → ④문서 반영.\n"
        "3. `docs/requests/TEMPLATE.md` 형식으로 작성: 제목=태스크 제목, 메타표(날짜=오늘, 상태=status_category 매핑 "
        "done→done·in_progress→partial·그 외→partial, 유형/영역은 합리적으로), 요청 내용=②기획 정리 결과, 작업 결과=③개발 계획 체크리스트.\n"
        f"   문서 맨 위 frontmatter에 `task_id: {task_id}`, `task_url: <url>`을 기록해 연동합니다.\n"
        "4. 경로: `docs/requests/YYYY-MM/YYYYMMDD-HHmmss-<짧은설명>.md` (타임스탬프는 date 명령).\n"
        "5. `docs/INDEX.md` `## 이력`에 한 줄 추가. 6. 생성 경로와 task_id/URL을 보고합니다.\n"
        "※ 이 요청으로 (하위)태스크를 **함께 생성**하는 경우, 태스크 description은 평문 한 문단으로 넣지 말고 "
        "`gdc_task_new`의 **라벨 섹션 템플릿(평문)**을 따릅니다: `[요약]` 한두 줄 → (선택·짝) `[AS-IS]`/`[TO-BE]` → "
        "`[작업 내용]` 아래 `-` 블렛(각 한 줄). `create_task`가 이를 GDC 리치텍스트(HTML)로 변환합니다."
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
        "이 커맨드는 **진행률·상태·실제 날짜 동기화 전용**입니다. "
        "본문(description)에 추가 작업/내용 변경을 반영하려면 `sync_doc_progress`의 `description`으로 통째 넘기지 말고"
        "(본문 통째 교체는 인라인 이미지가 유실됨), `/gdc-apply`(또는 `edit_task_description`)로 최소 편집하세요.\n"
        "동기화 후 progress(%)와 상태 전이(진행/완료), 실제 시작/종료일을 보고하세요."
    )


@mcp.prompt
def gdc_apply(path: str = "") -> str:
    """문서 변경을 연결된 태스크 본문/댓글/하위 태스크에 반영(분류→질문→라우팅)."""
    return (
        f"작업 요청 문서의 변경을 연결된 태스크에 반영합니다. 경로: {path or '(생략 시 현재 docs/requests 문서)'}\n"
        "본문은 통째로 덮어쓰지 않습니다(인라인 이미지 유실 방지) — 아래 절차로 최소 편집/댓글/하위 태스크로 라우팅하세요.\n"
        "1. 문서 frontmatter의 task_id 확인(없으면 link_task_to_doc/gdc_login 안내). `get_task`로 현재 본문(description)을 가져옵니다.\n"
        "2. 문서(요청 내용/`## 작업 결과`)와 현재 본문을 비교해 **추가 작업**인지 **기존 내용 변경**인지 분류합니다.\n"
        "3. **추가 작업**이면 AskUserQuestion으로 반영 위치를 묻습니다:\n"
        "   ① 본문 append — `edit_task_description(task_id, mode='append_work', bullets=[...])`로 `[작업 내용]`에 블렛 추가.\n"
        "   ② 댓글 — `add_task_comment`에 `[추가 (YYYY-MM-DD)]` 라벨 + 블렛.\n"
        "   ③ 하위 태스크 — `create_task(parent=task_id, ...)`.\n"
        "4. **내용 변경**이면 AskUserQuestion으로 묻습니다:\n"
        "   ① 본문만 최신화 — `edit_task_description(task_id, mode='replace_section', label='<라벨>', new_body_html='<본문HTML>')`로 해당 라벨 섹션만 교체.\n"
        "   ② 댓글만 — `add_task_comment`에 `[변경 (YYYY-MM-DD)]` + 변경 이유 + 전/후(본문 유지).\n"
        "   ③ 둘 다 — 본문 교체 + 변경이력 댓글.\n"
        "   변경 이유는 문서 diff·맥락에서 초안을 만들고 사용자가 수정하게 합니다.\n"
        "5. replace_section 대상 섹션에 인라인 이미지가 있으면 도구가 경고합니다 — 유지(기본)/삭제를 사용자에게 확인하고 keep_media로 반영하세요.\n"
        "6. new_body_html은 GDC 리치텍스트 형식(`<p>...</p>`, `<ul><li><p>...</p></li></ul>`)으로 작성합니다(라벨 문단 `<p><strong>라벨</strong></p>`은 도구가 유지).\n"
        "7. 반영 결과(모드·대상·URL, 이미지 경고 있으면 함께)를 보고합니다. 진행률·상태·날짜 동기화는 `/gdc-sync`가 담당합니다."
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
        print(f"synced task {task_id}: progress={t.get('progress')}% status={t.get('status')}")
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
