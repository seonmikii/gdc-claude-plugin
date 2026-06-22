"""브라우저 핸드오프 인증 (A안, loopback).

로컬 콜백 서버를 127.0.0.1에 띄우고 브라우저로 gdc 웹의 /mcp-auth를 연다.
사용자가 "연결 허용"을 누르면 웹이 MCP 전용 토큰을 콜백으로 POST한다.

보안:
- 콜백은 127.0.0.1에만 바인딩. Host 헤더가 127.0.0.1인지 검증(DNS rebinding 방어).
- 1회용 state로 요청 위조 차단.
- CORS는 localhost/127.0.0.1 또는 web origin에서 온 것만 허용.
- 타임아웃(기본 180초) 경과 시 거부.
"""

from __future__ import annotations

import json
import socket
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _find_chrome() -> str | None:
    """Chrome 실행파일 경로를 찾는다(Windows 레지스트리·표준 경로·PATH)."""
    import os
    import shutil

    candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        os.environ.get("GDC_CHROME_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    # Windows 레지스트리에서 chrome.exe 경로 조회
    try:
        import winreg

        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(
                    hive,
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                ) as k:
                    candidates.append(winreg.QueryValue(k, None))
            except OSError:
                continue
    except ImportError:
        pass

    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def open_in_chrome(url: str) -> bool:
    """Chrome 새 탭으로 직접 연다(webbrowser/$BROWSER·VSCode 내장 브라우저 우회).

    VSCode 통합 터미널은 $BROWSER를 가로채 내장 심플 브라우저로 열기 때문에
    표준 webbrowser를 쓰지 않고 chrome.exe를 직접 실행한다. 못 찾으면 기본 브라우저 폴백.
    """
    import subprocess

    chrome = _find_chrome()
    if chrome:
        try:
            subprocess.Popen(
                [chrome, "--new-tab", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except OSError:
            pass
    return webbrowser.open_new_tab(url)


def _origin_allowed(origin: str, web_url: str) -> bool:
    if not origin:
        return False
    try:
        host = urllib.parse.urlparse(origin).hostname
    except ValueError:
        return False
    if host in ("127.0.0.1", "localhost"):
        return True
    return host == urllib.parse.urlparse(web_url).hostname


def browser_handoff(web_url: str, timeout: float = 180.0) -> dict:
    """브라우저 핸드오프로 MCP 전용 토큰을 받아 반환한다.

    반환: {"access": str, "refresh": str}
    실패 시 TimeoutError 또는 RuntimeError.
    """
    import secrets

    port = _free_port()
    state = secrets.token_urlsafe(24)
    cb = f"http://127.0.0.1:{port}/callback"
    result: dict = {}
    done = threading.Event()

    web_origin = web_url.rstrip("/")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # noqa: D401 - 콘솔 로그 억제
            pass

        def _cors(self):
            origin = self.headers.get("Origin", "")
            if _origin_allowed(origin, web_origin):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "content-type")

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_POST(self):
            # DNS rebinding 방어: Host 헤더가 loopback인지 확인
            host = self.headers.get("Host", "")
            if not host.startswith("127.0.0.1"):
                self.send_response(403)
                self.end_headers()
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, OSError):
                self.send_response(400)
                self._cors()
                self.end_headers()
                return

            if payload.get("state") != state or not payload.get("access") or not payload.get("refresh"):
                self.send_response(400)
                self._cors()
                self.end_headers()
                self.wfile.write(b'{"ok":false}')
                return

            result["access"] = payload["access"]
            result["refresh"] = payload["refresh"]
            if payload.get("workspace_id") is not None:
                result["workspace_id"] = payload["workspace_id"]
            if payload.get("project_id") is not None:
                result["project_id"] = payload["project_id"]
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            done.set()

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 1
    thread = threading.Thread(target=_serve_until, args=(server, done, timeout), daemon=True)
    thread.start()

    url = f"{web_origin}/mcp-auth?cb={urllib.parse.quote(cb)}&state={state}"
    opened = open_in_chrome(url)

    finished = done.wait(timeout=timeout)
    thread.join(timeout=2)
    server.server_close()

    if not finished or not result:
        hint = "" if opened else " (브라우저를 자동으로 열지 못했습니다. 아래 URL을 직접 여세요.)"
        raise TimeoutError(
            f"핸드오프 인증이 시간 내 완료되지 않았습니다{hint}\n{url}"
        )
    return result


def _serve_until(server: HTTPServer, done: threading.Event, timeout: float) -> None:
    import time

    start = time.monotonic()
    while not done.is_set() and time.monotonic() - start < timeout:
        server.handle_request()
