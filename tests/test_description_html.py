"""description_to_html 순수 함수 단위 테스트 (서버·인증·네트워크 불필요).

task_from_doc가 라벨 섹션 템플릿(평문)을 GDC 리치텍스트(HTML)로 변환할 때 쓴다.
GDC description은 리치텍스트(HTML)로 저장·렌더링되므로(실증 확인: 태스크 #292/#273),
평문을 그대로 보내면 본문이 뭉개진다 — 이 변환이 조용히 깨지면 태스크 본문이 깨진다.
"""

from gdc_mcp.doc_utils import (
    description_to_html,
    html_to_text,
    is_html,
    mention_numbers,
    normalize_description,
)


def test_label_and_paragraph():
    """`[라벨]` 줄은 대괄호를 떼고 볼드 `<p><strong>`, 아래 텍스트는 `<p>`."""
    out = description_to_html("[요약]\n문서 요약")
    assert out == "<p><strong>요약</strong></p><p>문서 요약</p>"


def test_consecutive_bullets_grouped_in_one_ul():
    out = description_to_html("[작업 내용]\n- 첫째\n- 둘째")
    assert out == "<p><strong>작업 내용</strong></p><ul><li><p>첫째</p></li><li><p>둘째</p></li></ul>"


def test_sections_separated_by_empty_paragraph():
    """빈 줄로 구분된 섹션 사이에는 GDC 네이티브 형식대로 `<p></p>`를 넣는다."""
    text = "[요약]\n요약 본문\n\n[작업 내용]\n- 단계 1"
    out = description_to_html(text)
    assert out == (
        "<p><strong>요약</strong></p><p>요약 본문</p>"
        "<p></p>"
        "<p><strong>작업 내용</strong></p><ul><li><p>단계 1</p></li></ul>"
    )


def test_full_template_with_as_is_to_be():
    text = (
        "[요약]\n한 줄 요약\n\n"
        "[AS-IS]\n전 상황\n\n"
        "[TO-BE]\n후 상황\n\n"
        "[작업 내용]\n- 산출물 1\n- 산출물 2"
    )
    out = description_to_html(text)
    assert out == (
        "<p><strong>요약</strong></p><p>한 줄 요약</p>"
        "<p></p>"
        "<p><strong>AS-IS</strong></p><p>전 상황</p>"
        "<p></p>"
        "<p><strong>TO-BE</strong></p><p>후 상황</p>"
        "<p></p>"
        "<p><strong>작업 내용</strong></p><ul><li><p>산출물 1</p></li><li><p>산출물 2</p></li></ul>"
    )


def test_escapes_angle_brackets_and_amp():
    """작업 문서 본문의 부등호/코드가 태그로 오인·주입되지 않도록 이스케이프."""
    out = description_to_html("[작업 내용]\n- progress<100 && a>b")
    assert out == (
        "<p><strong>작업 내용</strong></p>"
        "<ul><li><p>progress&lt;100 &amp;&amp; a&gt;b</p></li></ul>"
    )


def test_escapes_label_and_paragraph_text():
    out = description_to_html("[요약]\n<p>태그 그대로</p>")
    assert out == "<p><strong>요약</strong></p><p>&lt;p&gt;태그 그대로&lt;/p&gt;</p>"


def test_empty_input_returns_empty_string():
    assert description_to_html("") == ""
    assert description_to_html("   \n  \n") == ""


def test_old_template_without_summary_label():
    """구 템플릿(라벨 없는 첫 줄 요약 + [작업 내용])도 깨지지 않게 변환."""
    text = "문서 한 줄 요약\n\n[작업 내용]\n- 단계 1"
    out = description_to_html(text)
    assert out == (
        "<p>문서 한 줄 요약</p>"
        "<p></p>"
        "<p><strong>작업 내용</strong></p><ul><li><p>단계 1</p></li></ul>"
    )


def test_bullet_then_paragraph_closes_ul():
    """블렛 뒤에 일반 문단이 오면 `<ul>`을 닫고 `<p>`로 이어간다."""
    out = description_to_html("- 항목\n일반 문단")
    assert out == "<ul><li><p>항목</p></li></ul><p>일반 문단</p>"


