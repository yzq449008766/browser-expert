#!/usr/bin/env python3
"""Distill a HAR 1.2 recording into filtered API endpoints + a deterministic Python client."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

STATIC_EXTENSIONS = {
    ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".map", ".mp4", ".webm", ".mp3", ".avif",
}

NOISE_HOST_PATTERNS = (
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "hotjar.com",
    "sentry.io",
    "clarity.ms",
    "hm.baidu.com",
)

SENSITIVE_HEADER_KEYS = {
    "authorization", "cookie", "x-api-key", "x-auth-token", "x-csrf-token", "proxy-authorization",
}


def is_noise_entry(entry: dict[str, Any], domain_filter: str | None) -> bool:
    req = entry.get("request") or {}
    res = entry.get("response") or {}
    url = req.get("url", "")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path_lower = parsed.path.lower()

    if not host:
        return True
    if domain_filter and domain_filter.lower() not in host:
        return True
    if any(pat in host for pat in NOISE_HOST_PATTERNS):
        return True
    if any(path_lower.endswith(ext) for ext in STATIC_EXTENSIONS):
        return True

    mime = ((res.get("content") or {}).get("mimeType") or "").lower()
    if mime.startswith(("image/", "font/", "audio/", "video/", "text/css")):
        return True
    if "javascript" in mime:
        return True
    return False


def sanitize_headers(headers: list[dict[str, Any]]) -> tuple[dict[str, str], list[str]]:
    safe: dict[str, str] = {}
    auth_keys: list[str] = []
    for h in headers or []:
        name = str(h.get("name", "")).strip()
        if not name or name.startswith(":"):
            continue
        low = name.lower()
        if low in SENSITIVE_HEADER_KEYS:
            auth_keys.append(name)
        elif low in {"accept", "content-type", "x-requested-with"}:
            safe[name] = str(h.get("value", ""))
    return safe, sorted(set(auth_keys))


def distill_har(har_data: dict[str, Any], domain_filter: str | None = None) -> list[dict[str, Any]]:
    entries = ((har_data.get("log") or {}).get("entries")) or []
    dedup: dict[tuple[str, str, str], dict[str, Any]] = {}

    for entry in entries:
        if is_noise_entry(entry, domain_filter):
            continue
        req = entry.get("request") or {}
        res = entry.get("response") or {}
        method = str(req.get("method", "GET")).upper()
        url = str(req.get("url", ""))
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path or "/"
        query_keys = sorted(parse_qs(parsed.query).keys())
        safe_headers, auth_headers = sanitize_headers(req.get("headers") or [])
        status = int(res.get("status") or 0)
        res_mime = ((res.get("content") or {}).get("mimeType") or "").split(";")[0].strip()

        key = (method, origin, path)
        if key not in dedup:
            dedup[key] = {
                "method": method,
                "origin": origin,
                "path": path,
                "query_params": query_keys,
                "headers": safe_headers,
                "required_auth_headers": auth_headers,
                "sample_status": status,
                "response_mime": res_mime,
                "occurrences": 1,
            }
        else:
            dedup[key]["occurrences"] += 1
            merged_q = sorted(set(dedup[key]["query_params"]) | set(query_keys))
            dedup[key]["query_params"] = merged_q
            merged_a = sorted(set(dedup[key]["required_auth_headers"]) | set(auth_headers))
            dedup[key]["required_auth_headers"] = merged_a

    return sorted(dedup.values(), key=lambda x: (x["origin"], x["path"], x["method"]))


def slugify_func_name(method: str, path: str, used: set[str]) -> str:
    parts = [p for p in re.split(r"[^a-zA-Z0-9]+", path.strip("/")) if p]
    base = f"{method.lower()}_{'_'.join(parts[:4])}" if parts else f"{method.lower()}_root"
    base = re.sub(r"[^a-zA-Z0-9_]", "_", base).lower()
    if base[0].isdigit():
        base = f"ep_{base}"
    name = base
    idx = 2
    while name in used:
        name = f"{base}_{idx}"
        idx += 1
    used.add(name)
    return name


def generate_client_code(endpoints: list[dict[str, Any]]) -> str:
    lines = [
        '#!/usr/bin/env python3',
        '"""Auto-distilled deterministic HTTP client from HAR recording (stdlib only)."""',
        '',
        'from __future__ import annotations',
        '',
        'import json',
        'import os',
        'from typing import Any',
        'from urllib.parse import urlencode',
        'from urllib.request import Request, urlopen',
        '',
        '',
        'class DistilledClient:',
        '    def __init__(self, base_url: str | None = None, extra_headers: dict[str, str] | None = None, timeout: int = 30):',
        '        self.base_url = (base_url or os.environ.get("TARGET_BASE_URL", "")).rstrip("/")',
        '        self.extra_headers = dict(extra_headers or {})',
        '        self.timeout = timeout',
        '',
        '    def _request(self, method: str, origin: str, path: str, params: dict[str, Any] | None = None, body: Any = None, headers: dict[str, str] | None = None) -> tuple[int, str]:',
        '        root = self.base_url or origin',
        '        url = f"{root}{path}"',
        '        if params:',
        '            url = f"{url}?{urlencode(params)}"',
        '        req_headers = dict(headers or {})',
        '        req_headers.update(self.extra_headers)',
        '        data = None',
        '        if body is not None:',
        '            if isinstance(body, (dict, list)):',
        '                data = json.dumps(body).encode("utf-8")',
        '                req_headers.setdefault("Content-Type", "application/json")',
        '            elif isinstance(body, str):',
        '                data = body.encode("utf-8")',
        '            else:',
        '                data = body',
        '        req = Request(url, data=data, headers=req_headers, method=method)',
        '        with urlopen(req, timeout=self.timeout) as resp:',
        '            return resp.status, resp.read().decode("utf-8", errors="replace")',
        '',
    ]
    used_names: set[str] = set()
    for ep in endpoints:
        fn = slugify_func_name(ep["method"], ep["path"], used_names)
        lines.append(f'    def {fn}(self, params: dict[str, Any] | None = None, body: Any = None) -> tuple[int, str]:')
        auth_hint = f' | Auth headers needed: {", ".join(ep["required_auth_headers"])}' if ep["required_auth_headers"] else ""
        lines.append(f'        """{ep["method"]} {ep["path"]} (sample status={ep["sample_status"]}{auth_hint})"""')
        lines.append(f'        return self._request({ep["method"]!r}, {ep["origin"]!r}, {ep["path"]!r}, params=params, body=body, headers={ep["headers"]!r})')
        lines.append('')
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Distill HAR 1.2 into endpoints.json + deterministic client.py")
    parser.add_argument("har_file", help="Path to HAR 1.2 JSON file")
    parser.add_argument("--out-dir", required=True, help="Output directory for endpoints.json and client.py")
    parser.add_argument("--domain", default=None, help="Optional substring filter on host (e.g. api.example.com)")
    args = parser.parse_args(argv)

    har_path = Path(args.har_file)
    if not har_path.exists():
        print(f"ERROR: HAR file not found: {har_path}", file=sys.stderr)
        return 2

    har_data = json.loads(har_path.read_text(encoding="utf-8"))
    endpoints = distill_har(har_data, domain_filter=args.domain)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "endpoints.json").write_text(json.dumps(endpoints, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "client.py").write_text(generate_client_code(endpoints), encoding="utf-8")
    print(json.dumps({"endpoints": len(endpoints), "out_dir": str(out_dir.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
