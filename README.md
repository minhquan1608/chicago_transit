# 🚇 Chicago Route Planner

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/C%2B%2B-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white" alt="C++">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Algorithm-A*_%7C_GA-blue?style=for-the-badge" alt="Algorithms">
</p>

## 📖 Mô tả dự án
**Chicago Route Planner** là ứng dụng bản đồ tương tác hướng dẫn chỉ đường tại khu vực thành phố Chicago. Hệ thống kết hợp định tuyến di chuyển đi bộ và mạng lưới tàu điện của Chicago Transit Authority (CTA). Dự án là sự kết hợp giữa lõi thuật toán C++ hiệu năng cao và giao diện Web trực quan nhằm giải quyết các bài toán giao thông thực tế.

## ✨ Các Tính năng Chính
- **Định tuyến linh hoạt:** Tìm đường đi bộ và đi qua mạng lưới tàu điện CTA một cách liền mạch.
- **Tối ưu hóa đa điểm (Multi-stops):** Khả năng chọn nhiều điểm dừng trên lộ trình. Hệ thống sử dụng giải thuật Di truyền (Genetic Algorithm - GA) để sắp xếp thứ tự các điểm dừng sao cho tổng chi phí di chuyển là thấp nhất.
- **Thích ứng rủi ro theo thời gian thực:** Tự động cảnh báo ngập lụt cục bộ hoặc kẹt xe, từ đó cộng thêm thời gian phạt (penalty time) vào quá trình tính toán để đưa ra lộ trình an toàn hơn.
- **Tùy biến chướng ngại vật:** Tính năng tương tác cao cho phép người dùng **vẽ trực tiếp đoạn đường cấm/đang thi công** trên bản đồ. Hệ thống lập tức nhận diện và tự động tìm đường vòng (rerouting).

## 🧠 Kiến trúc Hệ thống & Thuật toán
Dự án được thiết kế theo mô hình client-server, chia thành 2 thành phần chính:

1. **Frontend (`frontend/`):** Giao diện web được xây dựng bằng HTML/JS/CSS, cung cấp bản đồ trực quan để người dùng thao tác (chọn điểm, vẽ đường cấm, xem lộ trình).
2. **Backend (`backend/`):** Web server triển khai bằng **FastAPI**, làm nhiệm vụ tiếp nhận yêu cầu, xử lý logic và giao tiếp với lõi thuật toán C++.
   - **Thuật toán A* (A-Star):** Đảm nhiệm việc tìm đường đi ngắn nhất giữa các điểm, sử dụng hàm Heuristic để tối ưu tốc độ so với các thuật toán truyền thống.
   - **Giải thuật Di truyền (GA):** Giải quyết bài toán người chào hàng (TSP) khi lộ trình có nhiều điểm dừng phức tạp.

### Cấu trúc thư mục
```text
chicago_transit/
├── frontend/               # Giao diện web (HTML/JS/CSS)
├── backend/                # Toàn bộ mã nguồn xử lý
│   ├── api/                # FastAPI (Controllers, Models, Services)
│   ├── algorithms/         # Mã nguồn thuật toán C++ (Astar, GA, main)
│   ├── scripts/            # Các tập lệnh (Build đồ thị từ bản đồ thực tế)
│   └── server.py           # File chạy web server Uvicorn
├── data/                   # Chứa file đồ thị (.txt) và dữ liệu tĩnh (.json)
├── run.py                  # Lệnh khởi động chung
└── requirements.txt        # Các thư viện Python cần thiết
```

## 🚀 Hướng dẫn Cài đặt & Khởi chạy

### 1. Yêu cầu hệ thống và Cài đặt thư viện
Máy tính của bạn cần được cài sẵn **Python 3** và trình biên dịch **C++** (như `g++` hoặc `clang++` - thường có sẵn trên macOS/Linux hoặc MinGW trên Windows).

Mở Terminal/Command Prompt và cài đặt các thư viện Python cần thiết:

```bash
pip install -r requirements.txt
pip install osmnx networkx  # Dùng để trích xuất đồ thị ban đầu từ OpenStreetMap
```

### 2. Biên dịch C++ và Khởi tạo Đồ thị (Chỉ chạy 1 lần duy nhất)
Để hệ thống tự động tải dữ liệu bản đồ Chicago, trích xuất cấu trúc đồ thị (lưu tại `data_graph.txt`) và biên dịch lõi thuật toán C++, hãy chạy lệnh sau:

```bash
python run.py setup
```
*(Lưu ý: Quá trình trích xuất đồ thị bằng OSMnx có thể mất khoảng 1-2 phút tùy thuộc vào tốc độ mạng của bạn).*

### 3. Khởi động ứng dụng (Sử dụng hằng ngày)
Khởi động máy chủ web bằng lệnh:

```bash
python run.py start
```
Mở trình duyệt web và truy cập địa chỉ: **`http://127.0.0.1:8000`** để bắt đầu sử dụng bản đồ.

## 👨‍💻 Tác giả
- **Lê Phước Minh Quân** - Sinh viên chuyên ngành Khoa học Máy tính (K69), Đại học Bách khoa Hà Nội và các thành viên khác
- **Email:** minhquan160806@gmail.com
- **Github:** [@minhquan1608](https://github.com/minhquan1608)
