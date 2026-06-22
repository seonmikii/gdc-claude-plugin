"""MCP 전용 JWT 토큰과 레포별 워크스페이스/프로젝트 컨텍스트의 로컬 저장.

~/.gdc-mcp/credentials.json 구조:
    {
      "access": "...", "refresh": "...", "base_url": "...",
      "workspace_id": 2, "project_id": 4,         # 글로벌 fallback(마지막 선택/루트 미상)
      "contexts": {                                # 레포(루트)별 선택
        "c:/projects/repoa": {"workspace_id": 2, "project_id": 4},
        "c:/projects/repob": {"workspace_id": 3, "project_id": 7}
      }
    }

인증(토큰)은 사용자 단위로 공유하고, 워크스페이스/프로젝트 컨텍스트는 레포(루트)별로 분리한다.
POSIX는 0600. Windows는 사용자 프로필 ACL에 의존(시크릿 커밋·로그 노출 금지).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse


def _cred_path() -> Path:
    return Path.home() / ".gdc-mcp" / "credentials.json"


def _read() -> dict:
    path = _cred_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def _write(data: dict) -> None:
    path = _cred_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    if os.name == "posix":
        os.chmod(path, 0o600)


def normalize_root(root: str | None) -> str | None:
    """file:// URI 또는 경로를 비교 가능한 정규 경로로 변환(소문자·슬래시 통일)."""
    if not root:
        return None
    s = str(root)
    if s.startswith("file://"):
        s = unquote(urlparse(s).path)  # 예: /c:/Projects/repoA
        if re.match(r"^/[A-Za-z]:", s):  # Windows 드라이브면 선행 슬래시 제거
            s = s[1:]
    return s.replace("\\", "/").rstrip("/").lower()


def load_tokens() -> dict | None:
    """저장된 토큰(전체 dict)을 반환한다. 없거나 손상되면 None."""
    d = _read()
    if not d.get("access") or not d.get("refresh"):
        return None
    return d


def save_auth(access: str, refresh: str, base_url: str) -> None:
    """인증 토큰만 갱신한다(컨텍스트는 보존)."""
    d = _read()
    d["access"] = access
    d["refresh"] = refresh
    d["base_url"] = base_url
    _write(d)


def save_context(root: str | None, workspace_id: int | None, project_id: int | None) -> None:
    """선택한 워크스페이스/프로젝트를 레포(루트)별로 저장한다.

    root가 있으면 그 루트 키에 저장하고, 항상 글로벌 fallback도 갱신한다(루트 미상 시 사용).
    """
    d = _read()
    nroot = normalize_root(root)
    if nroot:
        d.setdefault("contexts", {})[nroot] = {
            "workspace_id": workspace_id,
            "project_id": project_id,
        }
    d["workspace_id"] = workspace_id
    d["project_id"] = project_id
    _write(d)


def load_context(root: str | None) -> dict:
    """루트에 해당하는 컨텍스트를 반환한다. 없으면 글로벌 fallback."""
    d = _read()
    nroot = normalize_root(root)
    ctxs = d.get("contexts", {})
    if nroot and nroot in ctxs:
        return ctxs[nroot]
    return {"workspace_id": d.get("workspace_id"), "project_id": d.get("project_id")}


def clear_tokens() -> None:
    _cred_path().unlink(missing_ok=True)
