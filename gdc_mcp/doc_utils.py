"""작업 요청 문서(.md) 파싱 유틸리티.

- YAML 풍 frontmatter(`--- ... ---`)에서 task_id/task_url 읽기·쓰기 (연동 키)
- 메타데이터 테이블에서 제목/유형 등 추출
- `## 작업 결과` 안의 Phase 진척으로 진행률(%) 산출
- 상위 디렉터리의 `.claude/rules/project.md`에서 gdc 워크스페이스/프로젝트 매핑 추출
"""

from __future__ import annotations

import html
import re
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_PHASE_HEADING_RE = re.compile(r"^#{2,4}\s*(?:Phase|단계)\b.*$", re.IGNORECASE)
_HEADING_RE = re.compile(r"^#{1,6}\s")
_CHECKBOX_RE = re.compile(r"^\s*[-*]\s*\[( |x|X)\]\s")
_LABEL_RE = re.compile(r"^\[(.+)\]$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$")
# 이미 HTML(리치텍스트)인지 판별용 — 실제 태그명 뒤가 와야 매칭(평문의 'a < b'는 미매칭)
_HTML_TAG_RE = re.compile(
    r"</?(?:p|br|ul|ol|li|div|span|strong|em|b|i|a|h[1-6]|table|thead|tbody|tr|td|th|blockquote|pre|code)\b",
    re.IGNORECASE,
)


def normalize_description(text: str | None) -> str | None:
    """태스크 description을 GDC 리치텍스트(HTML)로 정규화한다(생성/수정/동기화 공통 진입점).

    GDC는 description을 모든 경로에서 HTML로 저장·렌더링하므로, 평문을 그대로 보내면 줄바꿈이
    무시돼 본문이 뭉개진다. 이 래퍼를 모든 경로가 공유해 일관되게 변환하되, **이미 HTML인 입력은
    그대로 통과**시켜 이중 변환(예: 이미 변환된 `task_from_doc` 산출물, 에이전트가 직접 넘긴 HTML)을 막는다.

    - None → None (변경 없음/필드 생략 신호를 그대로 전달).
    - 블록/인라인 태그가 있으면 이미 HTML로 보고 **그대로 통과**.
    - 그 외 평문은 `description_to_html`로 변환.

    주의: 평문에 리터럴 태그 문자열(예: 문장 속 `<p>`)이 있으면 HTML로 오판할 수 있다(희귀).
    확실히 변환이 필요하면 라벨 섹션 템플릿(평문)을 쓴다.
    """
    if text is None:
        return None
    if _HTML_TAG_RE.search(text):
        return text  # 이미 HTML — 통과
    return description_to_html(text)


def description_to_html(text: str) -> str:
    """라벨 섹션 템플릿(평문)을 GDC 리치텍스트(HTML)로 변환한다.

    GDC의 description은 리치텍스트 에디터(HTML)로 저장·렌더링되므로(실증 확인: 태스크
    #292/#273), 평문 `\\n`/`-`를 그대로 보내면 줄바꿈이 무시돼 한 줄로 뭉개지고 하이픈이
    글자 그대로 보인다. 다음 규칙으로 변환한다(GDC 에디터 산출 형식과 정렬):

    - `[라벨]` 줄 → `<p><strong>라벨</strong></p>` (대괄호 제거, 라벨 볼드 — GDC가 <strong> 지원)
    - 일반 텍스트 줄 → `<p>...</p>`
    - `-`/`*` 블렛 줄 → `<ul><li><p>...</p></li>...</ul>` (연속 블렛은 하나의 `<ul>`)
    - 빈 줄로 구분된 섹션 사이 → 빈 문단 `<p></p>`
    - 모든 텍스트 내용은 `&`·`<`·`>`를 이스케이프한다.

    빈 입력(공백만 포함 포함)은 빈 문자열을 반환한다.
    """
    # 빈 줄 기준으로 섹션 분할
    sections: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip() == "":
            if current:
                sections.append(current)
                current = []
        else:
            current.append(line)
    if current:
        sections.append(current)

    def _ul(items: list[str]) -> str:
        return "<ul>" + "".join(f"<li><p>{b}</p></li>" for b in items) + "</ul>"

    html_sections: list[str] = []
    for sec in sections:
        parts: list[str] = []
        bullets: list[str] = []
        for line in sec:
            mb = _BULLET_RE.match(line)
            if mb:
                bullets.append(html.escape(mb.group(1).strip(), quote=False))
                continue
            if bullets:  # 블렛이 아닌 줄을 만나면 열린 <ul>을 닫는다
                parts.append(_ul(bullets))
                bullets = []
            stripped = line.strip()
            ml = _LABEL_RE.match(stripped)
            if ml:  # 라벨은 볼드 처리(GDC <strong> 지원 확인)
                label = html.escape(ml.group(1).strip(), quote=False)
                parts.append(f"<p><strong>{label}</strong></p>")
            else:
                parts.append(f"<p>{html.escape(stripped, quote=False)}</p>")
        if bullets:
            parts.append(_ul(bullets))
        html_sections.append("".join(parts))

    return "<p></p>".join(html_sections)


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