# ---------------------------------------------------------------------------
# URL 자동 연동 — 평문의 http/https 맨 URL을 <a href>로 (#409, description·댓글 공통)
# ---------------------------------------------------------------------------

def test_bare_url_in_bullet_becomes_anchor():
    """블렛의 맨 URL은 클릭 가능한 <a>로 변환된다."""
    out = description_to_html("- https://gdc.gemiso.com/tasks/14957")
    assert out == (
        "<ul><li><p>"
        '<a target="_blank" rel="noopener noreferrer" '
        'href="https://gdc.gemiso.com/tasks/14957">https://gdc.gemiso.com/tasks/14957</a>'
        "</p></li></ul>"
    )


def test_url_inside_paragraph_text():
    """문장 속 URL만 링크로 감싸고 앞뒤 텍스트는 그대로 둔다."""
    out = description_to_html("본문 https://example.com 참고")
    assert out == (
        '<p>본문 <a target="_blank" rel="noopener noreferrer" '
        'href="https://example.com">https://example.com</a> 참고</p>'
    )


def test_url_query_ampersand_is_escaped_in_href_and_text():
    """URL의 &는 href·표시 텍스트 모두 &amp;로 이스케이프(유효 HTML)."""
    out = description_to_html("- https://x.com/a?b=1&c=2")
    assert out == (
        "<ul><li><p>"
        '<a target="_blank" rel="noopener noreferrer" '
        'href="https://x.com/a?b=1&amp;c=2">https://x.com/a?b=1&amp;c=2</a>'
        "</p></li></ul>"
    )


def test_trailing_punctuation_excluded_from_url():
    """URL 뒤 마침표·쉼표·닫는 괄호는 링크에 포함하지 않는다."""
    out = description_to_html("참고 https://example.com.")
    assert out == (
        '<p>참고 <a target="_blank" rel="noopener noreferrer" '
        'href="https://example.com">https://example.com</a>.</p>'
    )


def test_non_url_angle_text_not_linked_and_still_escaped():
    """URL이 아닌 부등호 텍스트는 링크 없이 그대로 이스케이프(오탐 없음)."""
    out = description_to_html("- progress<100 && a>b")
    assert out == "<ul><li><p>progress&lt;100 &amp;&amp; a&gt;b</p></li></ul>"


def test_label_line_with_brackets_not_linkified():
    """라벨 마커(`[...]`)는 URL 처리 대상이 아니다(형식 유지)."""
    out = description_to_html("[작업 내용]\n- https://example.com")
    assert out == (
        "<p><strong>작업 내용</strong></p>"
        "<ul><li><p>"
        '<a target="_blank" rel="noopener noreferrer" '
        'href="https://example.com">https://example.com</a>'
        "</p></li></ul>"
    )


def test_comment_path_autolinks_via_normalize():
    """댓글 경로(normalize_description)도 같은 자동 연동을 받는다."""
    out = normalize_description("확인 https://example.com")
    assert out == (
        '<p>확인 <a target="_blank" rel="noopener noreferrer" '
        'href="https://example.com">https://example.com</a></p>'
    )


# ---------------------------------------------------------------------------
# 태스크 언급(#N) 자동 연동 — resolve_task 콜백 주입(서버 계층에서 client 백엔드)
# ---------------------------------------------------------------------------

def _resolver(mapping):
    """번호→(url, title) 매핑을 흉내내는 순수 콜백(미해결은 None)."""
    return lambda number: mapping.get(number)


def test_mention_linked_with_title_in_parens():
    """`#N`만 링크하고 바로 뒤에 `(제목)`을 평문으로 삽입한다."""
    r = _resolver({409: ("https://gdc.gemiso.com/tasks/15434", "HTML 변환시 링크 연동")})
    out = description_to_html("이슈 #409 참고", resolve_task=r)
    assert out == (
        '<p>이슈 <a target="_blank" rel="noopener noreferrer" '
        'href="https://gdc.gemiso.com/tasks/15434">#409</a> (HTML 변환시 링크 연동) 참고</p>'
    )


