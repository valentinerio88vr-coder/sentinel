#!/usr/bin/env python3
"""Builds TUTORIAL.html from docs/tutorial.src.html, inlining every image as a data URI.

The result is a single self-contained file: no external CSS, fonts, scripts or images,
so it renders identically in a browser, an email client, or offline on a plane.

    python3 tools/build_tutorial.py
"""
from __future__ import annotations

import base64
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "docs", "tutorial.src.html")
OUT = os.path.join(ROOT, "TUTORIAL.html")

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml", ".ico": "image/x-icon", ".webp": "image/webp"}


def inline(match: re.Match[str]) -> str:
    rel = match.group(1)
    for base in ("docs", "."):
        path = os.path.join(ROOT, base, rel)
        if os.path.exists(path):
            with open(path, "rb") as fh:
                data = base64.b64encode(fh.read()).decode()
            mime = MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
            return f"data:{mime};base64,{data}"
    raise SystemExit(f"missing image: {rel}")


def main() -> None:
    with open(SRC, encoding="utf-8") as fh:
        src = fh.read()
    out = re.sub(r"\{\{IMG:([^}]+)\}\}", inline, src)
    if "{{IMG:" in out:
        raise SystemExit("unreplaced image marker remains")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(out)

    external = re.findall(r'(?:src|href)="https?://', out)
    print(f"wrote {OUT}  ({len(out) / 1024:.0f} KB)")
    print(f"  inlined images:      {out.count('data:image/')}")
    print(f"  external resources:  {len(external)} (links only, no assets)")


if __name__ == "__main__":
    main()
