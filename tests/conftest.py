"""
@file <tên_file>.py
@brief Cấu hình đường dẫn hệ thống (sys.path) cho dự án.
@details Đoạn mã này tự động xác định thư mục gốc của dự án và thêm nó vào biến `sys.path`. 
         Điều này giúp Python có thể nhận diện và import các module từ các thư mục khác 
         trong cùng dự án một cách chính xác, bất kể script đang được chạy từ vị trí nào.
"""
from __future__ import annotations

import sys
from pathlib import Path

# ==========================================
# CẤU HÌNH ĐƯỜNG DẪN IMPORT MODULE
# ==========================================

# Xác định thư mục gốc của dự án (cách thư mục chứa file hiện tại 2 cấp)
ROOT = Path(__file__).resolve().parent.parent

# Kiểm tra xem thư mục gốc đã có trong danh sách đường dẫn tìm kiếm của Python chưa.
# Nếu chưa, thêm nó vào vị trí đầu tiên (index 0) để Python ưu tiên tìm kiếm module ở đây.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
