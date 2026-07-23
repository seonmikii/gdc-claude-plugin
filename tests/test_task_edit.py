"""태스크 description 최소 편집 헬퍼 단위 테스트 (서버·인증·네트워크 불필요).

edit_task_description 도구가 의존하는 순수 함수 — 본문 통째 재구성 대신 append/부분 교체만
수행해 편집 대상 밖 인라인 이미지(`<img data-attachment-id>`)를 보존한다. 조용히 깨지면
태스크 본문/이미지가 손상되므로 실서버 없이 여기서 검증한다.

SAMPLE은 실제 GDC 반환 HTML(태스크 #15428 라운드트립) — 파서 기준을 실측에 고정한다.
"""

from gdc_mcp.doc_utils import (
    append_work_bullets,
    label_section_has_media,
    replace_label_section,
    split_label_sections,
)

# 실제 GDC 반환 HTML (생성 형식을 그대로 반환, <strong> 유지, 태그 간 공백 없음)
SAMPLE = (
    "<p><strong>요약</strong></p><p>반환 HTML 형식 확인용 임시 태스크.</p><p></p>"
    "<p><strong>작업 내용</strong></p><ul><li><p>첫 번째 작업 항목</p></li>"
    "<li><p>두 번째 작업 항목</p></li></ul><p></p>"
    "<p><strong>비고</strong></p><p>확인 후 삭제 예정</p>"
)


# ---------------------------------------------------------------------------
# split_label_sections
# ---------------------------------------------------------------------------

def test_split_lossless_reconstruction():
    """섹션 html을 순서대로 이으면 원본과 동일(무손실)."""
    sections = split_label_sections(SAMPLE)
    assert "".join(s["html"] for s in sections) == SAMPLE


def test_split_labels_in_order():
    labels = [s["label"] for s in split_label_sections(SAMPLE)]
    assert labels == ["요약", "작업 내용", "비고"]


def test_split_preamble_is_label_none():
    """첫 라벨 앞 내용은 label=None 섹션."""
    html = "<p>머리말</p>" + SAMPLE
    sections = split_label_sections(html)
    assert sections[0]["label"] is None
    assert sections[0]["html"] == "<p>머리말</p>"
    assert "".join(s["html"] for s in sections) == html


def test_split_no_label():
    sections = split_label_sections("<p>라벨 없는 본문</p>")
    assert sections == [{"label": None, "html": "<p>라벨 없는 본문</p>"}]


def test_split_empty():
    assert split_label_sections("") == []


def test_inline_strong_not_a_label():
    """문장 속 인라인 <strong>은 문단 전체가 아니므로 라벨로 오인하지 않는다."""
    html = "<p>이것은 <strong>중요</strong>합니다</p>"
    sections = split_label_sections(html)
    assert sections == [{"label": None, "html": html}]


# ---------------------------------------------------------------------------
# append_work_bullets
# ---------------------------------------------------------------------------

def test_append_to_existing_ul():
    """[작업 내용] 기존 <ul> 끝에 블릿 추가, 타 섹션 불변."""
    out = append_work_bullets(SAMPLE, ["세 번째 작업 항목"])
    assert (
        "<li><p>두 번째 작업 항목</p></li><li><p>세 번째 작업 항목</p></li></ul>" in out
    )
    # 다른 섹션 보존
    assert "<p><strong>비고</strong></p><p>확인 후 삭제 예정</p>" in out
    assert out.count("<ul>") == 1  # 새 <ul>이 생기지 않음


def test_append_creates_ul_when_missing():
    """label 섹션은 있으나 <ul>이 없으면 섹션 끝에 새 <ul> 생성."""
    html = "<p><strong>작업 내용</strong></p><p>설명</p>"
    out = append_work_bullets(html, ["첫 항목"])
    assert out == "<p><strong>작업 내용</strong></p><p>설명</p><ul><li><p>첫 항목</p></li></ul>"


def test_append_creates_label_block_when_missing():
    """label 섹션이 없으면 문서 끝에 라벨 블록 신설(<p></p> 구분 선행)."""
    html = "<p><strong>요약</strong></p><p>요약뿐</p>"
    out = append_work_bullets(html, ["추가 항목"])
    assert out == (
        "<p><strong>요약</strong></p><p>요약뿐</p><p></p>"
        "<p><strong>작업 내용</strong></p><ul><li><p>추가 항목</p></li></ul>"
    )


def test_append_to_empty_doc():
    out = append_work_bullets("", ["첫 항목"])
    assert out == "<p><strong>작업 내용</strong></p><ul><li><p>첫 항목</p></li></ul>"


def test_append_escapes_text():
    out = append_work_bullets("", ["a < b & c"])
    assert "<li><p>a &lt; b &amp; c</p></li>" in out


def test_append_empty_bullets_noop():
    assert append_work_bullets(SAMPLE, []) == SAMPLE
    assert append_work_bullets(SAMPLE, ["  "]) == SAMPLE


# ---------------------------------------------------------------------------
# replace_label_section
# ---------------------------------------------------------------------------

def test_replace_body_preserves_marker_and_others():
    out = replace_label_section(SAMPLE, "비고", "<p>변경된 비고</p>")
    assert "<p><strong>비고</strong></p><p>변경된 비고</p>" in out
    # 타 섹션 보존
    assert "<p><strong>요약</strong></p><p>반환 HTML 형식 확인용 임시 태스크.</p>" in out
    assert "<li><p>첫 번째 작업 항목</p></li>" in out


def test_replace_missing_label_raises():
    import pytest

    with pytest.raises(ValueError):
        replace_label_section(SAMPLE, "없는라벨", "<p>x</p>")


def test_replace_keep_media_moves_img_to_section_end():
    html = (
        '<p><strong>작업 내용</strong></p><p><img data-attachment-id="7" src="s"></p>'
        "<p>옛 텍스트</p><p></p><p><strong>비고</strong></p><p>끝</p>"
    )
    out = replace_label_section(html, "작업 내용", "<p>새 텍스트</p>", keep_media=True)
    assert (
        '<p><strong>작업 내용</strong></p><p>새 텍스트</p>'
        '<p><img data-attachment-id="7" src="s"></p>' in out
    )
    assert "옛 텍스트" not in out
    assert "<p><strong>비고</strong></p><p>끝</p>" in out  # 타 섹션 보존


def test_replace_drop_media_when_keep_false():
    html = (
        '<p><strong>작업 내용</strong></p><p><img data-attachment-id="7" src="s"></p>'
        "<p>옛 텍스트</p>"
    )
    out = replace_label_section(html, "작업 내용", "<p>새 텍스트</p>", keep_media=False)
    assert out == "<p><strong>작업 내용</strong></p><p>새 텍스트</p>"
    assert "<img" not in out


# ---------------------------------------------------------------------------
# label_section_has_media
# ---------------------------------------------------------------------------

def test_has_media_true():
    html = '<p><strong>작업 내용</strong></p><p><img data-attachment-id="1" src="s"></p>'
    assert label_section_has_media(html, "작업 내용") is True


def test_has_media_false():
    assert label_section_has_media(SAMPLE, "작업 내용") is False


def test_has_media_missing_label_false():
    assert label_section_has_media(SAMPLE, "없는라벨") is False
