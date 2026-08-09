"""安全清除佔用指定 ngrok 靜態網域的舊 tunnel session。"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request


API_BASE = "https://api.ngrok.com"


def _normalise_host(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    parsed = urllib.parse.urlsplit(value if "://" in value else f"//{value}")
    return (parsed.hostname or "").lower().rstrip(".")


def _endpoint_matches_domain(endpoint: dict, domain: str) -> bool:
    expected = _normalise_host(domain)
    if not expected:
        return False
    candidates = [
        endpoint.get("host", ""),
        endpoint.get("hostport", ""),
        endpoint.get("url", ""),
        endpoint.get("public_url", ""),
    ]
    return any(_normalise_host(str(candidate)) == expected for candidate in candidates)


def _api_request(api_key: str, method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "ngrok-version": "2",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        raw = response.read()
        return response.status, json.loads(raw.decode("utf-8")) if raw else {}


def stop_stale_domain_sessions(domain: str, api_key: str, wait_seconds: float = 2.0) -> dict:
    """停止所有正在佔用 *domain* 的 agent tunnel session。

    僅精確比對目前設定的靜態網域；不會列舉後任意停止帳號中的其他 agent。
    API 發生錯誤時回傳 warning，讓呼叫端繼續採用本機清理與重試。
    """
    if not api_key or not domain:
        return {"ok": True, "checked": False, "stopped_session_ids": [], "warning": ""}

    endpoint_url = f"{API_BASE}/endpoints"
    matching_sessions = set()
    try:
        # 逐頁讀取，避免帳號存在許多 endpoint 時漏掉目標網域。
        for _ in range(20):
            _, payload = _api_request(api_key, "GET", endpoint_url)
            for endpoint in payload.get("endpoints", []):
                if not _endpoint_matches_domain(endpoint, domain):
                    continue
                session_id = (endpoint.get("tunnel_session") or {}).get("id")
                if session_id:
                    matching_sessions.add(session_id)
            endpoint_url = payload.get("next_page_uri")
            if endpoint_url and endpoint_url.startswith("/"):
                endpoint_url = API_BASE + endpoint_url
            if not endpoint_url:
                break
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        return {"ok": False, "checked": True, "stopped_session_ids": [], "warning": str(exc)}

    stopped = []
    for session_id in sorted(matching_sessions):
        try:
            status, _ = _api_request(
                api_key,
                "POST",
                f"{API_BASE}/tunnel_sessions/{urllib.parse.quote(session_id, safe='')}/stop",
                {"id": session_id},
            )
            if status in (200, 202, 204):
                stopped.append(session_id)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            return {
                "ok": False,
                "checked": True,
                "stopped_session_ids": stopped,
                "warning": f"停止 tunnel session 失敗：{exc}",
            }

    if stopped and wait_seconds:
        time.sleep(wait_seconds)
    return {"ok": True, "checked": True, "stopped_session_ids": stopped, "warning": ""}
