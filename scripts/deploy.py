#!/usr/bin/env python3
"""Provision and deploy CareerOS to a single Google Compute Engine VM (stdlib only).

    python scripts/deploy.py provision            # static IP, firewall, e2-medium VM (once)
    python scripts/deploy.py deploy               # ship the current git commit and (re)start
    python scripts/deploy.py create-user --email you@example.com [--name "You"]
    python scripts/deploy.py status | logs [service]

Uses your active gcloud project unless --project is given. Everything runs through
`gcloud compute ssh/scp`, so no extra credentials or open SSH ports are required beyond
Google's standard SSH access.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {
    "zone": "asia-south1-b",
    "region": "asia-south1",
    "instance": "careeros-vm",
    "address": "careeros-ip",
    "machine": "e2-medium",
    "disk_gb": "30",
}
REMOTE_DIR = "/opt/careeros"


def gcloud() -> str:
    exe = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if not exe:
        sys.exit("gcloud CLI not found")
    return exe


def run(args: list[str], *, check: bool = True, capture: bool = False) -> str:
    printable = " ".join(a if " " not in a else f'"{a}"' for a in args[1:])
    print(f"$ gcloud {printable}" if args[0] == gcloud() else f"$ {' '.join(args)}", flush=True)
    result = subprocess.run(args, check=False, text=True, capture_output=capture)
    if check and result.returncode != 0:
        if capture:
            sys.stderr.write(result.stdout + result.stderr)
        sys.exit(result.returncode)
    return (result.stdout or "").strip() if capture else ""


def common(opts: argparse.Namespace) -> list[str]:
    flags = [f"--zone={opts.zone}"]
    if opts.project:
        flags.append(f"--project={opts.project}")
    return flags


def ssh(opts: argparse.Namespace, command: str, *, check: bool = True) -> None:
    run([gcloud(), "compute", "ssh", opts.instance, *common(opts), "--quiet", f"--command={command}"], check=check)


def external_ip(opts: argparse.Namespace) -> str:
    project = [f"--project={opts.project}"] if opts.project else []
    return run(
        [gcloud(), "compute", "addresses", "describe", opts.address, f"--region={opts.region}", *project,
         "--format=value(address)"],
        capture=True,
    )  # fmt: skip


def cmd_provision(opts: argparse.Namespace) -> None:
    project = [f"--project={opts.project}"] if opts.project else []
    run([gcloud(), "services", "enable", "compute.googleapis.com", *project])
    run(
        [gcloud(), "compute", "addresses", "create", opts.address, f"--region={opts.region}", *project],
        check=False,
    )
    run(
        [gcloud(), "compute", "firewall-rules", "create", "careeros-allow-web", "--allow=tcp:80,tcp:443,tcp:8443,udp:443",
         "--target-tags=careeros", "--description=CareerOS web + API over HTTPS", *project],
        check=False,
    )  # fmt: skip
    ip = external_ip(opts)
    run(
        [
            gcloud(), "compute", "instances", "create", opts.instance, *common(opts),
            f"--machine-type={opts.machine}", "--image-family=ubuntu-2404-lts-amd64",
            "--image-project=ubuntu-os-cloud", f"--boot-disk-size={opts.disk_gb}GB",
            "--boot-disk-type=pd-balanced", "--tags=careeros", f"--address={ip}",
            "--scopes=https://www.googleapis.com/auth/devstorage.read_write,"
            "https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write",
            "--shielded-secure-boot", "--shielded-vtpm", "--shielded-integrity-monitoring",
        ],
        check=False,
    )  # fmt: skip
    print(f"\nVM ready at {ip}. Next: python scripts/deploy.py deploy")


def cmd_deploy(opts: argparse.Namespace) -> None:
    sha = run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture=True)
    dirty = run(["git", "-C", str(ROOT), "status", "--porcelain"], capture=True)
    if dirty and not opts.allow_dirty:
        sys.exit("Working tree has uncommitted changes; commit first (or pass --allow-dirty).")
    ip = external_ip(opts)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"careeros-{sha}.tar.gz"
        run(["git", "-C", str(ROOT), "archive", "--format=tar.gz", f"--output={archive}", "HEAD"])
        run([gcloud(), "compute", "scp", *common(opts), "--quiet", str(archive), f"{opts.instance}:/tmp/careeros.tar.gz"])
    release = f"{REMOTE_DIR}/releases/{sha}"
    ssh(
        opts,
        " && ".join(
            [
                f"sudo mkdir -p {release}",
                f"sudo chown -R $USER:$USER {REMOTE_DIR}",
                f"tar -xzf /tmp/careeros.tar.gz -C {release}",
                f"ln -sfn {release} {REMOTE_DIR}/current",
                f"([ -f {REMOTE_DIR}/.env.production ] || bash {REMOTE_DIR}/current/infrastructure/vm/bootstrap.sh {ip} {opts.acme_email})",
                f"ln -sfn {REMOTE_DIR}/.env.production {REMOTE_DIR}/current/.env.production",
                f"cd {REMOTE_DIR}/current && sudo docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build --remove-orphans",
                "sudo docker image prune -f >/dev/null",
                f"ls -1dt {REMOTE_DIR}/releases/* | tail -n +6 | xargs -r rm -rf",
            ]
        ),
    )
    domain = f"{ip.replace('.', '-')}.sslip.io"
    print("\nWaiting for HTTPS (first certificate issuance can take a minute)...", flush=True)
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"https://{domain}:8443/healthz", timeout=10) as response:  # noqa: S310
                body = json.loads(response.read())
                print(f"API healthy: {body}")
                break
        except OSError:
            time.sleep(5)
    else:
        print("API did not become healthy yet; check `python scripts/deploy.py logs api`.")
    print(f"\nWeb:  https://{domain}\nAPI:  https://{domain}:8443\nRelease: {sha}")


def cmd_create_user(opts: argparse.Namespace) -> None:
    name = f" --name '{opts.name}'" if opts.name else ""
    ssh(
        opts,
        f"cd {REMOTE_DIR}/current && sudo docker compose --env-file .env.production -f docker-compose.prod.yml "
        f"exec -T api python -m careeros.tools.create_user --email '{opts.email}'{name} --generate",
    )


def cmd_status(opts: argparse.Namespace) -> None:
    ssh(opts, f"cd {REMOTE_DIR}/current && sudo docker compose --env-file .env.production -f docker-compose.prod.yml ps")


def cmd_logs(opts: argparse.Namespace) -> None:
    service = opts.service or ""
    ssh(
        opts,
        f"cd {REMOTE_DIR}/current && sudo docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=200 {service}",
        check=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=os.environ.get("CLOUDSDK_CORE_PROJECT"))
    for key, value in DEFAULTS.items():
        parser.add_argument(f"--{key.replace('_', '-')}", dest=key, default=value)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("provision")
    deploy = sub.add_parser("deploy")
    deploy.add_argument("--allow-dirty", action="store_true")
    deploy.add_argument("--acme-email", default="")
    user = sub.add_parser("create-user")
    user.add_argument("--email", required=True)
    user.add_argument("--name")
    sub.add_parser("status")
    logs = sub.add_parser("logs")
    logs.add_argument("service", nargs="?")
    opts = parser.parse_args()
    {
        "provision": cmd_provision,
        "deploy": cmd_deploy,
        "create-user": cmd_create_user,
        "status": cmd_status,
        "logs": cmd_logs,
    }[opts.command](opts)


if __name__ == "__main__":
    main()
