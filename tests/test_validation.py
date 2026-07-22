"""server.py의 순수 검증/변환 헬퍼 단위 테스트 (서버·인증·네트워크 불필요).

도구 레벨 입력 검증(날짜 순서·미래 종료일 차단, 멤버 이름 해석)과 본문 메타 단계
필터는 잘못되면 운영 데이터에 그대로 반영되므로, 실서버 없이 여기서 가드한다.

import 시 server.py의 FastMCP/GdcClient가 초기화되지만 네트워크·서버 기동은 없다(.run() 미호출).
"""

import pytest

from gdc_mcp.server import (
    _build_comment_html,
    _parse_date,
    _resolve_members,
    _resolve_mention_usernames,
    _strip_meta_steps,
    _validate_dates,
)


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

def test_parse_date_valid():
    import datetime

    assert _parse_date("2026-07-20", "예상 시작일") == datetime.date(2026, 7, 20)


def test_parse_date_bad_format_raises():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        _parse_date("2026/07/20", "예상 시작일")


# ---------------------------------------------------------------------------
# _validate_dates — 날짜 순서 + 미래 종료일 차단
# ---------------------------------------------------------------------------

def test_validate_dates_ok():
    # 순서 정상, 실제 종료일은 과거 → 통과(예외 없음)
    _validate_dates("2026-01-01", "2026-02-01", "2000-01-01", "2000-02-01")


def test_validate_dates_partial_args_ok():
    # 일부만 전달되면 비교 대상이 없어 통과
    _validate_dates(planned_start="2026-01-01")


def test_planned_start_after_end_raises():
    with pytest.raises(ValueError, match="예상 시작일"):
        _validate_dates(planned_start="2026-03-01", planned_end="2026-01-01")


def test_actual_start_after_end_raises():
    with pytest.raises(ValueError, match="실제 시작일"):
        _validate_dates(actual_start="2000-03-01", actual_end="2000-01-01")


def test_actual_end_in_future_raises():
    with pytest.raises(ValueError, match="미래"):
        _validate_dates(actual_end="2999-12-31")


def test_actual_end_in_past_ok():
    _validate_dates(actual_end="2000-01-01")  # 예외 없어야 함


# ---------------------------------------------------------------------------
# _strip_meta_steps — [작업 내용] 밑 프로세스 메타 블렛 제거
# ---------------------------------------------------------------------------

def test_strip_removes_meta_bullets():
    desc = """요약 한 줄

[작업 내용]
- 로그인 화면 구현
- 빌드 후 배포
- 단위 테스트 작성
- 커밋 및 푸시
- INDEX.md 이력 추가
- 동작 확인
"""
    out = _strip_meta_steps(desc)
    assert "로그인 화면 구현" in out       # 실제 산출물 → 유지
    assert "빌드 후 배포" not in out         # 빌드 → 제거
    assert "단위 테스트 작성" not in out     # 테스트 → 제거
    assert "커밋 및 푸시" not in out         # 커밋/푸시 → 제거
    assert "INDEX.md 이력 추가" not in out   # index.md/이력 추가 → 제거
    assert "동작 확인" not in out            # 동작 확인 → 제거


def test_strip_keeps_summary_and_non_bullets():
    desc = "요약 한 줄\n\n[작업 내용]\n- 실제 기능 A\n"
    out = _strip_meta_steps(desc)
    assert "요약 한 줄" in out
    assert "[작업 내용]" in out
    assert "실제 기능 A" in out


def test_strip_ignores_bullets_before_header():
    # [작업 내용] 헤더 이전의 빌드 블렛은 건드리지 않는다
    desc = "- 빌드 관련 서문 블렛\n\n[작업 내용]\n- 실제 기능\n"
    out = _strip_meta_steps(desc)
    assert "빌드 관련 서문 블렛" in out


def test_strip_no_header_keeps_all_bullets():
    # [작업 내용] 헤더가 없으면 메타 키워드 블렛도 제거하지 않는다
    # (끝 개행은 splitlines/join으로 정규화되므로 내용 보존만 확인)
    desc = "- 빌드\n- 커밋\n"
    out = _strip_meta_steps(desc)
    assert "- 빌드" in out
    assert "- 커밋" in out


# ---------------------------------------------------------------------------
# _resolve_members — project dict 주입으로 client 호출 스킵(순수)
# ---------------------------------------------------------------------------

PROJECT = {
    "members": [
        {"user": 101, "full_name": "김철수", "username": "chulsoo"},
        {"user": 202, "full_name": "이영희", "username": "younghee"},
    ]
}


def test_resolve_member_by_name():
    assignee, parts = _resolve_members(1, "김철수", None, project=PROJECT)
    assert assignee == 101
    assert parts is None


def test_resolve_member_by_username():
    assignee, _ = _resolve_members(1, "younghee", None, project=PROJECT)
    assert assignee == 202


def test_resolve_member_by_int_id():
    assignee, _ = _resolve_members(1, 101, None, project=PROJECT)
    assert assignee == 101


def test_resolve_member_by_digit_string():
    assignee, _ = _resolve_members(1, "202", None, project=PROJECT)
    assert assignee == 202


def test_resolve_participants_list():
    _, parts = _resolve_members(1, None, ["김철수", 202], project=PROJECT)
    assert parts == [101, 202]


def test_resolve_non_member_raises():
    with pytest.raises(ValueError, match="멤버가 아닙니다"):
        _resolve_members(1, "박모름", None, project=PROJECT)


def test_resolve_both_none_skips():
    # 둘 다 없으면 project 조회 없이 원본 반환
    assert _resolve_members(1, None, None) == (None, None)


# ---------------------------------------------------------------------------
# _resolve_mention_usernames — 이름/id → username (댓글 멘션용)
# ---------------------------------------------------------------------------

def test_mention_resolve_by_name():
    assert _resolve_mention_usernames(1, ["김철수"], project=PROJECT) == ["chulsoo"]


def test_mention_resolve_by_username():
    assert _resolve_mention_usernames(1, ["younghee"], project=PROJECT) == ["younghee"]


def test_mention_resolve_by_id_mixed():
    assert _resolve_mention_usernames(1, [101, "202"], project=PROJECT) == ["chulsoo", "younghee"]


def test_mention_resolve_non_member_raises():
    with pytest.raises(ValueError, match="멤버가 아닙니다"):
        _resolve_mention_usernames(1, ["박모름"], project=PROJECT)


def test_mention_resolve_empty_skips():
    assert _resolve_mention_usernames(1, None) == []
    assert _resolve_mention_usernames(1, []) == []


# ---------------------------------------------------------------------------
# _build_comment_html — 본문 HTML 변환 + 멘션 선두 주입
# ---------------------------------------------------------------------------

def test_build_comment_plain_no_mentions():
    assert _build_comment_html("안녕하세요", []) == "<p>안녕하세요</p>"


def test_build_comment_prepends_mentions():
    out = _build_comment_html("확인 부탁", ["chulsoo", "younghee"])
    assert out == "<p>@chulsoo @younghee</p><p>확인 부탁</p>"


def test_build_comment_passthrough_html_with_mention():
    # 이미 HTML이면 통과하고, 멘션 문단만 앞에 붙는다
    out = _build_comment_html("<p>이미 HTML</p>", ["chulsoo"])
    assert out == "<p>@chulsoo</p><p>이미 HTML</p>"