def test_mention_unresolved_number_stays_plaintext():
    """현재 프로젝트에 없는 번호(resolver None)는 평문 `#N`으로 둔다."""
    r = _resolver({})
    out = description_to_html("- 없는 #999 링크 안됨", resolve_task=r)
    assert out == "<ul><li><p>없는 #999 링크 안됨</p></li></ul>"


def test_mention_without_resolver_is_plaintext():
    """resolver 미주입(None)이면 `#N`은 손대지 않는다(하위 호환) — URL만 연동."""
    out = description_to_html("보류 #409 이지만 https://example.com 는 링크")
    assert out == (
        '<p>보류 #409 이지만 <a target="_blank" rel="noopener noreferrer" '
        'href="https://example.com">https://example.com</a> 는 링크</p>'
    )


def test_mention_boundary_no_false_positive():
    """색상 `#fff`·단어 뒤 `v1#2`는 태스크 언급이 아니다."""
    r = _resolver({2: ("https://x/2", "T2"), 3: ("https://x/3", "T3")})
    out = description_to_html("색상 #fff 와 버전 v1#2", resolve_task=r)
    assert out == "<p>색상 #fff 와 버전 v1#2</p>"


def test_mention_inside_url_not_double_linked():
    """URL 프래그먼트(`...#409`)는 URL로만 링크되고 별도 언급 처리 안 함."""
    r = _resolver({409: ("https://gdc.gemiso.com/tasks/15434", "제목")})
    out = description_to_html("- https://gdc.gemiso.com/tasks/15434#409", resolve_task=r)
    assert out == (
        "<ul><li><p>"
        '<a target="_blank" rel="noopener noreferrer" '
        'href="https://gdc.gemiso.com/tasks/15434#409">https://gdc.gemiso.com/tasks/15434#409</a>'
        "</p></li></ul>"
    )


def test_mention_title_is_escaped():
    """제목의 `<`·`&`는 평문 삽입 시 이스케이프."""
    r = _resolver({7: ("https://x/7", "a<b & c")})
    out = description_to_html("보라 #7", resolve_task=r)
    assert out == (
        '<p>보라 <a target="_blank" rel="noopener noreferrer" '
        'href="https://x/7">#7</a> (a&lt;b &amp; c)</p>'
    )


def test_mention_repeated_both_linked():
    """같은 번호가 여러 번 나와도 모두 링크된다."""
    r = _resolver({5: ("https://x/5", "다섯")})
    out = description_to_html("#5 와 또 #5", resolve_task=r)
    assert out == (
        '<p><a target="_blank" rel="noopener noreferrer" href="https://x/5">#5</a> (다섯) '
        '와 또 <a target="_blank" rel="noopener noreferrer" href="https://x/5">#5</a> (다섯)</p>'
    )


def test_mention_numbers_dedup_and_boundary():
    """번호 추출은 디둡하고 경계 규칙(색상/단어 뒤)을 지킨다."""
    assert mention_numbers("이슈 #409 와 #409 또 #5, 색상 #fff, v1#2") == {409, 5}
    assert mention_numbers("") == set()


def test_normalize_description_threads_resolver():
    """normalize_description도 resolver를 아래로 전달한다(댓글·본문 공통 경로)."""
    r = _resolver({409: ("https://gdc.gemiso.com/tasks/15434", "제목")})
    out = normalize_description("확인 #409", resolve_task=r)
    assert out == (
        '<p>확인 <a target="_blank" rel="noopener noreferrer" '
        'href="https://gdc.gemiso.com/tasks/15434">#409</a> (제목)</p>'
    )


# ---------------------------------------------------------------------------
# normalize_description — 생성/수정/동기화 공통 진입점 (HTML 감지 → 통과 / 평문 → 변환)
# ---------------------------------------------------------------------------

def test_normalize_none_passthrough():
    """None은 그대로 None(필드 생략 신호 유지)."""
    assert normalize_description(None) is None


def test_normalize_plaintext_label_template_is_converted():
    out = normalize_description("[요약]\n문서 요약")
    assert out == "<p><strong>요약</strong></p><p>문서 요약</p>"


