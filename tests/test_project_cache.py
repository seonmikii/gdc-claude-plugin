"""프로젝트 상세 TTL 캐시(_project) 단위 테스트 (네트워크 불필요).

프로젝트 상세는 상태 enum·멤버·preset 판정에 여러 도구가 반복 조회한다. 캐시가 어긋나면
왕복이 줄지 않거나(히트 실패) 오래된 상태 목록으로 잘못 판정하므로(무효화 실패) 여기서 가드한다.
client.get은 monkeypatch로 대체하고 호출 횟수를 센다.
"""

import time

import pytest

from gdc_mcp import server

PROJECT_A = {"id": 1, "name": "A", "task_statuses": [{"name": "open", "category": "planned"}]}
PROJECT_B = {"id": 2, "name": "B", "task_statuses": []}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture
def calls(monkeypatch):
    """client.get을 가로채 조회된 경로를 기록한다(실제 네트워크 없음)."""
    recorded: list[str] = []
    payloads = {"/api/projects/1/": PROJECT_A, "/api/projects/2/": PROJECT_B}

    def fake_get(path, **kwargs):
        recorded.append(path)
        return _FakeResponse(payloads[path])

    monkeypatch.setattr(server.client, "get", fake_get)
    server._clear_project_cache()
    yield recorded
    server._clear_project_cache()


def test_first_call_fetches(calls):
    assert server._project(1) == PROJECT_A
    assert calls == ["/api/projects/1/"]


def test_second_call_hits_cache_without_fetching(calls):
    server._project(1)
    server._project(1)
    server._project(1)
    assert calls == ["/api/projects/1/"]  # 왕복 1회뿐


def test_different_projects_cached_separately(calls):
    assert server._project(1)["name"] == "A"
    assert server._project(2)["name"] == "B"
    assert server._project(1)["name"] == "A"
    assert calls == ["/api/projects/1/", "/api/projects/2/"]


def test_expired_entry_refetches(calls):
    server._project(1)
    # 저장 시각을 TTL 이전으로 되돌려 만료를 흉내낸다
    stamp, data = server._PROJECT_CACHE[1]
    server._PROJECT_CACHE[1] = (stamp - server._PROJECT_TTL - 1, data)
    server._project(1)
    assert calls == ["/api/projects/1/", "/api/projects/1/"]


def test_entry_within_ttl_is_not_refetched(calls):
    server._project(1)
    stamp, data = server._PROJECT_CACHE[1]
    server._PROJECT_CACHE[1] = (stamp - (server._PROJECT_TTL - 1), data)
    server._project(1)
    assert calls == ["/api/projects/1/"]


def test_clear_cache_forces_refetch(calls):
    server._project(1)
    server._clear_project_cache()
    server._project(1)
    assert calls == ["/api/projects/1/", "/api/projects/1/"]


def test_cache_stores_monotonic_stamp(calls):
    before = time.monotonic()
    server._project(1)
    stamp, _ = server._PROJECT_CACHE[1]
    assert before <= stamp <= time.monotonic()


# ---------------------------------------------------------------------------
# 캐시를 경유하는 헬퍼 — 같은 프로젝트를 여러 번 물어도 왕복은 1회
# ---------------------------------------------------------------------------

def test_helpers_share_one_fetch(calls):
    assert server._not_finished_names(1) == ["open"]
    assert server._status_category(1, "open") == "planned"
    assert calls == ["/api/projects/1/"]


def test_injected_project_skips_cache_and_fetch(calls):
    # project= 인자로 상세를 직접 넘기면 캐시도 조회도 타지 않는다(기존 동작 유지)
    assert server._not_finished_names(1, project=PROJECT_A) == ["open"]
    assert calls == []
