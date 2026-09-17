#!/usr/bin/env python3
"""
@file run.py
@brief File khởi động và quản lý tiến trình cho Chicago Route Planner.
@author [Lê Phước Minh Quân & others]
@date 2026-09-18
@details File này cung cấp một CLI (Command Line Interface) đa nền tảng để thiết lập môi trường, 
         biên dịch lõi thuật toán C++, khởi động, dừng và kiểm tra trạng thái của web server (FastAPI).
         Sử dụng: `python run.py [start|stop|status|setup]`
"""

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


# ==========================================
# CẤU HÌNH BIẾN TOÀN CỤC & ĐƯỜNG DẪN
# ==========================================

ROOT_DIR = Path(__file__).resolve().parent
ASSETS_SCRIPT = ROOT_DIR / "backend" / "scripts" / "prepare_assets.py"
APP_LOG = ROOT_DIR / "app.log"
APP_PID = ROOT_DIR / "app.pid"
APP_PORT = int(os.getenv("PORT", "8000"))
APP_URL = f"http://127.0.0.1:{APP_PORT}"

# Danh sách các thư viện Python bắt buộc phải có để chạy server
APP_REQUIRED_MODULES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "httpx": "httpx",
    "shapely": "shapely",
    "polyline": "polyline",
    "pyshp": "shapefile",
}


# ==========================================
# CÁC HÀM TIỆN ÍCH HỆ THỐNG
# ==========================================

def is_windows() -> bool:
    """
    @brief Kiểm tra xem hệ điều hành hiện tại có phải là Windows hay không.
    @return True nếu là Windows, ngược lại False.
    """
    return os.name == "nt"


def run_command(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """
    @brief Chạy một lệnh terminal dưới dạng tiến trình con (subprocess).
    @param command Danh sách chuỗi chứa lệnh và tham số.
    @param cwd Thư mục làm việc hiện tại cho tiến trình con (mặc định là ROOT_DIR).
    @param env Biến môi trường tùy chỉnh.
    @raises subprocess.CalledProcessError nếu lệnh chạy thất bại (mã thoát khác 0).
    """
    subprocess.run(command, cwd=cwd or ROOT_DIR, env=env, check=True)


def http_ok(url: str, timeout: float = 2.0) -> bool:
    """
    @brief Kiểm tra xem một URL có phản hồi trạng thái HTTP hợp lệ (200-399) hay không.
    @param url URL cần kiểm tra.
    @param timeout Thời gian chờ tối đa (giây).
    @return True nếu URL phản hồi bình thường, False nếu lỗi hoặc timeout.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= getattr(response, "status", 200) < 400
    except Exception:
        return False


def wait_for_url(url: str, timeout_sec: int) -> bool:
    """
    @brief Chờ đợi cho đến khi một URL sẵn sàng phản hồi hoặc hết thời gian chờ (timeout).
    @param url URL cần kiểm tra (thường là endpoint health-check của server).
    @param timeout_sec Thời gian chờ tối đa (giây).
    @return True nếu server lên kịp, False nếu quá thời gian.
    """
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if http_ok(url):
            return True
        time.sleep(1)
    return False


# ==========================================
# QUẢN LÝ TIẾN TRÌNH (PROCESS PID)
# ==========================================

def write_pid(path: Path, pid: int) -> None:
    """
    @brief Ghi mã tiến trình (PID) vào file để quản lý.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid), encoding="utf-8")


def read_pid(path: Path) -> int | None:
    """
    @brief Đọc mã tiến trình (PID) từ file.
    """
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def process_running(pid: int | None) -> bool:
    """
    @brief Kiểm tra xem một tiến trình có PID cụ thể có đang chạy trên hệ thống không.
    @param pid Mã tiến trình cần kiểm tra.
    @return True nếu tiến trình đang chạy.
    """
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
    """
    @brief Dừng một tiến trình đang chạy dựa trên PID file và xóa PID file đó.
    @param pid_file Đường dẫn đến file chứa PID.
    """
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
    """
    @brief Chạy một lệnh dưới dạng background (chạy ngầm) và độc lập với terminal hiện tại.
    @param command Lệnh cần chạy.
    @param log_path Nơi ghi đầu ra log của tiến trình ngầm.
    @param pid_path Nơi lưu PID của tiến trình ngầm.
    @param env Biến môi trường.
    @return Mã tiến trình (PID) vừa tạo.
    """
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
    """
    @brief Lấy n dòng cuối cùng của một file log để debug khi lỗi.
    """
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = text.splitlines()
    return "\n".join(parts[-lines:])


