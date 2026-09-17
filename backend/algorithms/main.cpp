/**
 * @file main.cpp
 * @brief Tệp thực thi chính (Entry Point) của phần lõi thuật toán định tuyến Chicago Transit.
 * @author Lê Phước Minh Quân & others
 * @date 2026-09-18
 * @details File xử lý đầu vào từ `stdin` do backend truyền tới, sau đó sử dụng thuật toán A* 
 *          kết hợp với Giải thuật Di truyền (GA) để tìm ra lộ trình đi qua các trạm (điểm dừng) 
 *          tối ưu nhất, và cuối cùng trả về kết quả dạng chuỗi JSON thông qua `stdout`.
 */

#include "Astar.h"
#include "GA.h"
#include <algorithm>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

using namespace std;

/**
 * @brief Hàm chính thực thi chương trình.
 * @param argc Số lượng tham số dòng lệnh.
 * @param argv Mảng các tham số dòng lệnh (argv[1] chứa đường dẫn file đồ thị).
 * @return 0 nếu chạy thành công, 1 nếu có lỗi.
 */
int main(int argc, char **argv) {
  // 1. Kiểm tra đối số đầu vào (phải truyền đường dẫn file đồ thị)
  if (argc < 2) {
    cerr << "Usage: " << argv[0] << " <graph_file>" << endl;
    return 1;
  }

  // 2. Khởi tạo đồ thị và load dữ liệu từ file
  Graph graph;
  if (!graph.loadFromFile(argv[1])) {
    cerr << "Failed to load graph from " << argv[1] << endl;
    return 1;
  }

  // ==========================================
  // ĐỌC THAM SỐ TỪ STDIN (Do Backend truyền vào)
  // ==========================================

  // 3. Đọc tọa độ điểm đầu (S) và điểm đích (T)
  double s_lat, s_lon, t_lat, t_lon;
  if (!(cin >> s_lat >> s_lon >> t_lat >> t_lon))
    return 0;

  // 4. Đọc số lượng điểm dừng trung gian (Stops) và tọa độ của chúng
  int num_stops;
  if (!(cin >> num_stops))
    return 0;

  vector<pair<double, double>> stops(num_stops);
  for (int i = 0; i < num_stops; ++i) {
    cin >> stops[i].first >> stops[i].second;
  }

  // 5. Đọc cờ tối ưu hóa (0 = giữ nguyên thứ tự, 1 = tối ưu hóa)
  int optimize_flag;
  if (!(cin >> optimize_flag))
    return 0;

  // 6. Đọc số lượng và thông tin các đoạn đường cấm (Blocked Segments)
  int num_blocked;
  if (!(cin >> num_blocked))
    return 0;

  vector<BlockedSegment> blocked_segments(num_blocked);
  for (int i = 0; i < num_blocked; ++i) {
    cin >> blocked_segments[i].lat1 >> blocked_segments[i].lon1 >>
        blocked_segments[i].lat2 >> blocked_segments[i].lon2 >>
        blocked_segments[i].buffer_m;
  }
  
  // Áp dụng các đoạn cấm vào cấu trúc đồ thị
  graph.applyBlockedSegments(blocked_segments);

  // ==========================================
  // TIẾN HÀNH ĐỊNH TUYẾN
  // ==========================================

  // Ánh xạ tọa độ người dùng nhập vào các Node thực tế trên đồ thị
  int start_node = graph.findNearestNode(s_lat, s_lon);
  int target_node = graph.findNearestNode(t_lat, t_lon);

  if (start_node == -1 || target_node == -1) {
    cout << "{\"error\": \"Could not find nearest nodes.\"}" << endl;
    return 0;
  }

  // Trường hợp 1: Định tuyến thẳng (Không có điểm dừng)
  if (num_stops == 0) {
    AStarResult res = findPathAStar(graph, start_node, target_node);
    if (!res.found) {
      cout << "{\"error\": \"Path not found.\"}" << endl;
      return 0;
    }

    // Trả về JSON cho Python Backend phân tích
    cout << "{\"total_time\": " << res.total_time
         << ", \"total_distance\": " << res.total_distance << ", \"path\": [";
    for (size_t i = 0; i < res.path.size(); ++i) {
      const auto &step = res.path[i];
      const auto &node = graph.nodes[step.node_id];
      cout << "{\"lat\": " << node.lat << ", \"lon\": " << node.lon
           << ", \"type\": " << step.type_from_prev << "}";
      if (i < res.path.size() - 1)
        cout << ",";
    }
    cout << "]}" << endl;
    return 0;
  }

  // Trường hợp 2: Định tuyến đa điểm (Có điểm dừng trung gian)
  vector<int> stop_nodes(num_stops);
  for (int i = 0; i < num_stops; ++i) {
    stop_nodes[i] = graph.findNearestNode(stops[i].first, stops[i].second);
  }

  // Tập hợp toàn bộ các điểm cần đi qua: [Start, Stop_1...N, Target]
  vector<int> all_nodes = {start_node};
  for (int s : stop_nodes)
    all_nodes.push_back(s);
  all_nodes.push_back(target_node);

  int n_all = (int)all_nodes.size();
  
  // Tính toán trước tất cả các đường đi ngắn nhất giữa từng cặp điểm (All-Pairs) bằng A*
  vector<vector<AStarResult>> allPairs(n_all, vector<AStarResult>(n_all));
  for (int i = 0; i < n_all; ++i) {
    for (int j = 0; j < n_all; ++j) {
      if (i == j) {
        allPairs[i][j].total_time = 0;
        allPairs[i][j].total_distance = 0;
        allPairs[i][j].path = {{all_nodes[i], -1, 0.0}};
      } else {
        allPairs[i][j] = findPathAStar(graph, all_nodes[i], all_nodes[j]);
      }
    }
  }

  vector<int> best_order;
  double best_cost = numeric_limits<double>::infinity();

  // ==========================================
  // XÁC ĐỊNH THỨ TỰ ĐIỂM DỪNG TỐI ƯU (TSP)
  // ==========================================

  if (optimize_flag == 0) {
    // 2.a - Không tối ưu: Giữ nguyên thứ tự người dùng nhập vào
    best_order.resize(num_stops);
    for(int i=0; i<num_stops; ++i) best_order[i] = i;
    
    best_cost = allPairs[0][best_order[0] + 1].total_time;
    for (int i = 0; i < num_stops - 1; ++i) {
      best_cost += allPairs[best_order[i] + 1][best_order[i + 1] + 1].total_time;
    }
    best_cost += allPairs[best_order[num_stops - 1] + 1][n_all - 1].total_time;
  } else if (num_stops <= 8) {
    // 2.b - Tối ưu Exact (Brute Force / Duyệt hoán vị): Dành cho số lượng điểm nhỏ (<= 8)
    vector<int> perm(num_stops);
    for (int i = 0; i < num_stops; ++i)
      perm[i] = i;
    do {
      double cost = allPairs[0][perm[0] + 1].total_time;
      for (int i = 0; i < num_stops - 1; ++i) {
        cost += allPairs[perm[i] + 1][perm[i + 1] + 1].total_time;
      }
      cost += allPairs[perm[num_stops - 1] + 1][n_all - 1].total_time;

      if (cost < best_cost) {
        best_cost = cost;
        best_order = perm;
      }
    } while (next_permutation(perm.begin(), perm.end()));
  } else {
    // 2.c - Tối ưu bằng Giải thuật Di truyền (GA Fallback): Khi số lượng điểm dừng lớn (> 8)
    // Chuyển đổi dữ liệu sang dạng ma trận thời gian cho GA
    vector<vector<double>> timeMatrix(n_all, vector<double>(n_all, 0.0));
    for (int i = 0; i < n_all; ++i) {
        for (int j = 0; j < n_all; ++j) {
            timeMatrix[i][j] = allPairs[i][j].total_time;
        }
    }
    // Gọi thuật toán GA để tìm chuỗi gene (thứ tự) tối ưu nhất
    best_order = solveTSP_GA(timeMatrix, num_stops, 100, 50);
    
    // Tính toán lại tổng thời gian theo thứ tự best_order
    best_cost = allPairs[0][best_order[0] + 1].total_time;
    for (int i = 0; i < num_stops - 1; ++i) {
      best_cost +=
          allPairs[best_order[i] + 1][best_order[i + 1] + 1].total_time;
    }
    best_cost += allPairs[best_order[num_stops - 1] + 1][n_all - 1].total_time;
  }

  // ==========================================
  // XÂY DỰNG LẠI LỘ TRÌNH HOÀN CHỈNH VÀ XUẤT RA JSON
  // ==========================================

  // Tính tổng quãng đường của lộ trình đã khâu ghép
  double total_distance = 0;
  total_distance += allPairs[0][best_order[0] + 1].total_distance;
  for (int i = 0; i < num_stops - 1; ++i) {
    total_distance +=
        allPairs[best_order[i] + 1][best_order[i + 1] + 1].total_distance;
  }
  total_distance +=
      allPairs[best_order[num_stops - 1] + 1][n_all - 1].total_distance;

  // Xuất các thông tin tổng quan (thời gian, quãng đường, thứ tự điểm dừng)
  cout << "{\"total_time\": " << best_cost
       << ", \"total_distance\": " << total_distance 
       << ", \"stop_order_indices\": [";
  for (size_t i = 0; i < best_order.size(); ++i) {
      cout << best_order[i];
      if (i < best_order.size() - 1) cout << ",";
  }
  cout << "], \"path\": [";

  // Khâu (stitch) các đoạn đường con lại với nhau thành một mảng hoàn chỉnh
  vector<PathStep> full_path;
  int curr = 0; // Bắt đầu từ Start
  for (int stop_idx : best_order) {
    int nxt = stop_idx + 1;
    auto p = allPairs[curr][nxt].path;
    if (full_path.empty())
      full_path = p;
    else
      // Bỏ qua điểm đầu tiên của đoạn nối tiếp để tránh trùng lặp điểm
      full_path.insert(full_path.end(), p.begin() + 1, p.end());
    curr = nxt;
  }
  
  // Nối đoạn cuối cùng (từ điểm dừng cuối đến đích)
  auto p_end = allPairs[curr][n_all - 1].path;
  if (full_path.empty())
    full_path = p_end;
  else
    full_path.insert(full_path.end(), p_end.begin() + 1, p_end.end());

  // In các mảng điểm (coordinates) của lộ trình hoàn chỉnh
  for (size_t i = 0; i < full_path.size(); ++i) {
    const auto &step = full_path[i];
    const auto &node = graph.nodes[step.node_id];
    cout << "{\"lat\": " << node.lat << ", \"lon\": " << node.lon
         << ", \"type\": " << step.type_from_prev << "}";
    if (i < full_path.size() - 1)
      cout << ",";
  }
  cout << "]}" << endl;

  return 0;
}
