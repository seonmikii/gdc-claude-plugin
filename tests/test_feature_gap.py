"""#850 플러그인 보강 헬퍼 단위 테스트 (서버·인증·네트워크 불필요).

태그 해석·병합(tag_ids는 서버에서 통째 교체), 고객사 자동 지정(#838 웹 규칙), #번호 해석,
연관 유형·검색 범위 해석 — 어긋나면 태그가 통째로 날아가거나 엉뚱한 태스크를 고치게 되므로 여기서 가드한다.
"""

import pytest

from gdc_mcp.server import (
    _SUGGESTION_STATUS_LABELS,
    _auto_customer,
    _merge_tag_ids,
    _parse_task_number,
    _project_tags,
    _resolve_link_type,
    _resolve_search_scope,
    _resolve_suggestion_status,
    _resolve_tags,
    _search_params,
)

PROJECT = {
    "name": "테스트",
    "preset": "issue",
    "tags": [
        {"id": 12, "name": "Backend", "order": 2},
        {"id": 11, "name": "버그", "order": 1},
        {"id": 13, "name": "UI", "order": 2},
    ],
}


# ---------------------------------------------------------------------------
# 태그
# ---------------------------------------------------------------------------

def test_project_tags_sorted_by_order_then_id():
    assert [g["id"] for g in _project_tags(PROJECT)] == [11, 12, 13]


def test_resolve_tags_by_name_case_insensitive_and_id():
    assert _resolve_tags(PROJECT, ["backend", 13, "11"]) == [12, 13, 11]


def test_resolve_tags_dedupes():
    assert _resolve_tags(PROJECT, ["버그", 11]) == [11]


def test_resolve_tags_unknown_name_lists_available():
    with pytest.raises(ValueError, match="가능한 태그: 버그"):
        _resolve_tags(PROJECT, ["없는태그"])


def test_resolve_tags_rejects_other_project_id():
    with pytest.raises(ValueError, match="'99'"):
        _resolve_tags(PROJECT, [99])


def test_resolve_tags_empty():
    assert _resolve_tags(PROJECT, None) == []
    assert _resolve_tags(PROJECT, []) == []


def test_resolve_tags_project_without_tags_hints_settings():
    with pytest.raises(ValueError, match="프로젝트 설정"):
        _resolve_tags({"tags": []}, ["버그"])


def test_merge_add_keeps_existing():
    assert _merge_tag_ids([11, 12], add=[13]) == [11, 12, 13]


def test_merge_add_existing_is_noop():
    assert _merge_tag_ids([11], add=[11]) == [11]


def test_merge_remove():
    assert _merge_tag_ids([11, 12, 13], remove=[12]) == [11, 13]


def test_merge_add_and_remove_together():
    assert _merge_tag_ids([11, 12], add=[13], remove=[11]) == [12, 13]


def test_merge_replace():
    assert _merge_tag_ids([11, 12], tags=[13]) == [13]


def test_merge_replace_empty_clears_all():
    assert _merge_tag_ids([11, 12], tags=[]) == []


def test_merge_replace_with_add_is_error():
    with pytest.raises(ValueError, match="함께 쓸 수 없습니다"):
        _merge_tag_ids([11], tags=[12], add=[13])


# ---------------------------------------------------------------------------
# 고객사 자동 지정 (#838 — TaskCreateDialog 조건)
# ---------------------------------------------------------------------------

AUTO = {"preset": "issue", "auto_assign_customer": True, "customer_hidden": False, "customer": 7}


def test_auto_customer_applies():
    assert _auto_customer(AUTO) == 7


def test_auto_customer_off():
    assert _auto_customer({**AUTO, "auto_assign_customer": False}) is None


def test_auto_customer_wbs_excluded():
    assert _auto_customer({**AUTO, "preset": "wbs"}) is None


def test_auto_customer_hidden_excluded():
    assert _auto_customer({**AUTO, "customer_hidden": True}) is None


def test_auto_customer_no_project_customer():
    assert _auto_customer({**AUTO, "customer": None}) is None


# ---------------------------------------------------------------------------
# #번호 해석 — 숫자만은 내부 id
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [("#850", 850), ("# 850", 850), (" #12 ", 12)])
def test_parse_task_number(value, expected):
    assert _parse_task_number(value) == expected


@pytest.mark.parametrize("value", [850, "850", "제목 #850", "#", "#85a0", True])
def test_parse_task_number_not_number(value):
    assert _parse_task_number(value) is None


# ---------------------------------------------------------------------------
# 연관 유형 · 검색 범위
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, "related"), ("", "related"), ("related", "related"), ("관련", "related"),
    ("BLOCKS", "blocks"), ("차단", "blocks"), ("차단됨", "blocked_by"), ("blocked_by", "blocked_by"),
])
def test_resolve_link_type(value, expected):
    assert _resolve_link_type(value) == expected


def test_resolve_link_type_unknown():
    with pytest.raises(ValueError, match="가능한 값"):
        _resolve_link_type("parent")


@pytest.mark.parametrize("value,expected", [
    (None, None), ("all", None), ("전체", None), ("content", "content"), ("제목+내용", "content"),
    ("댓글", "comment"), ("comment", "comment"), ("번호", "number"),
])
def test_resolve_search_scope(value, expected):
    assert _resolve_search_scope(value) == expected


def test_resolve_search_scope_unknown():
    with pytest.raises(ValueError, match="가능한 값"):
        _resolve_search_scope("작성자")


def test_search_params_new_filters():
    p = _search_params(31, query="로그인", tag_ids=[11, 12], search_scope="comment", is_report_task=True)
    assert p["tags"] == "11,12"
    assert p["search_scope"] == "comment"
    assert p["is_report_task"] == "true"


def test_search_params_report_false():
    assert _search_params(31, is_report_task=False)["is_report_task"] == "false"


def test_search_params_scope_requires_query():
    with pytest.raises(ValueError, match="query"):
        _search_params(31, search_scope="comment")


def test_search_params_defaults_unchanged():
    assert _search_params(31) == {"project": 31, "page_size": 20}


# ---------------------------------------------------------------------------
# 건의 상태 '답변완료' (#787)
# ---------------------------------------------------------------------------

def test_suggestion_answered_label():
    assert _SUGGESTION_STATUS_LABELS["answered"] == "답변완료"
    assert _resolve_suggestion_status("답변완료") == "answered"


# ---------------------------------------------------------------------------
# 휴지통 #번호 해석
# ---------------------------------------------------------------------------

def test_find_trashed_by_number():
    from gdc_mcp.server import _find_trashed
    items = [{"id": 501, "number": 850, "title": "A"}, {"id": 502, "number": 851, "title": "B"}]
    assert _find_trashed(items, "#851") == (502, items[1])
    with pytest.raises(ValueError, match="#999"):
        _find_trashed(items, "#999")