def test_is_html_matches_normalize_passthrough_rule():
    """is_html은 `normalize_description`이 통과시킬 입력과 같은 기준 — 서버가 선행 조회를 건너뛰는 근거."""
    assert is_html("<p>이미 HTML #409</p>") is True
    assert is_html("평문 #409 이고 progress < 100") is False
    assert is_html(None) is False


def test_is_html_ignores_literal_tag_mid_sentence():
    """문장 중간의 리터럴 태그는 HTML이 아니다 — 선두 앵커링(#417 재현)."""
    assert is_html("현재 본문 선두에 평문 <p>@username</p>만 붙는다.") is False
    assert is_html("[요약]\n프론트는 <span data-type=\"mention\">만 멘션으로 본다") is False


def test_is_html_allows_leading_whitespace_before_tag():
    """선행 공백·개행이 있어도 태그로 시작하면 HTML로 본다."""
    assert is_html("\n  <p>본문</p>") is True


def test_normalize_plaintext_with_literal_tag_is_converted_and_escaped():
    """리터럴 태그가 섞인 평문도 변환된다 — 태그 문자열은 이스케이프되어 텍스트로 보존(#417)."""
    out = normalize_description("[요약]\n평문 <p>@user</p>만 붙는다")
    assert out == (
        "<p><strong>요약</strong></p>"
        "<p>평문 &lt;p&gt;@user&lt;/p&gt;만 붙는다</p>"
    )


def test_normalize_already_html_passthrough_unchanged():
    """이미 HTML이면 그대로 통과 — 이중 변환/이스케이프 방지."""
    html = "<p><strong>요약</strong></p><ul><li><p>항목</p></li></ul>"
    assert normalize_description(html) == html


def test_normalize_task_from_doc_output_not_double_converted():
    """task_from_doc가 만든 HTML을 다시 태워도 이중 변환되지 않는다."""
    converted = description_to_html("[작업 내용]\n- 단계 1")
    assert normalize_description(converted) == converted


def test_normalize_plaintext_with_bare_angle_is_converted_and_escaped():
    """평문의 부등호(`progress < 100`)는 태그가 아니므로 변환+이스케이프 대상."""
    out = normalize_description("[작업 내용]\n- progress < 100")
    assert out == "<p><strong>작업 내용</strong></p><ul><li><p>progress &lt; 100</p></li></ul>"


def test_normalize_empty_string_returns_empty():
    assert normalize_description("") == ""


def test_normalize_ux_ticket_style_html_passthrough():
    """(방어) ux-ticket 방식으로 직접 작성한 HTML도 통과."""
    html = '<p>화면/위치: 콘텐츠 상세</p><ul><li><p>AS-IS: "생성일"</p></li></ul>'
    assert normalize_description(html) == html


# ---------------------------------------------------------------------------
# html_to_text — 조회한 댓글(HTML) → 터미널 표시용 평문
# ---------------------------------------------------------------------------

def test_html_to_text_none_and_empty():
    assert html_to_text(None) == ""
    assert html_to_text("") == ""


def test_html_to_text_strips_tags():
    assert html_to_text("<p>안녕하세요</p>") == "안녕하세요"


def test_html_to_text_paragraphs_become_newlines():
    assert html_to_text("<p>첫째</p><p>둘째</p>") == "첫째\n둘째"


def test_html_to_text_br_and_list():
    assert html_to_text("한 줄<br>다음 줄") == "한 줄\n다음 줄"
    assert html_to_text("<ul><li>항목1</li><li>항목2</li></ul>") == "항목1\n항목2"


def test_html_to_text_unescapes_entities():
    assert html_to_text("<p>a &lt; b &amp;&amp; c &gt; d</p>") == "a < b && c > d"


def test_html_to_text_mention_preserved():
    """멘션(@username)은 평문으로 그대로 보인다."""
    assert html_to_text("<p>@chulsoo 확인 부탁</p>") == "@chulsoo 확인 부탁"


def test_html_to_text_collapses_excess_blank_lines():
    assert html_to_text("<p>A</p><p></p><p></p><p>B</p>") == "A\n\nB"
