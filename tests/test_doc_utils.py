"""doc_utils 순수 함수 단위 테스트 (서버·인증·네트워크 불필요).

핵심 대상은 compute_phase_progress — PostToolUse 진행률 동기화 훅이 직접 의존하므로
조용히 깨지면 태스크 진행률이 잘못 반영된다. 실서버 없이 여기서 검증한다.
"""

from gdc_mcp.doc_utils import (
    compute_phase_progress,
    extract_title,
    find_repo_mapping,
    read_frontmatter,
    read_metadata_table,
    upsert_frontmatter,
)


# ---------------------------------------------------------------------------
# compute_phase_progress — checkbox 폴백 모드 (Phase/단계 헤딩 없음)
# ---------------------------------------------------------------------------

def test_checkbox_mode_partial():
    """실제 작업요청문서 형태: '## 수행 계획' + 체크박스, Phase 헤딩 없음."""
    text = """# 제목

## 수행 계획
- [x] 1. 첫 항목
- [x] 2. 둘째 항목
- [ ] 3. 셋째 항목
- [ ] 4. 넷째 항목
"""
    r = compute_phase_progress(text)
    assert r["mode"] == "checkbox"
    assert r["total_checkboxes"] == 4
    assert r["checked_checkboxes"] == 2
    assert r["progress"] == 50
    assert r["total_phases"] == 0


def test_checkbox_mode_all_done():
    text = "- [x] a\n- [x] b\n- [x] c\n"
    r = compute_phase_progress(text)
    assert r["mode"] == "checkbox"
    assert r["progress"] == 100


def test_checkbox_mode_none_done():
    text = "- [ ] a\n- [ ] b\n"
    r = compute_phase_progress(text)
    assert r["progress"] == 0


def test_uppercase_X_counts_as_checked():
    text = "- [X] a\n- [ ] b\n"
    r = compute_phase_progress(text)
    assert r["checked_checkboxes"] == 1


def test_no_checkboxes_is_zero():
    text = "# 제목\n\n본문만 있고 체크박스 없음.\n"
    r = compute_phase_progress(text)
    assert r["mode"] == "checkbox"
    assert r["total_checkboxes"] == 0
    assert r["progress"] == 0


def test_empty_document():
    r = compute_phase_progress("")
    assert r["progress"] == 0
    assert r["mode"] == "checkbox"


# ---------------------------------------------------------------------------
# compute_phase_progress — phase 모드 (Phase/단계 헤딩 있음)
# ---------------------------------------------------------------------------

def test_phase_mode_half_done():
    """Phase 2개 중 하나만 전부 완료 → 50%."""
    text = """## Phase 1: 설계
- [x] 요구사항 정리
- [x] 스키마 확정

## Phase 2: 구현
- [x] 코드 작성
- [ ] 리뷰 반영
"""
    r = compute_phase_progress(text)
    assert r["mode"] == "phase"
    assert r["total_phases"] == 2
    assert r["done_phases"] == 1
    assert r["progress"] == 50
    assert r["phases"][0]["done"] is True
    assert r["phases"][1]["done"] is False


def test_phase_mode_korean_heading():
    """'단계' 헤딩도 Phase로 인식."""
    text = """### 단계 1
- [x] 항목
"""
    r = compute_phase_progress(text)
    assert r["mode"] == "phase"
    assert r["total_phases"] == 1
    assert r["done_phases"] == 1
    assert r["progress"] == 100


def test_phase_with_no_checkboxes_is_not_done():
    """체크박스가 하나도 없는 Phase는 완료로 치지 않는다(total>0 가드)."""
    text = """## Phase 1
설명만 있고 체크박스 없음

## Phase 2
- [x] 완료
"""
    r = compute_phase_progress(text)
    assert r["total_phases"] == 2
    assert r["done_phases"] == 1  # Phase 1은 total=0이라 미완료
    assert r["progress"] == 50


def test_non_phase_heading_closes_phase():
    """Phase 뒤 일반 헤딩(## 참고)이 오면 Phase가 닫혀, 이후 체크박스는 집계 제외."""
    text = """## Phase 1
- [x] 항목

## 참고 사항
- [ ] 이건 Phase 밖이라 카운트 안 됨
"""
    r = compute_phase_progress(text)
    assert r["total_phases"] == 1
    assert r["phases"][0]["total"] == 1  # 참고 섹션 체크박스는 미포함
    assert r["done_phases"] == 1
    assert r["progress"] == 100


# ---------------------------------------------------------------------------
# read_frontmatter / upsert_frontmatter
# ---------------------------------------------------------------------------

def test_read_frontmatter_extracts_pairs():
    text = "---\ntask_id: 15356\ntask_url: https://gdc.gemiso.com/tasks/15356\n---\n\n# 제목\n"
    fm = read_frontmatter(text)
    assert fm["task_id"] == "15356"
    assert fm["task_url"] == "https://gdc.gemiso.com/tasks/15356"


def test_read_frontmatter_absent():
    assert read_frontmatter("# 제목만 있음\n") == {}


def test_upsert_adds_to_existing_block():
    text = "---\ntask_id: 1\n---\n\n본문\n"
    out = upsert_frontmatter(text, {"task_url": "http://x"})
    fm = read_frontmatter(out)
    assert fm["task_id"] == "1"
    assert fm["task_url"] == "http://x"


def test_upsert_creates_block_when_absent():
    out = upsert_frontmatter("# 제목\n", {"task_id": "9"})
    assert out.startswith("---\ntask_id: 9\n---\n")
    assert read_frontmatter(out)["task_id"] == "9"


def test_upsert_updates_existing_key():
    text = "---\ntask_id: 1\n---\n본문\n"
    out = upsert_frontmatter(text, {"task_id": "2"})
    assert read_frontmatter(out)["task_id"] == "2"


# ---------------------------------------------------------------------------
# read_metadata_table / extract_title
# ---------------------------------------------------------------------------

def test_metadata_table_parsed():
    text = """# 제목

| 속성 | 값 |
|------|-----|
| 유형 | feat |
| 상태 | done |

본문
"""
    meta = read_metadata_table(text)
    assert meta["유형"] == "feat"
    assert meta["상태"] == "done"
    assert "속성" not in meta  # 헤더 제외


def test_extract_title_first_h1():
    assert extract_title("전문\n# 진짜 제목\n## 부제\n") == "진짜 제목"


def test_extract_title_none():
    assert extract_title("## h2만 있음\n") is None


# ---------------------------------------------------------------------------
# find_repo_mapping — .claude/rules/project.md 탐색 (파일시스템, 네트워크 X)
# ---------------------------------------------------------------------------

def _write_rule(root, body):
    rule = root / ".claude" / "rules" / "project.md"
    rule.parent.mkdir(parents=True, exist_ok=True)
    rule.write_text(body, encoding="utf-8")


def test_find_repo_mapping_reads_ids(tmp_path):
    _write_rule(tmp_path, "gdc_workspace_id: 5\ngdc_project_id: 42\n")
    m = find_repo_mapping(tmp_path)
    assert m == {"gdc_workspace_id": "5", "gdc_project_id": "42"}


def test_find_repo_mapping_walks_up_from_subdir(tmp_path):
    _write_rule(tmp_path, "gdc_workspace_id: 5\ngdc_project_id: 42\n")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    assert find_repo_mapping(sub)["gdc_project_id"] == "42"


def test_find_repo_mapping_absent(tmp_path):
    assert find_repo_mapping(tmp_path) == {}
