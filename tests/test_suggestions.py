"""건의사항 도구의 순수 검증/변환 헬퍼 단위 테스트 (서버·인증·네트워크 불필요).

제목 자동 생성·본문 길이·분류/상태 해석은 잘못되면 서버 400이나 엉뚱한 건의로 이어지므로
도구 레벨에서 막는다(입력 검증은 도구 레벨 규칙).
"""

import pytest

from gdc_mcp.server import (
    _resolve_suggestion_category,
    _resolve_suggestion_status,
    _suggestion_title,
    _validate_suggestion_content,
)


# ---------------------------------------------------------------------------
# _validate_suggestion_content — 5~2000자
# ---------------------------------------------------------------------------

def test_validate_content_strips_surrounding_whitespace():
    assert _validate_suggestion_content("  검색 정렬이 이상합니다  ") == "검색 정렬이 이상합니다"


def test_validate_content_too_short_raises():
    with pytest.raises(ValueError, match="5자"):
        _validate_suggestion_content("짧다")


def test_validate_content_whitespace_only_raises():
    with pytest.raises(ValueError, match="5자"):
        _validate_suggestion_content("        ")


def test_validate_content_too_long_raises():
    with pytest.raises(ValueError, match="2000자"):
        _validate_suggestion_content("가" * 2001)


def test_validate_content_at_upper_bound_passes():
    assert len(_validate_suggestion_content("가" * 2000)) == 2000


# ---------------------------------------------------------------------------
# _suggestion_title — 생략 시 본문 첫 줄(40자), 명시 시 200자 상한
# ---------------------------------------------------------------------------

def test_title_from_first_line_when_omitted():
    assert _suggestion_title("검색 정렬이 이상해요\n최신순인데 오래된 게 위에 옵니다") == "검색 정렬이 이상해요"


def test_title_skips_leading_blank_lines():
    assert _suggestion_title("\n\n  첫 줄입니다\n둘째 줄") == "첫 줄입니다"


def test_title_collapses_inner_whitespace():
    assert _suggestion_title("검색     정렬이\t이상해요") == "검색 정렬이 이상해요"


def test_title_auto_cut_to_40_chars():
    assert _suggestion_title("가" * 60) == "가" * 40


def test_explicit_title_wins():
    assert _suggestion_title("본문 첫 줄", title="직접 쓴 제목") == "직접 쓴 제목"


def test_explicit_title_cut_to_server_limit_200():
    assert len(_suggestion_title("본문 첫 줄", title="나" * 250)) == 200


def test_blank_explicit_title_falls_back_to_content():
    assert _suggestion_title("본문 첫 줄", title="   ") == "본문 첫 줄"


# ---------------------------------------------------------------------------
# _resolve_suggestion_category — 코드/한글 라벨, 기본값 improvement
# ---------------------------------------------------------------------------

def test_category_defaults_to_improvement():
    assert _resolve_suggestion_category(None) == "improvement"


def test_category_accepts_server_code():
    assert _resolve_suggestion_category("bug") == "bug"


def test_category_accepts_korean_label():
    assert _resolve_suggestion_category("기능 요청") == "feature"


def test_category_invalid_raises_with_options():
    with pytest.raises(ValueError, match="improvement"):
        _resolve_suggestion_category("문의")


# ---------------------------------------------------------------------------
# _resolve_suggestion_status — 필터용(생략 가능)
# ---------------------------------------------------------------------------

def test_status_none_stays_none():
    assert _resolve_suggestion_status(None) is None


def test_status_accepts_server_code():
    assert _resolve_suggestion_status("reviewing") == "reviewing"


def test_status_accepts_korean_label():
    assert _resolve_suggestion_status("반영완료") == "completed"


def test_status_invalid_raises_with_options():
    with pytest.raises(ValueError, match="received"):
        _resolve_suggestion_status("접수중")
