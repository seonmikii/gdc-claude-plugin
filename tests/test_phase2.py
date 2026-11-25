"""#850 2차 — 주간 업무·캘린더·일정·예약·프로젝트 이동·고객 접수 헬퍼 단위 테스트 (네트워크 불필요).

응답 모양 변환(주간 버킷 필터·캘린더 접기)과 입력 해석(종류·시각·반복·옵션 코드)이 어긋나면
엉뚱한 일정·예약이 만들어지거나 결과가 조용히 빠지므로 실서버 없이 여기서 가드한다.
"""

import httpx
import pytest

import gdc_mcp.server as s


# ---------------------------------------------------------------------------
# 공통
# ---------------------------------------------------------------------------

def test_drop_empty_keeps_zero():
    assert s._drop_empty({"a": 0, "b": None, "c": "", "d": [], "e": False, "f": "x"}) == {"a": 0, "f": "x"}


MEMBERS = [
    {"user": 1, "full_name": "김선민", "username": "seonmi"},
    {"user": 2, "full_name": "윤가현", "username": "ghyun"},
    {"user": 3, "full_name": "동명이", "username": "a"},
    {"user": 4, "full_name": "동명이", "username": "b"},
]


def test_match_user_by_name_username_id():
    assert s._match_user(MEMBERS, "윤가현", "참석자") == 2
    assert s._match_user(MEMBERS, "SEONMI", "참석자") == 1
    assert s._match_user(MEMBERS, 2, "참석자") == 2
    assert s._match_user(MEMBERS, "2", "참석자") == 2


def test_match_user_me(monkeypatch):
    monkeypatch.setattr(s, "_current_user_id", lambda: 1)
    assert s._match_user(MEMBERS, "나", "참석자") == 1


def test_match_user_ambiguous_and_missing():
    with pytest.raises(ValueError, match="여럿"):
        s._match_user(MEMBERS, "동명이", "참석자")
    with pytest.raises(ValueError, match="멤버가 아닙니다"):
        s._match_user(MEMBERS, "없는사람", "참석자")
    with pytest.raises(ValueError, match="멤버가 아닙니다"):
        s._match_user(MEMBERS, 99, "참석자")


# ---------------------------------------------------------------------------
# 주간 업무
# ---------------------------------------------------------------------------

WEEKLY = {
    "week_start": "2026-11-23", "week_end": "2026-11-29",
    "summary": {"active_project_count": 2, "completed_count": 1, "delayed_count": 3},
    "projects": [
        {"id": 30, "name": "A", "customer_name": "", "risk_status": "DELAYED",
         "last_week": [{"id": 1, "number": 10, "title": "t1", "assignee_id": 1, "assignee_name": "김",
                        "status_chip": "done", "progress": 0, "days_overdue": None, "is_urgent": False}],
         "this_week": [{"id": 2, "number": 11, "title": "t2", "assignee_id": 2, "assignee_name": "윤",
                        "status_chip": "in_progress", "progress": 50, "days_overdue": 2, "is_urgent": True}],
         "risk": [], "undated": []},
        {"id": 31, "name": "B", "risk_status": "ON_TRACK",
         "last_week": [], "this_week": [], "risk": [], "undated": []},
    ],
}


def test_weekly_current_project_only():
    out = s._shape_weekly(WEEKLY, 30, None)
    assert [p["project_id"] for p in out["projects"]] == [30]
    p = out["projects"][0]
    assert p["risk"] == "지연"
    assert p["저번주"][0]["status"] == "완료" and p["저번주"][0]["progress"] == 0
    assert p["이번주"][0]["days_overdue"] == 2 and p["이번주"][0]["is_urgent"] is True
    assert out["workspace_summary"]["delayed"] == 3


def test_weekly_all_projects_skips_empty():
    out = s._shape_weekly(WEEKLY, None, None)
    assert [p["project_id"] for p in out["projects"]] == [30]


def test_weekly_assignee_filter():
    p = s._shape_weekly(WEEKLY, 30, 2)["projects"][0]
    assert p["저번주"] == [] and [x["number"] for x in p["이번주"]] == [11]


# ---------------------------------------------------------------------------
# 캘린더
# ---------------------------------------------------------------------------

