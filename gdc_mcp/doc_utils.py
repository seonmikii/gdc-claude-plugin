"""작업 요청 문서(.md) 파싱 유틸리티.

- YAML 풍 frontmatter(`--- ... ---`)에서 task_id/task_url 읽기·쓰기 (연동 키)
- 메타데이터 테이블에서 제목/유형 등 추출
- `## 작업 결과` 안의 Phase 진척으로 진행률(%) 산출
- 상위 디렉터리의 `.claude/rules/project.md`에서 gdc 워크스페이스/프로젝트 매핑 추출
"""

from __future__ import annotations

import re
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_PHASE_HEADING_RE = re.compile(r"^#{2,4}\s*(?:Phase|단계)\b.*$", re.IGNORECASE)
_HEADING_RE = re.compile(r"^#{1,6}\s")
_CHECKBOX_RE = re.compile(r"^\s*[-*]\s*\[( |x|X)\]\s")


def read_frontmatter(text: str) -> dict[str, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def upsert_frontmatter(text: str, updates: dict[str, str]) -> str:
    """frontmatter에 key를 추가/갱신한 새 문서 텍스트를 반환한다."""
    m = _FRONTMATTER_RE.match(text)
    if m:
        body = m.group(1)
        existing: dict[str, str] = {}
        order: list[str] = []
        for line in body.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                k = k.strip()
                if k not in existing:
                    order.append(k)
                existing[k] = v.strip()
        for k, v in updates.items():
            if k not in existing:
                order.append(k)
            existing[k] = str(v)
        new_block = "\n".join(f"{k}: {existing[k]}" for k in order)
        return f"---\n{new_block}\n---\n" + text[m.end():]
    new_block = "\n".join(f"{k}: {v}" for k, v in updates.items())
    return f"---\n{new_block}\n---\n\n" + text


def extract_title(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def read_metadata_table(text: str) -> dict[str, str]:
    """상단 `| 속성 | 값 |` 메타데이터 테이블을 {속성: 값}으로 파싱한다.

    구분선(`|---|`)과 헤더 행은 건너뛴다. 첫 표만 읽는다.
    """
    meta: dict[str, str] = {}
    seen_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            seen_table = True
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) < 2:
                continue
            key, value = cells[0], cells[1]
            if not key or set(key) <= {"-", ":"}:  # 구분선
                continue
            if key in ("속성", "항목"):  # 헤더
                continue
            meta[key] = value
        elif seen_table and stripped == "":
            break  # 표가 끝나면 종료
    return meta


def compute_phase_progress(text: str) -> dict:
    """진행률을 산출한다.

    기본은 Phase 단위: 각 'Phase'/'단계' 헤딩 아래 체크박스가 있고 전부 [x]면 그 Phase 완료,
    progress = 완료 Phase 수 / 전체 Phase 수 × 100.
    Phase 헤딩이 하나도 없으면 **문서 전체 체크박스의 완료 비중**으로 대체한다(fallback),
    progress = 완료 체크박스 / 전체 체크박스 × 100. (정수, 반올림)
    반환 키 `mode`로 어느 방식이 적용됐는지 알린다("phase" | "checkbox").
    """
    lines = text.splitlines()
    phases: list[dict] = []
    current: dict | None = None
    for line in lines:
        if _PHASE_HEADING_RE.match(line):
            current = {"title": line.strip("# ").strip(), "total": 0, "checked": 0}
            phases.append(current)
            continue
        if current is not None and _HEADING_RE.match(line) and not _PHASE_HEADING_RE.match(line):
            # 같은/상위 레벨의 다른 헤딩을 만나면 현재 Phase 종료
            if not line.startswith("####"):
                current = None
        cb = _CHECKBOX_RE.match(line) if current is not None else None
        if cb:
            current["total"] += 1
            if cb.group(1).lower() == "x":
                current["checked"] += 1

    total_phases = len(phases)

    # Phase 헤딩이 없으면 전체 체크박스 비중으로 대체
    if total_phases == 0:
        total_cb = 0
        checked_cb = 0
        for line in lines:
            cb = _CHECKBOX_RE.match(line)
            if cb:
                total_cb += 1
                if cb.group(1).lower() == "x":
                    checked_cb += 1
        progress = round(checked_cb / total_cb * 100) if total_cb else 0
        return {
            "mode": "checkbox",
            "total_phases": 0,
            "done_phases": 0,
            "total_checkboxes": total_cb,
            "checked_checkboxes": checked_cb,
            "progress": progress,
            "phases": [],
        }

    done_phases = sum(1 for p in phases if p["total"] > 0 and p["checked"] == p["total"])
    progress = round(done_phases / total_phases * 100)
    return {
        "mode": "phase",
        "total_phases": total_phases,
        "done_phases": done_phases,
        "progress": progress,
        "phases": [
            {**p, "done": p["total"] > 0 and p["checked"] == p["total"]} for p in phases
        ],
    }


def find_repo_mapping(start: Path) -> dict[str, str]:
    """start에서 위로 올라가며 .claude/rules/project.md의 gdc 매핑을 찾는다."""
    keys = {"gdc_workspace_id", "gdc_project_id"}
    for d in [start, *start.parents]:
        rule = d / ".claude" / "rules" / "project.md"
        if rule.exists():
            mapping: dict[str, str] = {}
            for line in rule.read_text(encoding="utf-8").splitlines():
                mm = re.match(r"^\s*[-*]?\s*(gdc_\w+)\s*[:=]\s*(\S+)", line)
                if mm and mm.group(1) in keys:
                    mapping[mm.group(1)] = mm.group(2)
            if mapping:
                return mapping
    return {}
