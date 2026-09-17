/**
 * @file GA.h
 * @brief Khai báo cấu trúc và hàm cho Giải thuật Di truyền (Genetic Algorithm).
 * @author Lê Phước Minh Quân & others
 * @date 2026-09-18
 * @details File header này định nghĩa cấu trúc của một cá thể (Individual) đại diện cho 
 *          một phương án định tuyến, cùng với khai báo hàm cốt lõi để giải quyết bài toán 
 *          Người chào hàng (TSP) nhằm tối ưu hóa thứ tự các điểm dừng.
 */

#pragma once

#include <vector>

/**
 * @struct Individual
 * @brief Đại diện cho một cá thể trong quần thể của giải thuật di truyền.
 */
struct Individual {
    std::vector<int> gene; ///< Chuỗi gene biểu diễn thứ tự đi qua các điểm dừng (ví dụ: {0, 2, 1})
    double fitness;        ///< Độ thích nghi của cá thể (tổng thời gian di chuyển, trị số càng nhỏ càng tốt)
};

/**
 * @brief Tìm thứ tự đi qua các điểm dừng tối ưu nhất bằng Giải thuật Di truyền (GA).
 * @details Hàm tiếp nhận một ma trận thời gian (kích thước N_all x N_all). 
 *          Quy ước chỉ số (index) trong ma trận:
 *          - Index 0: Điểm xuất phát (Start).
 *          - Index 1 đến num_stops: Các điểm dừng trung gian (Stops).
 *          - Index N_all - 1: Điểm đích đến (Target).
 * 
 * @param timeMatrix Ma trận chi phí (thời gian di chuyển) giữa tất cả các điểm (Start, Stops, Target).
 * @param num_stops Số lượng điểm dừng trung gian cần đi qua.
 * @param numGenerations Số lượng thế hệ tiến hóa tối đa của thuật toán (mặc định = 100).
 * @param popSize Kích thước quần thể (số lượng cá thể duy trì trong mỗi thế hệ, mặc định = 50).
 * @return std::vector<int> Mảng hoán vị chứa các chỉ số (từ 0 đến num_stops - 1) 
 *         đại diện cho thứ tự tối ưu nhất để đi qua toàn bộ các điểm dừng.
 */
std::vector<int> solveTSP_GA(const std::vector<std::vector<double>>& timeMatrix, int num_stops, int numGenerations = 100, int popSize = 50);
