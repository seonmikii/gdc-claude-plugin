"""gdc-service REST API 호출용 인증 클라이언트.

인증은 브라우저 핸드오프(gdc_login) 전용이다. 핸드오프로 발급받아
~/.gdc-mcp/credentials.json에 저장된 MCP 전용 토큰만 사용한다.
access 만료(401) 시 refresh로 회전하고, 회전된 토큰은 다시 저장 파일에 반영한다.
워크스페이스/프로젝트 컨텍스트는 레포(루트)별로 tokens 모듈이 별도 관리한다(여기선 인증만).
시크릿은 저장 파일·메모리로만 다룬다(커밋 금지).
"""

from __future__ import annotations

import os

import httpx

from .tokens import load_tokens, save_auth


class NotAuthenticatedError(RuntimeError):
    """저장된 토큰이 없고 자동 로그인도 불가한 상태."""


class GdcClient:
    def __init__(self) -> None:
        self.base_url = os.environ.get("GDC_BASE_URL", "http://localhost:8000").rstrip("/")
        self._access: str | None = None
        self._refresh: str | None = None
        self._http = httpx.Client(base_url=self.base_url, timeout=30.0)
        self._load_saved()

    # --- 인증 ---------------------------------------------------------------
    def _load_saved(self) -> None:
        saved = load_tokens()
        if saved:
            self._access = saved["access"]
            self._refresh = saved["refresh"]

    def _persist(self) -> None:
        if self._access and self._refresh:
            save_auth(self._access, self._refresh, self.base_url)

    def set_tokens(self, access: str, refresh: str, persist: bool = True) -> None:
        """핸드오프 등으로 받은 토큰을 적용한다(인증만)."""
        self._access = access
        self._refresh = refresh
        if persist:
            self._persist()

    @property
    def is_authenticated(self) -> bool:
        return bool(self._access or self._refresh)

    def _ensure_access(self) -> None:
        if self._access:
            return
        if self._refresh and self._try_refresh():
            return
        raise NotAuthenticatedError(
            "인증되지 않았습니다. gdc_login 도구로 브라우저 핸드오프 인증을 먼저 실행하세요."
        )

    def _try_refresh(self) -> bool:
        if not self._refresh:
            return False
        r = self._http.post("/api/accounts/auth/refresh/", json={"refresh": self._refresh})
        if r.status_code != 200:
            return False
        data = r.json()
        self._access = data["access"]
        if data.get("refresh"):
            self._refresh = data["refresh"]
        self._persist()
        return True

    # --- 요청 ---------------------------------------------------------------
    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        self._ensure_access()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._access}"
        r = self._http.request(method, path, headers=headers, **kwargs)
        if r.status_code == 401:
            if not self._try_refresh():
                raise NotAuthenticatedError(
                    "토큰이 만료되었습니다. gdc_login 도구로 다시 인증하세요."
                )
            headers["Authorization"] = f"Bearer {self._access}"
            r = self._http.request(method, path, headers=headers, **kwargs)
        r.raise_for_status()
        return r

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.request("GET", path, **kwargs)