def test_collapse_calendar_merges_spread_days():
    items = [
        {"key": "schedule-5", "source": "schedule", "id": 5, "title": "휴가", "date": "2026-11-25",
         "start_date": "2026-11-24", "end_date": "2026-11-26", "all_day": True, "assignees": [{"id": 1, "name": "김"}]},
        {"key": "schedule-5", "source": "schedule", "id": 5, "title": "휴가", "date": "2026-11-26",
         "start_date": "2026-11-24", "end_date": "2026-11-26", "all_day": True, "assignees": [{"id": 1, "name": "김"}]},
        {"key": "task-9", "source": "task", "id": 9, "number": 3, "title": "마감", "date": "2026-11-24",
         "start_date": None, "end_date": None, "all_day": True, "assignee_name": "윤", "assignees": []},
    ]
    out = {x["source"]: x for x in s._collapse_calendar(items)}
    assert len(out) == 2
    task, sched = out["태스크"], out["일정"]
    assert task["start"] == "2026-11-24" and "end" not in task
    assert task["people"] == ["윤"] and task["url"].endswith("/tasks/9")
    assert (sched["start"], sched["end"]) == ("2026-11-24", "2026-11-26") and sched["people"] == ["김"]


def test_collapse_calendar_time_label():
    out = s._collapse_calendar([{"key": "r-1", "source": "reservation", "id": 1, "title": "회의",
                                 "date": "2026-11-25", "all_day": False,
                                 "start_time": "10:00:00", "end_time": "11:30:00"}])
    assert out[0]["time"] == "10:00~11:30"


def test_resolve_cal_sources():
    assert s._resolve_cal_sources(["일정", "task", "고객 이슈"]) == ["schedule", "task", "customer_issue"]
    assert s._resolve_cal_sources(None) is None
    with pytest.raises(ValueError, match="가능한 값"):
        s._resolve_cal_sources(["회의"])


# ---------------------------------------------------------------------------
# 일정
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, None), ("", ""), ("일반", ""), ("휴가", "vacation"), ("외부 일정", "external"),
    ("외부일정", "external"), ("field_work", "field_work"),
])
def test_resolve_schedule_kind(value, expected):
    assert s._resolve_schedule_kind(value) == expected


def test_resolve_schedule_kind_unknown():
    with pytest.raises(ValueError, match="가능한 값"):
        s._resolve_schedule_kind("출장")


def test_parse_hhmm():
    assert s._parse_hhmm("9:05", "t") == "09:05"
    with pytest.raises(ValueError):
        s._parse_hhmm("25:00", "t")


def test_schedule_times_infers_not_all_day():
    assert s._schedule_times(None, "09:00", "10:00") == (False, "09:00", "10:00")
    assert s._schedule_times(None, None, None) == (None, None, None)
    with pytest.raises(ValueError, match="종일"):
        s._schedule_times(True, "09:00", None)


def test_check_range():
    s._check_range("2026-11-24", "2026-11-25", "일정")
    with pytest.raises(ValueError, match="빠를 수 없습니다"):
        s._check_range("2026-11-25", "2026-11-24", "일정")


# ---------------------------------------------------------------------------
# 리소스 예약
# ---------------------------------------------------------------------------

def test_parse_dt():
    assert s._parse_dt("2026-11-25 9:30", "start") == "2026-11-25T09:30"
    assert s._parse_dt("2026-11-25T14:00", "start") == "2026-11-25T14:00"
    with pytest.raises(ValueError, match="형식"):
        s._parse_dt("2026-11-25", "start")


@pytest.mark.parametrize("value,expected", [(None, None), ("매주", "weekly"), ("biweekly", "biweekly"), ("2주마다", "biweekly")])
def test_resolve_recurrence(value, expected):
    assert s._resolve_recurrence(value) == expected


def test_resolve_scope():
    assert s._resolve_scope(None) == "one"
    assert s._resolve_scope("이후 반복 전체") == "series"
    with pytest.raises(ValueError):
        s._resolve_scope("all")


def _http_error(status, body):
    req = httpx.Request("POST", "http://x/api/reservations/")
    return httpx.HTTPStatusError("e", request=req, response=httpx.Response(status, json=body, request=req))


def test_reservation_error_code_mapping():
    err = s._reservation_error(_http_error(400, {"start_at": ["past"]}))
    assert isinstance(err, ValueError) and "지난 시각" in str(err)
    err = s._reservation_error(_http_error(400, {"detail": "disabled"}))
    assert "꺼져" in str(err)


