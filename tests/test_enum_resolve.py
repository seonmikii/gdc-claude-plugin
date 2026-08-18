"""프로젝트 enum 값 해석(_resolve_enum_value) 단위 테스트 (네트워크 불필요).

백엔드 모델 기본값은 영문 시드(other/open/medium) 고정이라, WBS 프리셋 프로젝트
(등록/보통/기타)에 생성하면 프로젝트 enum에 없는 값이 저장된다 —
`list_my_tasks`/`search_tasks(not_finished=True)`에서 통째로 누락되는 결함으로 이어졌다.
프론트 생성 다이얼로그(TaskCreateDialog.tsx의 pickName)와 **같은 규칙**으로 기본값을
고르는지, 잘못된 값을 도구 레벨에서 차단하는지 여기서 가드한다.
"""

import asyncio

import pytest

from gdc_mcp import server

# backend/projects/models.py DEFAULT_* (이슈관리) / WBS_DEFAULT_* (WBS) 시드와 동일
ISSUE_PROJECT = {
    "task_statuses": [
        {"name": "open", "is_active": True},
        {"name": "in_progress", "is_active": True},
        {"name": "review", "is_active": True},
        {"name": "resolved", "is_active": True},
        {"name": "closed", "is_active": True},
    ],
    "task_priorities": [
        {"name": "low", "is_active": True},
        {"name": "medium", "is_active": True},
        {"name": "high", "is_active": True},
        {"name": "urgent", "is_active": True},
    ],
    "task_types": [
        {"name": "planning", "is_active": True},
        {"name": "development", "is_active": True},
        {"name": "other", "is_active": True},
    ],
}

WBS_PROJECT = {
    "task_statuses": [
        {"name": "등록", "is_active": True},
        {"name": "진행", "is_active": True},
        {"name": "완료", "is_active": True},
    ],
    "task_priorities": [
        {"name": "낮음", "is_active": True},
        {"name": "보통", "is_active": True},
        {"name": "높음", "is_active": True},
        {"name": "긴급", "is_active": True},
    ],
    "task_types": [
        {"name": "기획", "is_active": True},
        {"name": "분석/설계", "is_active": True},
        {"name": "개발", "is_active": True},
        {"name": "테스트", "is_active": True},
        {"name": "기타", "is_active": True},
    ],
}

# 시드 선호값이 하나도 없는 커스텀 세트 — 첫 활성 항목으로 폴백해야 한다
CUSTOM_PROJECT = {
    "task_statuses": [
        {"name": "접수", "is_active": True},
        {"name": "처리중", "is_active": True},
    ],
    "task_priorities": [{"name": "P1", "is_active": True}],
    "task_types": [{"name": "운영", "is_active": True}],
}


# --- 값 생략 시 기본값 선택 (핵심 수정) ------------------------------------------


def test_issue_project_defaults_match_english_seed():
    assert server._resolve_enum_value(ISSUE_PROJECT, "status", None) == "open"
    assert server._resolve_enum_value(ISSUE_PROJECT, "priority", None) == "medium"
    assert server._resolve_enum_value(ISSUE_PROJECT, "task_type", None) == "other"


def test_wbs_project_defaults_match_korean_seed():
    # 이 결함의 본체 — 서버 기본값(open/medium/other) 대신 프로젝트 enum 값이 나와야 한다
    assert server._resolve_enum_value(WBS_PROJECT, "status", None) == "등록"
    assert server._resolve_enum_value(WBS_PROJECT, "priority", None) == "보통"
    assert server._resolve_enum_value(WBS_PROJECT, "task_type", None) == "기타"


def test_custom_project_falls_back_to_first_active():
    assert server._resolve_enum_value(CUSTOM_PROJECT, "status", None) == "접수"
    assert server._resolve_enum_value(CUSTOM_PROJECT, "priority", None) == "P1"
    assert server._resolve_enum_value(CUSTOM_PROJECT, "task_type", None) == "운영"


def test_inactive_items_are_not_candidates():
    project = {
        "task_statuses": [
            {"name": "등록", "is_active": False},
            {"name": "진행", "is_active": True},
        ]
    }
    assert server._resolve_enum_value(project, "status", None) == "진행"


def test_empty_enum_leaves_value_untouched():
    # 판단 근거가 없으면 서버에 맡긴다(기존 동작 유지)
    assert server._resolve_enum_value({}, "status", None) is None
    assert server._resolve_enum_value({}, "status", "open") == "open"


# --- 값이 전달된 경우 -------------------------------------------------------------


def test_exact_match_passes_through():
    assert server._resolve_enum_value(WBS_PROJECT, "status", "진행") == "진행"
    assert server._resolve_enum_value(ISSUE_PROJECT, "status", "closed") == "closed"


