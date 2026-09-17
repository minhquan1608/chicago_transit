/**
 * @file Astar.cpp
 * @brief Triển khai thuật toán tìm đường A* và các tiện ích đồ thị.
 * @author Lê Phước Minh Quân & others
 * @date 2026-09-18
 * @details File chứa các hàm tính toán khoảng cách địa lý (Haversine), đọc dữ liệu 
 *          đồ thị từ file, xử lý logic chặn đường cấm và cốt lõi thuật toán A*.
 */

#include "Astar.h"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <limits>
#include <queue>
#include <utility>

using namespace std;

/**
 * @brief Tính khoảng cách đường chim bay giữa 2 tọa độ (kinh độ, vĩ độ).
 * @details Sử dụng công thức Haversine để bù đắp độ cong của Trái Đất.
 * 
 * @param lat1 Vĩ độ điểm 1 (độ).
 * @param lon1 Kinh độ điểm 1 (độ).
 * @param lat2 Vĩ độ điểm 2 (độ).
 * @param lon2 Kinh độ điểm 2 (độ).
 * @return Khoảng cách tính bằng mét (m).
 */
double haversine(double lat1, double lon1, double lat2, double lon2) {
  const double R = 6371000.0; // meters
  double p1 = lat1 * M_PI / 180.0;
  double p2 = lat2 * M_PI / 180.0;
  double dp = (lat2 - lat1) * M_PI / 180.0;
  double dl = (lon2 - lon1) * M_PI / 180.0;

  double a =
      sin(dp / 2) * sin(dp / 2) + cos(p1) * cos(p2) * sin(dl / 2) * sin(dl / 2);
  double c = 2 * atan2(sqrt(a), sqrt(1 - a));

  return R * c;
}

/**
 * @brief Tải dữ liệu đồ thị (Graph) từ file txt/csv.
 * @details Đọc số lượng node, edge và thiết lập danh sách kề (adj).
 * 
 * @param filename Đường dẫn tới file chứa đồ thị (ví dụ: data_graph.txt).
 * @return true nếu đọc file thành công, false nếu file lỗi.
 */
bool Graph::loadFromFile(const string &filename) {
  ifstream infile(filename);
  if (!infile.is_open())
    return false;

  int num_nodes, num_edges;
  if (!(infile >> num_nodes >> num_edges))
    return false;

  nodes.resize(num_nodes);
  adj.resize(num_nodes);

  for (int i = 0; i < num_nodes; ++i) {
    int id;
    double lat, lon;
    infile >> id >> lat >> lon;
    nodes[id] = {id, lat, lon};
  }

  for (int i = 0; i < num_edges; ++i) {
    int u, v;
    double dist, time;
    int type;
    infile >> u >> v >> dist >> time >> type;
    adj[u].push_back({v, dist, time, type});
  }

  infile.close();
  return true;
}

/**
 * @brief Tìm Node (đỉnh) gần nhất trên đồ thị so với một tọa độ bất kỳ.
 * @details Lặp qua toàn bộ nodes và dùng hàm haversine để đo khoảng cách.
 * 
 * @param lat Vĩ độ của điểm cần tìm.
 * @param lon Kinh độ của điểm cần tìm.
 * @return ID của Node gần nhất. Trả về -1 nếu đồ thị rỗng.
 */
int Graph::findNearestNode(double lat, double lon) const {
  int best_id = -1;
  double min_dist = numeric_limits<double>::infinity();
  for (const auto &node : nodes) {
    double d = haversine(lat, lon, node.lat, node.lon);
    if (d < min_dist) {
      min_dist = d;
      best_id = node.id;
    }
  }
  return best_id;
}

/**
 * @brief Tính khoảng cách ngắn nhất từ một điểm P đến một đoạn thẳng AB (segment).
 * @details Sử dụng phép chiếu vector phẳng (xấp xỉ khoảng cách nhỏ trên bề mặt cầu).
 * 
 * @param p_lat Vĩ độ điểm P.
 * @param p_lon Kinh độ điểm P.
 * @param a_lat Vĩ độ điểm A (đầu đoạn thẳng).
 * @param a_lon Kinh độ điểm A.
 * @param b_lat Vĩ độ điểm B (cuối đoạn thẳng).
 * @param b_lon Kinh độ điểm B.
 * @return Khoảng cách ngắn nhất tính bằng mét.
 */
double distanceToSegment(double p_lat, double p_lon, double a_lat, double a_lon,
                         double b_lat, double b_lon) {
  double R = 6371000.0;
  double lat_rad = a_lat * M_PI / 180.0;

  double px = (p_lon - a_lon) * M_PI / 180.0 * R * cos(lat_rad);
  double py = (p_lat - a_lat) * M_PI / 180.0 * R;

  double bx = (b_lon - a_lon) * M_PI / 180.0 * R * cos(lat_rad);
  double by = (b_lat - a_lat) * M_PI / 180.0 * R;

  double l2 = bx * bx + by * by;
  if (l2 == 0)
    return sqrt(px * px + py * py);

  double t = max(0.0, min(1.0, (px * bx + py * by) / l2));
  double proj_x = t * bx;
  double proj_y = t * by;

  double dx = px - proj_x;
  double dy = py - proj_y;

  return sqrt(dx * dx + dy * dy);
}

