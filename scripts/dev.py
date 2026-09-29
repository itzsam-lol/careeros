#!/usr/bin/env python3
"""Cross-platform developer task runner (stdlib only).

    python scripts/dev.py <command>

Works the same on Windows, macOS and Linux. The Makefile is a thin wrapper around it.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
WEB = ROOT / "apps" / "web"
MOBILE = ROOT / "apps" / "mobile"

COLORS = ["\033[36m", "\033[35m", "\033[33m", "\033[32m", "\033[34m"]
RESET = "\033[0m"


def tool(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:
        sys.exit(f"error: `{name}` is not installed or not on PATH")
    return resolved


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> int:
    print(f"$ {' '.join(cmd)}  (in {cwd.relative_to(ROOT) or '.'})", flush=True)
    code = subprocess.call(cmd, cwd=cwd)
    if check and code != 0:
        sys.exit(code)
    return code


def run_parallel(procs: dict[str, tuple[list[str], Path]]) -> None:
    """Run long-lived processes side by side with prefixed, coloured output."""
    running: list[subprocess.Popen[str]] = []
    width = max(len(name) for name in procs)

    def pump(name: str, color: str, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(f"{color}{name.ljust(width)} |{RESET} {line}")
            sys.stdout.flush()

    for index, (name, (cmd, cwd)) in enumerate(procs.items()):
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        running.append(proc)
        threading.Thread(
            target=pump, args=(name, COLORS[index % len(COLORS)], proc), daemon=True
        ).start()

    try:
        while all(proc.poll() is None for proc in running):
            try:
                running[0].wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                continue
    except KeyboardInterrupt:
        pass
    finally:
        for proc in running:
            if proc.poll() is None:
                if os.name == "nt":
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGINT)
        for proc in running:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


# --- commands ----------------------------------------------------------------------------


def cmd_setup(_: argparse.Namespace) -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        shutil.copyfile(ROOT / ".env.example", env_file)
        print("created .env from .env.example")
    run([tool("uv"), "sync"], cwd=API)
    run([tool("pnpm"), "install"])
    cmd_db(_)
    cmd_migrate(_)
    print("\nSetup complete. Start everything with: python scripts/dev.py dev")


def cmd_db(_: argparse.Namespace) -> None:
    run([tool("docker"), "compose", "up", "-d", "--wait", "db"])


def cmd_migrate(_: argparse.Namespace) -> None:
    run([tool("uv"), "run", "alembic", "upgrade", "head"], cwd=API)


def cmd_makemigration(args: argparse.Namespace) -> None:
    run(
        [tool("uv"), "run", "alembic", "revision", "--autogenerate", "-m", args.message],
        cwd=API,
    )


def _api_cmd() -> list[str]:
    return [
        tool("uv"), "run", "uvicorn", "careeros.main:create_app", "--factory", "--reload",
        "--host", "0.0.0.0", "--port", "8000",
    ]  # fmt: skip


def cmd_dev(_: argparse.Namespace) -> None:
    cmd_db(_)
    cmd_migrate(_)
    run_parallel(
        {
            "api": (_api_cmd(), API),
            "worker": ([tool("uv"), "run", "python", "-m", "careeros.workers"], API),
            "web": ([tool("pnpm"), "--filter", "@careeros/web", "dev"], ROOT),
        }
    )


def cmd_api(_: argparse.Namespace) -> None:
    run(_api_cmd(), cwd=API)


def cmd_worker(_: argparse.Namespace) -> None:
    run([tool("uv"), "run", "python", "-m", "careeros.workers"], cwd=API)


def cmd_web(_: argparse.Namespace) -> None:
    run([tool("pnpm"), "--filter", "@careeros/web", "dev"])


def cmd_mobile(_: argparse.Namespace) -> None:
    run([tool("pnpm"), "--filter", "@careeros/mobile", "start"])


def cmd_test(args: argparse.Namespace) -> None:
    pytest_cmd = [tool("uv"), "run", "pytest"]
    if args.unit:
        pytest_cmd += ["-m", "not db and not browser and not latex"]
    run(pytest_cmd, cwd=API)
    if not args.backend_only and (WEB / "package.json").exists():
        run([tool("pnpm"), "-r", "--if-present", "test"])


def cmd_lint(_: argparse.Namespace) -> None:
    run([tool("uv"), "run", "ruff", "check", "careeros", "tests"], cwd=API)
    run([tool("uv"), "run", "ruff", "format", "--check", "careeros", "tests"], cwd=API)
    run([tool("pnpm"), "-r", "--if-present", "lint"])


def cmd_typecheck(_: argparse.Namespace) -> None:
    run([tool("uv"), "run", "mypy", "careeros"], cwd=API)
    run([tool("pnpm"), "-r", "--if-present", "typecheck"])


def cmd_format(_: argparse.Namespace) -> None:
    run([tool("uv"), "run", "ruff", "check", "--fix", "careeros", "tests"], cwd=API)
    run([tool("uv"), "run", "ruff", "format", "careeros", "tests"], cwd=API)
    run([tool("pnpm"), "-r", "--if-present", "format"])


def cmd_gen_types(_: argparse.Namespace) -> None:
    schema = ROOT / "packages" / "api-client" / "openapi.json"
    run([tool("uv"), "run", "python", "-m", "careeros.tools.export_openapi", str(schema)], cwd=API)
    run([tool("pnpm"), "--filter", "@careeros/api-client", "generate"])


def cmd_seed(_: argparse.Namespace) -> None:
    run([tool("uv"), "run", "python", "-m", "careeros.tools.seed"], cwd=API)


COMMANDS: dict[str, tuple[Callable[[argparse.Namespace], None], str]] = {
    "setup": (cmd_setup, "install dependencies, start Postgres, run migrations"),
    "dev": (cmd_dev, "run API, worker and web app together"),
    "api": (cmd_api, "run the API with auto-reload"),
    "worker": (cmd_worker, "run the background task worker"),
    "web": (cmd_web, "run the Next.js web app"),
    "mobile": (cmd_mobile, "run the Expo mobile app"),
    "db": (cmd_db, "start Postgres + pgvector in Docker"),
    "migrate": (cmd_migrate, "apply database migrations"),
    "makemigration": (cmd_makemigration, "autogenerate a migration"),
    "test": (cmd_test, "run test suites"),
    "lint": (cmd_lint, "run linters"),
    "typecheck": (cmd_typecheck, "run type checkers"),
    "format": (cmd_format, "auto-format code"),
    "gen-types": (cmd_gen_types, "regenerate the typed API client from OpenAPI"),
    "seed": (cmd_seed, "load a demo profile and job sources"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="CareerOS developer tasks")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        p = sub.add_parser(name, help=help_text)
        if name == "test":
            p.add_argument("--unit", action="store_true", help="skip DB/browser/LaTeX tests")
            p.add_argument("--backend-only", action="store_true")
        if name == "makemigration":
            p.add_argument("message")
    args = parser.parse_args()
    COMMANDS[args.command][0](args)


if __name__ == "__main__":
    main()
