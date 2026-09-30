#!/usr/bin/env python3
"""Load your career data into a CareerOS server (stdlib only).

    CAREEROS_PASSWORD=... python scripts/load_profile.py \
        --server https://api.example.com --email you@example.com \
        --profile personal/profile.json --resume personal/resume.tex \
        [--sponsorship-only Australia] [--catalog all|IN|AU|none]

Imports the profile JSON, marks everything you supplied as verified (it is your own data),
applies sponsorship-only countries, uploads your master LaTeX resume and adds boards from
the curated catalogue. Safe to re-run: duplicates are skipped by the server.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SECTIONS = ("education", "experience", "projects", "research", "publications", "skills", "achievements", "facts", "answers")


class Client:
    def __init__(self, server: str) -> None:
        self.server = server.rstrip("/")
        self.token: str | None = None

    def call(self, method: str, path: str, body: object | None = None) -> object:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(f"{self.server}/api/v1{path}", data=data, method=method)
        request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - user-supplied server
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            sys.exit(f"{method} {path} failed: HTTP {exc.code} {exc.read().decode(errors='replace')[:400]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--server", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--sponsorship-only", nargs="*", default=[])
    parser.add_argument("--catalog", choices=["all", "IN", "AU", "none"], default="none")
    args = parser.parse_args()

    password = os.environ.get("CAREEROS_PASSWORD") or getpass.getpass("CareerOS password: ")
    api = Client(args.server)
    session = api.call("POST", "/auth/login", {"email": args.email, "password": password})
    api.token = session["access_token"]  # type: ignore[index]
    print(f"Signed in as {session['email']}")  # type: ignore[index]

    payload = json.loads(args.profile.read_text(encoding="utf-8"))
    result = api.call("POST", "/profile/import", payload)
    print("Imported:", result["created"], "skipped (already present):", result["skipped"])  # type: ignore[index]

    profile = api.call("GET", "/profile")
    for section in SECTIONS:
        ids = [item["id"] for item in profile[section] if item["verification_status"] != "VERIFIED"]  # type: ignore[index]
        if ids:
            api.call("POST", "/profile/verification", {"section": section, "ids": ids, "status": "VERIFIED"})
            print(f"Verified {len(ids)} {section}")
    basics = payload.get("basics") or {}
    if basics.get("summary"):
        api.call("PUT", "/profile/basics", {"summary": basics["summary"]})  # re-saving confirms the basics

    if args.sponsorship_only:
        api.call("PUT", "/profile/preferences", {"sponsorship_required_countries": args.sponsorship_only})
        print("Sponsorship-only countries:", ", ".join(args.sponsorship_only))

    if args.resume:
        master = api.call("PUT", "/resumes/master", {"tex": args.resume.read_text(encoding="utf-8"), "filename": args.resume.name})
        print(f"Uploaded master resume revision {master['revision']}; compiling...")  # type: ignore[index]
        for _ in range(90):
            master = api.call("GET", "/resumes/master")
            if master["has_pdf"] or master["compile_error"]:  # type: ignore[index]
                break
            time.sleep(4)
        if master["compile_error"]:  # type: ignore[index]
            print("LaTeX error:\n", master["compile_error"])  # type: ignore[index]
        else:
            print(f"Master compiled: {master['pages']} page(s) with {master['engine']}")  # type: ignore[index]

    if args.catalog != "none":
        region = None if args.catalog == "all" else args.catalog
        added = api.call("POST", "/sources/catalog", {"all": True, "region": region, "cadence": "DAILY"})
        print(f"Catalogue boards added: {added['added']} (already present: {added['already_present']})")  # type: ignore[index]

    stats = api.call("GET", "/profile")["stats"]  # type: ignore[index]
    print(f"Profile: {stats['completeness']}% complete, {stats['verified_items']} verified items")


if __name__ == "__main__":
    main()
