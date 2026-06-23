"""브라우저 핸드오프 인증 (A안, loopback).

로컬 콜백 서버를 127.0.0.1에 띄우고 브라우저로 gdc 웹의 /mcp-auth를 연다.
사용자가 "연결 허용"을 누르면 웹이 MCP 전용 토큰을 콜백으로 **top-level 폼 POST 네비게이션**으로
전달한다. (공개 origin 페이지 → loopback 으로의 fetch는 브라우저 Private Network Access 정책상
비보안 컨텍스트에서 차단되므로 fetch가 아닌 폼 네비게이션을 쓴다. 토큰은 URL이 아닌 POST 본문에 담긴다.)

보안:
- 콜백은 127.0.0.1에만 바인딩. Host 헤더가 127.0.0.1인지 검증(DNS rebinding 방어).
- 1회용 state로 요청 위조 차단.
- 타임아웃(기본 180초) 경과 시 거부.
"""

from __future__ import annotations

import json
import socket
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer


def _parse_body(content_type: str, raw: bytes) -> dict:
    """콜백 본문을 파싱한다. 폼(application/x-www-form-urlencoded)과 JSON 모두 지원."""
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct == "application/json":
        try:
            return json.loads(raw or b"{}")
        except ValueError:
            return {}
    parsed = urllib.parse.parse_qs(raw.decode("utf-8", "replace"))
    return {k: v[0] for k, v in parsed.items()}


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

        def _html(self, code: int, message: str):
            body = (
                "<!doctype html><meta charset=utf-8><title>GDC</title>"
                "<body style='font-family:sans-serif;text-align:center;padding:3rem'>"
                f"<h2>{message}</h2></body>"
            ).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            # DNS rebinding 방어: Host 헤더가 loopback인지 확인
            host = self.headers.get("Host", "")
            if not host.startswith("127.0.0.1"):
                self.send_response(403)
                self.end_headers()
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                data = _parse_body(self.headers.get("Content-Type", ""), self.rfile.read(length))
            except (ValueError, OSError):
                self._html(400, "잘못된 요청입니다.")
                return

            if data.get("state") != state or not data.get("access") or not data.get("refresh"):
                self._html(400, "인증 정보가 올바르지 않습니다. 다시 시도해 주세요.")
                return

            result["access"] = data["access"]
            result["refresh"] = data["refresh"]
            ws, pj = data.get("workspace_id"), data.get("project_id")
            if ws not in (None, ""):
                result["workspace_id"] = int(ws)
            if pj not in (None, ""):
                result["project_id"] = int(pj)
            self._html(200, "인증이 완료되었습니다. 이 탭을 닫고 Claude Code로 돌아가세요.")
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
