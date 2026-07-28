"""멘션 조회 도구 단위 테스트 (네트워크 불필요).

두 가지를 가드한다.
1. 미리보기 정리(_mention_preview) — /api/dashboard/mentions/의 content_preview는
   `mention.content[:100]` raw 슬라이스라 HTML 태그가 남고 끝이 태그 중간에서 잘리기도 한다
   (알림 serializer와 달리 strip_tags 없음).
2. 페이지 순회 — 이 엔드포인트는 pagination_class가 없어 DRF 전역 PAGE_SIZE(20) 고정이고
   page_size 파라미터를 받지 않는다. limit>20은 page를 넘겨가며 모아야 채워진다.
"""

import asyncio

import pytest

from gdc_mcp import server
from gdc_mcp.server import _mention_preview

MENTION_SPAN = (
    '<span data-type="mention" class="mention" data-id="chulsoo" '
    'data-label="김철수">@chulsoo</span>'
)


# ---------------------------------------------------------------------------
# _mention_preview
# ---------------------------------------------------------------------------

def test_empty_input_returns_empty_string():
    assert _mention_preview(None) == ""
    assert _mention_preview("") == ""


def test_plain_paragraph_is_unwrapped():
    assert _mention_preview("<p>확인 부탁드립니다</p>") == "확인 부탁드립니다"


def test_mention_span_becomes_plain_handle():
    assert _mention_preview(f"<p>{MENTION_SPAN} 확인 부탁</p>") == "@chulsoo 확인 부탁"


def test_dangling_tag_at_end_is_dropped():
    # 서버가 100자에서 자르며 태그 중간이 잘린 경우
    assert _mention_preview('<p>배포 완료했습니다 <span data-type="menti') == "배포 완료했습니다"


def test_dangling_tag_does_not_eat_earlier_text():
    raw = f"<p>{MENTION_SPAN} 앞 문장은 유지</p><p>뒷 문장 <span data-id"
    assert _mention_preview(raw) == "@chulsoo 앞 문장은 유지 뒷 문장"


def test_block_breaks_become_single_spaces():
    assert _mention_preview("<p>첫 줄</p><p>둘째 줄</p>") == "첫 줄 둘째 줄"


def test_entities_are_unescaped():
    assert _mention_preview("<p>A &amp; B &lt;test&gt;</p>") == "A & B <test>"


def test_result_is_capped_at_limit():
    raw = "<p>" + ("가" * 150) + "</p>"
    assert len(_mention_preview(raw)) == 100


def test_custom_limit():
    assert _mention_preview("<p>abcdefghij</p>", limit=4) == "abcd"


# ---------------------------------------------------------------------------
# list_my_mentions — 20건 고정 페이지 순회
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _page(page_no: int, total: int, has_next: bool) -> dict:
    """서버 응답 흉내 — 한 페이지에 20건."""
    start = (page_no - 1) * server._MENTION_LIST_PAGE_SIZE
    return {
        "count": total,
        "next": f"?page={page_no + 1}" if has_next else None,
        "results": [
            {
                "id": start + i,
                "author_name": "김선민",
                "task_id": 100 + start + i,
                "task_number": start + i,
                "task_title": "태스크",
                "project_name": "P",
                "content_preview": "<p>본문</p>",
                "created_at": "2026-07-28T00:00:00+09:00",
            }
            for i in range(server._MENTION_LIST_PAGE_SIZE)
        ],
    }


@pytest.fixture
def paged(monkeypatch):
    """mentions 엔드포인트를 3페이지(총 60건)로 흉내내고 요청된 page 번호를 기록한다."""
    requested: list[int] = []
    pages = {1: _page(1, 60, True), 2: _page(2, 60, True), 3: _page(3, 60, False)}

    def fake_get(path, params=None, **kwargs):
        assert path == server._DASHBOARD_MENTIONS
        assert "page_size" not in (params or {})  # 서버가 받지 않는 파라미터를 보내지 않는다
        requested.append((params or {}).get("page"))
        return _FakeResponse(pages[(params or {}).get("page", 1)])

    async def fake_ctx(_ctx):
        return {"workspace_id": 3, "project_id": 45}

    monkeypatch.setattr(server.client, "get", fake_get)
    monkeypatch.setattr(server, "_resolve_context", fake_ctx)
    return requested


def test_single_page_when_limit_fits(paged):
    out = asyncio.run(server.list_my_mentions(None, limit=20))
    assert out["count"] == 20
    assert paged == [1]


def test_walks_pages_until_limit_filled(paged):
    out = asyncio.run(server.list_my_mentions(None, limit=25))
    assert out["count"] == 25
    assert paged == [1, 2]  # 25건을 채우는 데 필요한 만큼만


def test_stops_when_server_has_no_next_page(paged):
    out = asyncio.run(server.list_my_mentions(None, limit=200))
    assert out["count"] == 60  # 전체 3페이지에서 멈춤
    assert paged == [1, 2, 3]
    assert out["total"] == 60


def test_context_scope_is_applied(paged, monkeypatch):
    captured = {}
    orig = server.client.get

    def spy(path, params=None, **kwargs):
        captured.update(params or {})
        return orig(path, params=params, **kwargs)

    monkeypatch.setattr(server.client, "get", spy)
    asyncio.run(server.list_my_mentions(None, limit=5))
    assert captured["workspace"] == 3
    assert captured["project_id"] == 45
    assert captured["mention_type"] == "both"


def test_explicit_project_overrides_context(paged, monkeypatch):
    captured = {}
    orig = server.client.get

    def spy(path, params=None, **kwargs):
        captured.update(params or {})
        return orig(path, params=params, **kwargs)

    monkeypatch.setattr(server.client, "get", spy)
    out = asyncio.run(server.list_my_mentions(None, project_id=46, limit=5))
    assert captured["project_id"] == 46
    assert out["project_id"] == 46


def test_invalid_mention_type_raises(paged):
    with pytest.raises(ValueError, match="mention_type"):
        asyncio.run(server.list_my_mentions(None, mention_type="wrong"))


def test_invalid_date_raises(paged):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        asyncio.run(server.list_my_mentions(None, date_from="2026/07/01"))