/**
 * @brief Gắn cờ (chặn) các node nằm trong vùng ảnh hưởng của các đoạn đường cấm.
 * @details Những node bị gắn cờ true trong blocked_nodes sẽ bị A* bỏ qua.
 * 
 * @param segments Danh sách các đoạn đường cấm (chứa tọa độ 2 đầu và bán kính buffer).
 */
void Graph::applyBlockedSegments(const vector<BlockedSegment> &segments) {
  blocked_nodes.assign(nodes.size(), false);
  for (const auto &node : nodes) {
    for (const auto &seg : segments) {
      double d = distanceToSegment(node.lat, node.lon, seg.lat1, seg.lon1,
                                   seg.lat2, seg.lon2);
      if (d <= seg.buffer_m) {
        blocked_nodes[node.id] = true;
        break;
      }
    }
  }
}

/**
 * @struct State
 * @brief Trạng thái duyệt của thuật toán A*.
 */
struct State {
  int u;         ///< ID của Node hiện tại
  double g;      ///< Chi phí thực tế (thời gian) đi từ Start đến u
  double f;      ///< Tổng chi phí ước lượng (f = g + h)
  bool operator>(const State &other) const { return f > other.f; }
};

/**
 * @struct ParentData
 * @brief Lưu trữ thông tin Node cha (traceback) để phục dựng lộ trình.
 */
struct ParentData {
  int u;         ///< ID của Node cha
  int type;      ///< Loại đường di chuyển (đi bộ, tàu)
  double dist;   ///< Khoảng cách từ Node cha đến Node hiện tại
};

/**
 * @brief Triển khai thuật toán A* (A-Star) để tìm đường đi ngắn nhất (về thời gian).
 * 
 * @param graph Đối tượng Graph (chứa nodes, adj, và danh sách node bị chặn).
 * @param start ID của Node bắt đầu.
 * @param target ID của Node đích.
 * @return AStarResult chứa lộ trình (path), tổng thời gian và tổng khoảng cách.
 */
AStarResult findPathAStar(const Graph &graph, int start, int target) {
  AStarResult res;
  res.found = false;
  res.total_distance = 0;
  res.total_time = 0;

  // Kiểm tra tính hợp lệ của điểm đầu/đích
  if (start < 0 || start >= (int)graph.nodes.size() || target < 0 ||
      target >= (int)graph.nodes.size()) {
    return res;
  }

  int n = (int)graph.nodes.size();
  vector<double> g_time(n, numeric_limits<double>::infinity());
  vector<ParentData> parent(n, {-1, -1, 0.0});

  // Hàng đợi ưu tiên (Min-Heap) để duyệt các node có chi phí f nhỏ nhất
  priority_queue<State, vector<State>, greater<State>> pq;

  g_time[start] = 0;
  // Hàm Heuristic: Khoảng cách đường chim bay chia cho vận tốc tối đa dự kiến (~15m/s)
  double h_start = haversine(graph.nodes[start].lat, graph.nodes[start].lon,
                             graph.nodes[target].lat, graph.nodes[target].lon) /
                   15.0;
  pq.push({start, 0, h_start});

  while (!pq.empty()) {
    State current = pq.top();
    pq.pop();

    int u = current.u;

    // Đã đến đích, bắt đầu truy xuất ngược lộ trình (traceback)
    if (u == target) {
      res.found = true;
      res.total_time = g_time[u];

      int curr = target;
      while (curr != -1) {
        ParentData p = parent[curr];
        res.path.push_back({curr, p.type, p.dist});
        if (p.type != -1) {
          res.total_distance += p.dist;
        }
        curr = p.u;
      }
      // Đảo ngược mảng vì traceback đi từ Đích về Start
      for (int i = 0; i < (int)res.path.size() / 2; ++i) {
        swap(res.path[i], res.path[(int)res.path.size() - 1 - i]);
      }
      return res;
    }

    if (current.g > g_time[u])
      continue;

    // Duyệt qua các hàng xóm của node hiện tại
    for (const auto &edge : graph.adj[u]) {
      int v = edge.to;
      // Bỏ qua nếu node bị khóa do rơi vào đoạn đường cấm
      if ((int)graph.blocked_nodes.size() > v && graph.blocked_nodes[v])
        continue;

      double time_cost = edge.time;
      // Cập nhật đường đi ngắn hơn
      if (g_time[u] + time_cost < g_time[v]) {
        g_time[v] = g_time[u] + time_cost;
        parent[v] = {u, edge.type, edge.distance};
        double h = haversine(graph.nodes[v].lat, graph.nodes[v].lon,
                             graph.nodes[target].lat, graph.nodes[target].lon) /
                   15.0;
        pq.push({v, g_time[v], g_time[v] + h});
      }
    }
  }

  return res;
}
