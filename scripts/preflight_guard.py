#!/usr/bin/env python3
"""Preflight risk classifier for planned browser actions (enforces DryRun approval gates)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

WRITE_KEYWORDS = re.compile(
    r"(submit|confirm|approve|reject|delete|remove|pay|purchase|send|publish|deploy|transfer|checkout|order|"
    r"提交|确认|审批|驳回|删除|支付|下单|发送|发布|转账|申請|承認|削除|送信|発注|確定)",
    re.IGNORECASE,
)

BLOCKED_KEYWORDS = re.compile(
    r"(captcha|recaptcha|turnstile|hcaptcha|bypass.?auth|crack.?password)",
    re.IGNORECASE,
)


def classify_action(action: dict[str, Any]) -> dict[str, Any]:
    kind = str(action.get("type", "unknown")).lower()
    target = str(action.get("target", ""))
    desc = str(action.get("description", ""))
    combined = f"{kind} {target} {desc}"

    if BLOCKED_KEYWORDS.search(combined):
        level = "BLOCKED"
        reason = "Anti-bot/CAPTCHA or auth-bypass operation requires manual user handling."
    elif kind in {"click", "press", "submit", "request"} and WRITE_KEYWORDS.search(combined):
        level = "WRITE_CONFIRM"
        reason = "Mutating action: pause before final click, capture screenshot, require explicit user confirmation."
    else:
        level = "READ"
        reason = "Safe read/navigation/drafting action."

    return {
        "type": kind,
        "target": target,
        "description": desc,
        "risk": level,
        "reason": reason,
    }


def evaluate_plan(actions: list[dict[str, Any]]) -> dict[str, Any]:
    results = [classify_action(a) for a in actions]
    counts = {"READ": 0, "WRITE_CONFIRM": 0, "BLOCKED": 0}
    for r in results:
        counts[r["risk"]] += 1
    verdict = "BLOCKED" if counts["BLOCKED"] else ("REQUIRES_APPROVAL" if counts["WRITE_CONFIRM"] else "AUTO_OK")
    return {"verdict": verdict, "counts": counts, "actions": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight risk check for browser action plan JSON")
    parser.add_argument("--actions", required=True, help="Path to JSON file containing list of actions")
    args = parser.parse_args(argv)

    p = Path(args.actions)
    if not p.exists():
        print(f"ERROR: file not found: {p}", file=sys.stderr)
        return 2

    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print("ERROR: actions JSON must be a list", file=sys.stderr)
        return 2

    report = evaluate_plan(raw)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