def test_label_mapping_resolves_both_directions():
    # 영문 코드 → 한글 name (WBS)
    assert server._resolve_enum_value(WBS_PROJECT, "status", "open") == "등록"
    assert server._resolve_enum_value(WBS_PROJECT, "priority", "high") == "높음"
    assert server._resolve_enum_value(WBS_PROJECT, "task_type", "other") == "기타"
    # 한글 라벨 → 영문 name (이슈관리)
    assert server._resolve_enum_value(ISSUE_PROJECT, "status", "등록") == "open"
    assert server._resolve_enum_value(ISSUE_PROJECT, "priority", "보통") == "medium"
    assert server._resolve_enum_value(ISSUE_PROJECT, "task_type", "기타") == "other"


def test_done_labels_do_not_collide():
    # 라벨 값에 중복이 없어 역매핑이 단사다 — 완료→closed, 해결→resolved로 갈리지 않는다
    assert server._resolve_enum_value(ISSUE_PROJECT, "status", "완료") == "closed"
    assert server._resolve_enum_value(ISSUE_PROJECT, "status", "해결") == "resolved"


def test_unknown_value_is_blocked_with_candidates():
    with pytest.raises(ValueError) as e:
        server._resolve_enum_value(WBS_PROJECT, "status", "검토")
    assert "등록" in str(e.value) and "진행" in str(e.value)


def test_wbs_only_type_is_blocked_in_issue_project():
    # '테스트'·'분석/설계'는 영문 대응이 없어 이슈관리 프로젝트에서는 차단돼야 한다
    with pytest.raises(ValueError):
        server._resolve_enum_value(ISSUE_PROJECT, "task_type", "테스트")


def test_inactive_value_is_blocked():
    project = {"task_statuses": [{"name": "폐기", "is_active": False}, {"name": "진행", "is_active": True}]}
    with pytest.raises(ValueError):
        server._resolve_enum_value(project, "status", "폐기")


# --- enum 불일치 판정(_enum_checker) ----------------------------------------------


@pytest.fixture
def fetches(monkeypatch):
    """_project를 가로채 프로젝트별 조회 횟수를 센다(실제 네트워크 없음)."""
    recorded: list[int] = []
    projects = {16: ISSUE_PROJECT, 46: WBS_PROJECT}

    def fake_project(project_id):
        recorded.append(project_id)
        return projects[project_id]

    monkeypatch.setattr(server, "_project", fake_project)
    return recorded


def test_checker_flags_values_missing_from_project_enum(fetches):
    check = server._enum_checker()
    # WBS 프로젝트에 남아 있는 서버 기본값 — 세 필드 모두 불일치
    bad = {"project": 46, "status": "open", "priority": "medium", "task_type": "other"}
    assert check(bad) == ["status", "priority", "task_type"]


def test_checker_is_silent_for_valid_values(fetches):
    check = server._enum_checker()
    assert check({"project": 46, "status": "등록", "priority": "보통", "task_type": "기타"}) == []
    assert check({"project": 16, "status": "open", "priority": "medium", "task_type": "other"}) == []


def test_checker_ignores_missing_fields_and_project(fetches):
    check = server._enum_checker()
    assert check({"project": 46, "status": "등록"}) == []  # priority/task_type 미포함
    assert check({"status": "open"}) == []  # 프로젝트 미상 → 판정하지 않음
    assert fetches == [46]


def test_checker_fetches_each_project_once(fetches):
    check = server._enum_checker()
    for _ in range(3):
        check({"project": 46, "status": "open"})
        check({"project": 16, "status": "open"})
    assert fetches == [46, 16]


def test_checker_counts_inactive_items_as_belonging(fetches, monkeypatch):
    monkeypatch.setattr(
        server, "_project", lambda _id: {"task_statuses": [{"name": "폐기", "is_active": False}]}
    )
    check = server._enum_checker()
    assert check({"project": 46, "status": "폐기"}) == []


# --- 도구가 실제로 보내는 payload -------------------------------------------------
# 결함의 본체는 "생략하면 payload에서 빠진다"였다. 헬퍼가 옳아도 전송에서 빠지면 그대로
# 재발하므로 전송 형태를 고정한다. 네트워크는 전부 monkeypatch로 대체한다.


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture
def sent(monkeypatch):
    """client.request를 가로채 (method, path, json)을 기록한다."""
    recorded: list[tuple[str, str, dict]] = []

    def fake_request(method, path, **kwargs):
        recorded.append((method, path, kwargs.get("json")))
        return _Resp({"id": 999, "number": 1, "title": "t", "status": kwargs.get("json", {}).get("status")})

    monkeypatch.setattr(server.client, "request", fake_request)
    monkeypatch.setattr(server, "_project", lambda _id: WBS_PROJECT)
    monkeypatch.setitem(server._me_cache, "id", 7)
    return recorded


def test_create_task_always_sends_three_fields_from_project_enum(sent):
    asyncio.run(server.create_task(None, project=46, title="제목"))
    _method, _path, payload = sent[0]
    # 생략해도 빠지지 않는다 — WBS 프로젝트의 실제 enum 값이 실린다
    assert payload["status"] == "등록"
    assert payload["priority"] == "보통"
    assert payload["task_type"] == "기타"


