#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
ASSETS_SCRIPT = ROOT_DIR / "backend" / "scripts" / "prepare_assets.py"
APP_LOG = ROOT_DIR / "app.log"
APP_PID = ROOT_DIR / "app.pid"
APP_PORT = int(os.getenv("PORT", "8000"))
APP_URL = f"http://127.0.0.1:{APP_PORT}"
APP_REQUIRED_MODULES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "httpx": "httpx",
    "shapely": "shapely",
    "polyline": "polyline",
    "pyshp": "shapefile",
}


def is_windows() -> bool:
    return os.name == "nt"


def run_command(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd or ROOT_DIR, env=env, check=True)




def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= getattr(response, "status", 200) < 400
    except Exception:
        return False


def wait_for_url(url: str, timeout_sec: int) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if http_ok(url):
            return True
        time.sleep(1)
    return False


def write_pid(path: Path, pid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid), encoding="utf-8")


def read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def process_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        if is_windows():
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                check=False,
            )
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def terminate_process(pid_file: Path) -> None:
    pid = read_pid(pid_file)
    if not process_running(pid):
        if pid_file.exists():
            pid_file.unlink()
        return

    if is_windows():
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    time.sleep(1)
    if pid_file.exists():
        pid_file.unlink()


def start_background(command: list[str], log_path: Path, pid_path: Path, *, env: dict[str, str] | None = None) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w", encoding="utf-8")
    kwargs: dict[str, object] = {
        "cwd": str(ROOT_DIR),
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
        "env": env or os.environ.copy(),
        "close_fds": True,
    }
    if is_windows():
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True

    process = subprocess.Popen(command, **kwargs)
    write_pid(pid_path, process.pid)
    return process.pid


def tail_file(path: Path, *, lines: int = 20) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = text.splitlines()
    return "\n".join(parts[-lines:])


def ensure_python_requirements() -> None:
    missing = [name for name, module in APP_REQUIRED_MODULES.items() if importlib.util.find_spec(module) is None]
    if missing:
        package_list = ", ".join(missing)
        raise RuntimeError(
            "Missing Python packages for the web app: "
            f"{package_list}. Run `{Path(sys.executable).name} -m pip install -r requirements.txt` first."
        )


def ensure_assets() -> None:
    if not ASSETS_SCRIPT.exists():
        raise FileNotFoundError(f"Missing {ASSETS_SCRIPT}")
    run_command([sys.executable, str(ASSETS_SCRIPT)])


def build_cpp_backend() -> None:
    print("Building C++ backend...")
    run_command(["g++", "-std=c++17", "-O3", "backend/algorithms/Astar.cpp", "backend/algorithms/GA.cpp", "backend/algorithms/main.cpp", "-o", "backend/router"])
    if not (ROOT_DIR / "data" / "assets" / "data_graph.txt").exists():
        print("Extracting graph data...")
        run_command([sys.executable, "backend/scripts/build_cpp_graph.py"])

def setup() -> None:
    ensure_assets()
    build_cpp_backend()

def start() -> None:
    if not http_ok(f"{APP_URL}/api/meta/boundary"):
        ensure_python_requirements()
        print("Starting web app ...")
        env = os.environ.copy()
        env["PORT"] = str(APP_PORT)
        start_background([sys.executable, "-m", "backend.server"], APP_LOG, APP_PID, env=env)
        if not wait_for_url(f"{APP_URL}/api/meta/boundary", 30):
            app_tail = tail_file(APP_LOG)
            detail = f"\n\nLast app log lines:\n{app_tail}" if app_tail else ""
            raise RuntimeError(f"Web app failed to start. Check {APP_LOG}.{detail}")

    print(f"Web dang chay tai: {APP_URL}")
    try:
        webbrowser.open(APP_URL)
    except Exception:
        pass


def stop() -> None:
    terminate_process(APP_PID)
    print("Da tat web app.")


def status() -> None:
    print(f"APP: {'up' if http_ok(f'{APP_URL}/api/meta/boundary') else 'down'} ({APP_URL})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cross-platform launcher for the Chicago route planner.")
    parser.add_argument(
        "command",
        nargs="?",
        default="start",
        choices=["start", "stop", "status", "setup"],
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "start":
            start()
        elif args.command == "stop":
            stop()
        elif args.command == "status":
            status()
        elif args.command == "setup":
            setup()
        else:
            raise ValueError(f"Unknown command: {args.command}")
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
