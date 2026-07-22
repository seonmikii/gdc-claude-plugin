"""description_to_html 순수 함수 단위 테스트 (서버·인증·네트워크 불필요).

task_from_doc가 라벨 섹션 템플릿(평문)을 GDC 리치텍스트(HTML)로 변환할 때 쓴다.
GDC description은 리치텍스트(HTML)로 저장·렌더링되므로(실증 확인: 태스크 #292/#273),
평문을 그대로 보내면 본문이 뭉개진다 — 이 변환이 조용히 깨지면 태스크 본문이 깨진다.
"""

from gdc_mcp.doc_utils import description_to_html, html_to_text, normalize_description


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
# normalize_description — 생성/수정/동기화 공통 진입점 (HTML 감지 → 통과 / 평문 → 변환)
# ---------------------------------------------------------------------------

def test_normalize_none_passthrough():
    """None은 그대로 None(필드 생략 신호 유지)."""
    assert normalize_description(None) is None


def test_normalize_plaintext_label_template_is_converted():
    out = normalize_description("[요약]\n문서 요약")
    assert out == "<p><strong>요약</strong></p><p>문서 요약</p>"


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
