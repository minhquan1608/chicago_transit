/**
 * @file Astar.h
 * @brief Định nghĩa cấu trúc dữ liệu đồ thị và khai báo thuật toán tìm đường A*.
 * @author Lê Phước Minh Quân & others
 * @date 2026-09-18
 * @details File header này chứa các định nghĩa (struct/class) cần thiết để mô phỏng 
 *          mạng lưới giao thông Chicago (CTA), cùng với khai báo hàm tìm đường A*.
 */

#pragma once

#include <vector>
#include <string>
#include <unordered_map>

/**
 * @struct Node
 * @brief Đại diện cho một đỉnh (trạm/nút giao) trên đồ thị.
 */
struct Node {
    int id;       ///< ID định danh duy nhất của Node
    double lat;   ///< Vĩ độ (Latitude)
    double lon;   ///< Kinh độ (Longitude)
};

/**
 * @struct Edge
 * @brief Đại diện cho một cạnh (tuyến đường) kết nối giữa các Node.
 */
struct Edge {
    int to;          ///< ID của Node đích đến
    double distance; ///< Khoảng cách vật lý (mét)
    double time;     ///< Thời gian di chuyển dự kiến (giây)
    int type;        ///< Phương tiện di chuyển: 0 = đi bộ, 1 = tàu (rail CTA)
};

/**
 * @struct PathStep
 * @brief Lưu trữ thông tin từng bước di chuyển trong kết quả lộ trình.
 */
struct PathStep {
    int node_id;            ///< ID của Node tại bước này
    int type_from_prev;     ///< Loại phương tiện từ Node trước đến Node này (-1 nếu là điểm xuất phát)
    double dist_from_prev;  ///< Khoảng cách từ Node trước đến Node này (mét)
};

/**
 * @struct AStarResult
 * @brief Cấu trúc chứa toàn bộ kết quả trả về của thuật toán A*.
 */
struct AStarResult {
    bool found;                     ///< Trạng thái: true nếu tìm thấy đường, false nếu không
    double total_distance;          ///< Tổng quãng đường của lộ trình (mét)
    double total_time;              ///< Tổng thời gian của lộ trình (giây)
    std::vector<PathStep> path;     ///< Danh sách các đỉnh và thông tin từng chặng đi qua
};

/**
 * @struct BlockedSegment
 * @brief Mô tả một đoạn đường bị cấm/phong tỏa trên bản đồ.
 */
struct BlockedSegment {
    double lat1, lon1;  ///< Tọa độ điểm bắt đầu đoạn cấm
    double lat2, lon2;  ///< Tọa độ điểm kết thúc đoạn cấm
    double buffer_m;    ///< Bán kính (bề rộng) ảnh hưởng của đoạn cấm tính bằng mét
};

/**
 * @class Graph
 * @brief Lớp quản lý cấu trúc đồ thị mạng lưới giao thông.
 */
class Graph {
public:
    std::vector<Node> nodes;                    ///< Danh sách toàn bộ các đỉnh trong hệ thống
    std::vector<std::vector<Edge>> adj;         ///< Danh sách kề biểu diễn các cạnh của đồ thị
    std::vector<bool> blocked_nodes;            ///< Mảng đánh dấu các đỉnh đang bị cấm đi qua

    /**
     * @brief Đọc dữ liệu đồ thị từ file văn bản.
     * @param filename Đường dẫn file dữ liệu đồ thị (vd: data_graph.txt).
     * @return true nếu load file thành công, ngược lại false.
     */
    bool loadFromFile(const std::string& filename);

    /**
     * @brief Tìm ID của Node gần với tọa độ địa lý cho trước nhất.
     * @param lat Vĩ độ.
     * @param lon Kinh độ.
     * @return ID của đỉnh gần nhất. Trả về -1 nếu đồ thị rỗng.
     */
    int findNearestNode(double lat, double lon) const;

    /**
     * @brief Đánh dấu chặn các Node nằm trong vùng ảnh hưởng của danh sách đường cấm.
     * @param segments Danh sách cấu trúc đoạn đường cấm (BlockedSegment).
     */
    void applyBlockedSegments(const std::vector<BlockedSegment>& segments);
};

/**
 * @brief Thuật toán A* cốt lõi để tìm đường đi ngắn nhất (tối ưu theo thời gian).
 * @param graph Đối tượng đồ thị đang xét.
 * @param start ID của đỉnh bắt đầu.
 * @param target ID của đỉnh đích.
 * @return Kết quả lộ trình dưới dạng đối tượng AStarResult.
 */
AStarResult findPathAStar(const Graph& graph, int start, int target);