def ensure_python_requirements() -> None:
    """
    @brief Kiểm tra xem môi trường ảo/máy tính có đủ các thư viện Python yêu cầu chưa.
    @raises RuntimeError Nếu thiếu thư viện.
    """
    missing = [name for name, module in APP_REQUIRED_MODULES.items() if importlib.util.find_spec(module) is None]
    if missing:
        package_list = ", ".join(missing)
        raise RuntimeError(
            "Missing Python packages for the web app: "
            f"{package_list}. Run `{Path(sys.executable).name} -m pip install -r requirements.txt` first."
        )


def ensure_assets() -> None:
    """
    @brief Kích hoạt script tải và chuẩn bị các dữ liệu cần thiết (assets).
    """
    if not ASSETS_SCRIPT.exists():
        raise FileNotFoundError(f"Missing {ASSETS_SCRIPT}")
    run_command([sys.executable, str(ASSETS_SCRIPT)])


# ==========================================
# CÁC LỆNH CHÍNH (CLI COMMANDS)
# ==========================================

def build_cpp_backend() -> None:
    """
    @brief Biên dịch mã nguồn C++ (các thuật toán A*, GA) và trích xuất đồ thị dữ liệu ban đầu.
    """
    print("Building C++ backend...")
    run_command(["g++", "-std=c++17", "-O3", "backend/algorithms/Astar.cpp", "backend/algorithms/GA.cpp", "backend/algorithms/main.cpp", "-o", "backend/router"])
    if not (ROOT_DIR / "data" / "assets" / "data_graph.txt").exists():
        print("Extracting graph data...")
        run_command([sys.executable, "backend/scripts/build_cpp_graph.py"])

def setup() -> None:
    """
    @brief Hàm thiết lập dự án ban đầu (cài đặt assets và biên dịch lõi C++).
    @details Dành cho lần khởi chạy đầu tiên hoặc khi có cập nhật code C++.
    """
    ensure_assets()
    build_cpp_backend()

def start() -> None:
    """
    @brief Khởi động FastAPI server chạy ngầm.
    @details Kiểm tra module, gọi tiến trình uvicorn qua `backend.server`, 
             chờ server khởi động thành công và tự động mở trình duyệt web.
    """
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
    """
    @brief Tắt tiến trình FastAPI server đang chạy ngầm.
    """
    terminate_process(APP_PID)
    print("Da tat web app.")


def status() -> None:
    """
    @brief Kiểm tra và in ra trạng thái hiện tại của web server (up/down).
    """
    print(f"APP: {'up' if http_ok(f'{APP_URL}/api/meta/boundary') else 'down'} ({APP_URL})")


def parse_args() -> argparse.Namespace:
    """
    @brief Phân tích các tham số dòng lệnh truyền vào.
    @return Không gian tên chứa các đối số (args.command).
    """
    parser = argparse.ArgumentParser(description="Cross-platform launcher for the Chicago route planner.")
    parser.add_argument(
        "command",
        nargs="?",
        default="start",
        choices=["start", "stop", "status", "setup"],
    )
    return parser.parse_args()


def main() -> int:
    """
    @brief Hàm điều phối chính (entry point) của script.
    @return Mã thoát (0 nếu thành công, 1 nếu có lỗi).
    """
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


# ==========================================
# KHỞI CHẠY CHƯƠNG TRÌNH
# ==========================================

if __name__ == "__main__":
    raise SystemExit(main())
