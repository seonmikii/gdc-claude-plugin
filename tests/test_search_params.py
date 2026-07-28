"""search_tasks의 질의 파라미터 조립(_search_params) 단위 테스트 (네트워크 불필요).

서버 필터 규약(CSV BaseInFilter·planned_end_date_to·root_only)과 어긋나면 검색 결과가
조용히 틀어지므로(누락/과다) 실서버 없이 여기서 가드한다.
"""

import datetime

import pytest

from gdc_mcp.server import _SEARCH_MAX_PAGE_SIZE, _search_params

YESTERDAY = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------
# 기본 조립
# ---------------------------------------------------------------------------

def test_defaults_only_project_and_page_size():
    assert _search_params(31) == {"project": 31, "page_size": 20}


def test_query_maps_to_search():
    assert _search_params(31, query="로그인")["search"] == "로그인"


def test_limit_maps_to_page_size():
    assert _search_params(31, limit=50)["page_size"] == 50


def test_limit_capped_at_server_max():
    assert _search_params(31, limit=999)["page_size"] == _SEARCH_MAX_PAGE_SIZE


# ---------------------------------------------------------------------------
# 리스트 필터 → CSV (서버 BaseInFilter)
# ---------------------------------------------------------------------------

def test_list_filters_join_as_csv():
    p = _search_params(
        31,
        status=["진행", "검토"],
        priority=["높음"],
        task_type=["개발", "기획"],
        participant_ids=[101, 202],
    )
    assert p["status"] == "진행,검토"
    assert p["priority"] == "높음"
    assert p["task_type"] == "개발,기획"
    assert p["participant"] == "101,202"


def test_scalar_ids_pass_through():
    p = _search_params(31, assignee_id=101, customer_id=7)
    assert p["assignee"] == 101
    assert p["customer"] == 7


def test_empty_lists_are_omitted():
    p = _search_params(31, status=[], priority=[], task_type=[], participant_ids=[])
    assert "status" not in p and "priority" not in p
    assert "task_type" not in p and "participant" not in p


# ---------------------------------------------------------------------------
# not_finished — status 명시가 우선
# ---------------------------------------------------------------------------

def test_not_finished_names_used_when_status_absent():
    p = _search_params(31, not_finished_names=["대기", "진행"])
    assert p["status"] == "대기,진행"


def test_explicit_status_wins_over_not_finished():
    p = _search_params(31, status=["완료"], not_finished_names=["대기", "진행"])
    assert p["status"] == "완료"


# ---------------------------------------------------------------------------
# overdue / undated
# ---------------------------------------------------------------------------

def test_overdue_becomes_server_end_date_filter():
    p = _search_params(31, overdue=True)
    assert p["planned_end_date_to"] == YESTERDAY


def test_overdue_does_not_imply_not_finished():
    # overdue와 not_finished는 독립 — status를 임의로 붙이지 않는다
    assert "status" not in _search_params(31, overdue=True)


def test_overdue_with_later_end_to_takes_yesterday():
    p = _search_params(31, planned_end_to="2999-12-31", overdue=True)
    assert p["planned_end_date_to"] == YESTERDAY


def test_overdue_with_earlier_end_to_keeps_it():
    p = _search_params(31, planned_end_to="2000-01-01", overdue=True)
    assert p["planned_end_date_to"] == "2000-01-01"


def test_undated_fetches_max_page_regardless_of_limit():
    # 서버에 "날짜 없음" 필터가 없어 클라이언트에서 거른다 → 넉넉히 선취
    assert _search_params(31, undated=True, limit=5)["page_size"] == _SEARCH_MAX_PAGE_SIZE


def test_planned_end_range_passes_through():
    p = _search_params(31, planned_end_from="2026-07-01", planned_end_to="2026-07-31")
    assert p["planned_end_date_from"] == "2026-07-01"
    assert p["planned_end_date_to"] == "2026-07-31"


def test_bad_date_format_raises():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        _search_params(31, planned_end_from="2026/07/01")


def test_reversed_date_range_raises():
    with pytest.raises(ValueError, match="늦을 수 없습니다"):
        _search_params(31, planned_end_from="2026-08-01", planned_end_to="2026-07-01")


# ---------------------------------------------------------------------------
# root_only — query와 배타 (BM25는 매칭 하위를 부모로 치환하지 않는다)
# ---------------------------------------------------------------------------

def test_root_only_alone_is_allowed():
    assert _search_params(31, root_only=True)["root_only"] == "true"


def test_query_with_root_only_raises():
    with pytest.raises(ValueError, match="함께 쓸 수 없습니다"):
        _search_params(31, query="로그인", root_only=True)


# ---------------------------------------------------------------------------
# ordering 화이트리스트 (서버는 미허용 값을 조용히 무시 → 여기서 안내)
# ---------------------------------------------------------------------------

def test_ordering_allowed_field():
    assert _search_params(31, ordering="planned_end_date")["ordering"] == "planned_end_date"


def test_ordering_descending_prefix_allowed():
    assert _search_params(31, ordering="-number")["ordering"] == "-number"


def test_ordering_unknown_field_raises():
    with pytest.raises(ValueError, match="지원하지 않습니다"):
        _search_params(31, ordering="assignee_name")


def test_ordering_omitted_leaves_server_default():
    assert "ordering" not in _search_params(31)