def test_reservation_error_conflict():
    body = {"code": "conflict", "conflicts": [{
        "start_at": "2026-11-25T10:00:00+09:00", "end_at": "2026-11-25T11:00:00+09:00", "remaining": 0,
        "reservations": [{"id": 1, "title": "주간회의", "start_at": "2026-11-25T09:30:00+09:00",
                          "end_at": "2026-11-25T10:30:00+09:00"}]}]}
    msg = str(s._reservation_error(_http_error(409, body)))
    assert "겹칩니다" in msg and "주간회의" in msg and "09:30~10:30" in msg


def test_reservation_error_other_field_message():
    assert "보유 대수를 넘었습니다" in str(s._reservation_error(_http_error(400, {"quantity": ["보유 대수를 넘었습니다."]})))


# ---------------------------------------------------------------------------
# 프로젝트 이동
# ---------------------------------------------------------------------------

def test_move_effects():
    task = {"status": "review", "priority": "high", "task_type": "dev", "assignee": 7, "assignee_name": "홍",
            "tag_list": [{"name": "버그"}]}
    target = {"task_statuses": [{"name": "open"}], "task_priorities": [{"name": "high"}],
              "task_types": [{"name": "other"}], "members": [{"user": 1}]}
    effects = " / ".join(s._move_effects(task, target))
    assert "번호" in effects and "버그" in effects and "'review'" in effects
    assert "task_type 'dev'" in effects and "priority" not in effects and "홍" in effects


def test_move_effects_minimal():
    task = {"status": "open", "priority": "high", "task_type": "other", "assignee": 1, "tag_list": []}
    target = {"task_statuses": [{"name": "open"}], "task_priorities": [{"name": "high"}],
              "task_types": [{"name": "other"}], "members": [{"user": 1}]}
    assert len(s._move_effects(task, target)) == 1  # 번호 재발급만


# ---------------------------------------------------------------------------
# 고객 접수 옵션
# ---------------------------------------------------------------------------

OPTS = {
    "status": [{"code": "open", "name": "접수", "name_en": "Open", "is_active": True},
               {"code": "old", "name": "예전", "is_active": False}],
    "issue_type": [], "priority": [],
}


def test_resolve_issue_option():
    assert s._resolve_issue_option(OPTS, "status", "접수") == "open"
    assert s._resolve_issue_option(OPTS, "status", "OPEN") == "open"
    with pytest.raises(ValueError, match="가능한 값: 접수"):
        s._resolve_issue_option(OPTS, "status", "예전")  # 비활성은 지정 불가
    assert s._resolve_issue_option(OPTS, "status", "예전", assign=False) == "old"  # 거르기는 가능


def test_issue_label():
    assert s._issue_label(OPTS, "status", "open") == "접수"
    assert s._issue_label(OPTS, "status", "zzz") == "zzz"


def test_collapse_calendar_groups_by_source_and_id_not_key():
    """서버 key는 펼친 날짜마다 다르다(실측) — (종류, id)로 묶어야 한 줄이 된다."""
    base = {"source": "schedule", "id": 18, "title": "외근", "start_date": "2026-11-26", "end_date": "2026-11-27"}
    out = s._collapse_calendar([{**base, "key": "schedule-18-2026-11-26", "date": "2026-11-26"},
                                {**base, "key": "schedule-18-2026-11-27", "date": "2026-11-27"}])
    assert len(out) == 1 and (out[0]["start"], out[0]["end"]) == ("2026-11-26", "2026-11-27")


def test_pick_issue_number_is_per_customer():
    """접수 번호는 고객사마다 따로(실측: #1이 고객사 3곳) — 여럿이면 고르지 않는다."""
    hits = [{"id": 138, "number": 1, "customer": 9, "customer_name": "테크노소프트"},
            {"id": 93, "number": 1, "customer": 12, "customer_name": "헬스케어플러스"},
            {"id": 70, "number": 11, "customer": 9, "customer_name": "테크노소프트"}]
    with pytest.raises(ValueError, match="고객사 2곳"):
        s._pick_issue(hits, 1)
    assert s._pick_issue(hits, 11)["id"] == 70
    with pytest.raises(ValueError, match="찾을 수 없습니다"):
        s._pick_issue(hits, 5)
