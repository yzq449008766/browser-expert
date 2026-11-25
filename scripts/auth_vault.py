#!/usr/bin/env python3
"""Persistent site profile & storage-state vault manager for browser-expert."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def get_vault_root() -> Path:
    env_dir = os.environ.get("BROWSER_VAULT_DIR", "").strip()
    root = Path(env_dir).expanduser() if env_dir else (Path.home() / ".browser-expert-vault")
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_slug(slug: str) -> str:
    s = slug.strip().lower()
    if not SLUG_RE.match(s):
        raise ValueError(f"Invalid site slug '{slug}': use lowercase letters, digits, '.', '_', '-'")
    return s


def site_dir(root: Path, slug: str) -> Path:
    return root / validate_slug(slug)


def meta_path(sdir: Path) -> Path:
    return sdir / "meta.json"


def cmd_init(args: argparse.Namespace) -> int:
    root = get_vault_root()
    sdir = site_dir(root, args.site)
    profile_dir = sdir / "chrome-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "site": validate_slug(args.site),
        "url": args.url or "",
        "notes": args.notes or "",
        "profile_dir": str(profile_dir.resolve()),
        "storage_state": str((sdir / "storage_state.json").resolve()),
        "created_at": now,
        "updated_at": now,
    }
    if meta_path(sdir).exists():
        old = json.loads(meta_path(sdir).read_text(encoding="utf-8"))
        meta["created_at"] = old.get("created_at", now)
        if not args.url:
            meta["url"] = old.get("url", "")
        if not args.notes:
            meta["notes"] = old.get("notes", "")
    meta_path(sdir).write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    root = get_vault_root()
    items = []
    for child in sorted(root.iterdir()):
        mp = meta_path(child)
        if child.is_dir() and mp.exists():
            meta = json.loads(mp.read_text(encoding="utf-8"))
            state_file = Path(meta.get("storage_state", child / "storage_state.json"))
            prof_dir = Path(meta.get("profile_dir", child / "chrome-profile"))
            items.append({
                "site": meta.get("site", child.name),
                "url": meta.get("url", ""),
                "has_profile": prof_dir.exists() and any(prof_dir.iterdir()),
                "has_storage_state": state_file.exists(),
                "updated_at": meta.get("updated_at", ""),
            })
    print(json.dumps({"vault_root": str(root.resolve()), "sites": items}, ensure_ascii=False, indent=2))
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    root = get_vault_root()
    sdir = site_dir(root, args.site)
    prof = sdir / "chrome-profile"
    if not prof.exists():
        print(f"ERROR: site '{args.site}' not initialized. Run: auth_vault.py init {args.site}", file=sys.stderr)
        return 2
    print(str(prof.resolve()))
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    root = get_vault_root()
    sdir = site_dir(root, args.site)
    if not sdir.exists():
        print(f"Site '{args.site}' does not exist.", file=sys.stderr)
        return 2
    shutil.rmtree(sdir)
    print(json.dumps({"removed": args.site, "status": "ok"}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Manage persistent browser profiles & auth states.")
    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create or update a site vault entry")
    p_init.add_argument("site", help="Site slug (e.g. supplier-portal)")
    p_init.add_argument("--url", default="", help="Base URL of the site")
    p_init.add_argument("--notes", default="", help="Optional non-secret notes")
    p_init.set_defaults(func=cmd_init)

    p_list = sub.add_parser("list", help="List initialized sites in vault")
    p_list.set_defaults(func=cmd_list)

    p_prof = sub.add_parser("profile", help="Print absolute Chrome profile directory for a site")
    p_prof.add_argument("site", help="Site slug")
    p_prof.set_defaults(func=cmd_profile)

    p_rm = sub.add_parser("remove", help="Remove a site profile from vault")
    p_rm.add_argument("site", help="Site slug")
    p_rm.set_defaults(func=cmd_remove)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