def test_create_task_resolves_english_input_to_project_enum(sent):
    asyncio.run(server.create_task(None, project=46, title="제목", status="open", priority="high"))
    _method, _path, payload = sent[0]
    assert payload["status"] == "등록"
    assert payload["priority"] == "높음"


def test_create_task_blocks_value_missing_from_project(sent):
    with pytest.raises(ValueError):
        asyncio.run(server.create_task(None, project=46, title="제목", status="review"))
    assert sent == []  # 서버로 나가지 않는다


def test_update_task_does_not_inject_defaults(sent, monkeypatch):
    monkeypatch.setattr(server.client, "get", lambda path, **kw: _Resp({"project": 46}))
    asyncio.run(server.update_task(None, task_id=15748, status="open"))
    _method, _path, payload = sent[0]
    assert payload == {"status": "등록"}  # 전달한 필드만 — 부분 수정 의미 유지


# --- 조회(get_project_enums)와 지정 가능 집합의 일치 --------------------------------
# 결함 본체: 조회에는 비활성 항목이 섞여 나오는데 지정하면 거부됐다(조회 14종 / 수정 9종).
# 조회 응답에 is_active를 싣고 assignable_*를 _resolve_enum_value와 **같은 헬퍼**로 산출해
# 두 목록이 다시 갈라지지 않게 고정한다.

# 재현 사례(프로젝트 16 GDC-Support)를 축약 — '기능 변경'이 조회에만 나오던 값
MIXED_PROJECT = {
    "name": "GDC-Support",
    "workspace": 3,
    "task_statuses": [
        {"name": "open", "category": "planned", "is_active": True},
        {"name": "in_progress", "category": "in_progress", "is_active": True},
        {"name": "확인 필요", "category": "in_progress", "is_active": False},
        {"name": "closed", "category": "done", "is_active": True},
        {"name": "보류", "category": "done", "is_active": False},
    ],
    "task_priorities": [
        {"name": "medium", "is_active": True},
        {"name": "urgent", "is_active": False},
    ],
    "task_types": [
        {"name": "development", "is_active": True},
        {"name": "버그", "is_active": True},
        {"name": "기능 변경", "is_active": False},
        {"name": "other", "is_active": False},
    ],
}

_KIND_FIELDS = [("status", "statuses"), ("priority", "priorities"), ("task_type", "task_types")]


@pytest.fixture
def mixed(monkeypatch):
    monkeypatch.setattr(server, "_project", lambda _id: MIXED_PROJECT)
    return server.get_project_enums(16)


def test_enums_response_marks_each_item_with_is_active(mixed):
    assert {x["name"]: x["is_active"] for x in mixed["task_types"]} == {
        "development": True, "버그": True, "기능 변경": False, "other": False,
    }
    assert {x["name"]: x["is_active"] for x in mixed["priorities"]} == {"medium": True, "urgent": False}
    assert [s["name"] for s in mixed["statuses"] if s["is_active"]] == ["open", "in_progress", "closed"]


def test_every_assignable_name_passes_the_resolver(mixed):
    # 조회 결과를 그대로 써도 수정이 실패하지 않는다 — 이 결함이 재발하면 여기서 걸린다
    for kind, _field in _KIND_FIELDS:
        names = mixed[f"assignable_{kind}_names"]
        assert names, f"{kind}: 활성 항목이 있어야 한다"
        for name in names:
            assert server._resolve_enum_value(MIXED_PROJECT, kind, name) == name


def test_every_inactive_name_is_rejected_with_reason(mixed):
    # 통과 집합이 assignable_*와 문자 그대로 같지는 않다(라벨 별칭도 통과) — 반대 방향으로 고정한다
    for kind, field in _KIND_FIELDS:
        inactive = [x["name"] for x in mixed[field] if not x["is_active"]]
        assert inactive, f"{kind}: 비활성 픽스처가 있어야 한다"
        for name in inactive:
            with pytest.raises(ValueError) as e:
                server._resolve_enum_value(MIXED_PROJECT, kind, name)
            assert "비활성" in str(e.value)


def test_not_finished_names_keep_inactive_statuses(mixed):
    # 기존 태스크를 거르는 필터 값이라 비활성도 포함해야 한다(빼면 그 상태의 태스크가 누락)
    assert mixed["not_finished_status_names"] == ["open", "in_progress", "확인 필요"]
    assert mixed["done_status_names"] == ["closed", "보류"]
    assert mixed["assignable_status_names"] == ["open", "in_progress", "closed"]


def test_assignable_is_empty_when_no_active_items(monkeypatch):
    # 활성이 하나도 없으면 _resolve_enum_value가 값을 그대로 통과시킨다(서버 위임)
    # → assignable_*는 빈 배열 = "제약 없음"
    project = {"task_types": [{"name": "기타", "is_active": False}], "task_statuses": [], "task_priorities": []}
    monkeypatch.setattr(server, "_project", lambda _id: project)
    enums = server.get_project_enums(16)
    assert enums["assignable_task_type_names"] == []
    assert server._resolve_enum_value(project, "task_type", "기타") == "기타"
