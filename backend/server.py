"""
@file run.py
@brief Điểm khởi chạy (Entry Point) của máy chủ Backend Chicago Route Planner.
@author Lê Phước Minh Quân & others
@date 2026-09-18
@details File script này chịu trách nhiệm khởi động ứng dụng FastAPI. Nó tự động tải 
         các tham số cấu hình (như cổng - port) từ biến môi trường và gọi Uvicorn 
         để phục vụ (serve) các API endpoint cho Frontend.
"""

from __future__ import annotations

import os
import sys

from backend.api.config import Settings


def main() -> None:
    """
    @brief Khởi chạy máy chủ Uvicorn thông qua lệnh hệ thống.
    @details Hàm này đọc cấu hình hệ thống (Settings), sau đó sử dụng `os.execv` để 
             thay thế hoàn toàn tiến trình Python hiện tại bằng tiến trình Uvicorn. 
             Việc này giúp tối ưu tài nguyên và đảm bảo server chạy trên `0.0.0.0` 
             với cổng (port) được chỉ định trong cấu hình.
    """
    settings = Settings.from_env()
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.api.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(settings.serve_port),
        ],
    )


if __name__ == "__main__":
    main()
