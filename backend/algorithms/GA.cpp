/**
 * @file GA.cpp
 * @brief Triển khai Giải thuật Di truyền (Genetic Algorithm) để giải quyết bài toán định tuyến đa điểm (TSP).
 * @author Lê Phước Minh Quân & others
 * @date 2026-09-18
 * @details File này chứa các hàm lai ghép (Crossover), đột biến (Mutation) và 
 *          hàm đánh giá (Fitness) để tìm ra thứ tự tối ưu khi đi qua nhiều điểm dừng.
 */

#include "GA.h"
#include <algorithm>
#include <random>
#include <iostream>

using namespace std;

/**
 * @brief Tính toán độ thích nghi (fitness) của một cá thể (individual).
 * @details Độ thích nghi ở đây là tổng thời gian di chuyển đi từ điểm xuất phát (S),
 *          đi qua tất cả các điểm dừng theo thứ tự của gene, và kết thúc tại điểm đích (T).
 * 
 * @param gene Một hoán vị các điểm dừng trung gian (ví dụ: {0, 2, 1}).
 * @param timeMatrix Ma trận chi phí thời gian di chuyển giữa tất cả các điểm {S, Stop_1...N, T}.
 * @return Tổng thời gian di chuyển (giây). Trị số càng nhỏ, cá thể càng ưu tú.
 */
double computeFitness(const vector<int>& gene, const vector<vector<double>>& timeMatrix) {
    if (gene.empty()) return 0.0;
    int n_all = (int)timeMatrix.size();
    int target_idx = n_all - 1;
    
    double totalTime = 0;
    // Điểm xuất phát (S) -> Điểm dừng đầu tiên trong chuỗi gene
    totalTime += timeMatrix[0][gene[0] + 1];
    
    // Tổng thời gian đi qua các điểm dừng theo thứ tự
    for (size_t i = 0; i < gene.size() - 1; ++i) {
        totalTime += timeMatrix[gene[i] + 1][gene[i+1] + 1];
    }
    
    // Điểm dừng cuối cùng trong chuỗi gene -> Điểm đích (T)
    totalTime += timeMatrix[gene.back() + 1][target_idx];
    
    return totalTime;
}

/**
 * @brief Thực hiện phép lai ghép theo thứ tự (Order Crossover - OX) giữa 2 cá thể cha mẹ.
 * @details Phép lai OX chọn ngẫu nhiên một đoạn gene từ cha/mẹ 1 và giữ nguyên vị trí, 
 *          các gene còn lại được điền từ cha/mẹ 2 theo thứ tự xuất hiện để đảm bảo không 
 *          có điểm dừng nào bị lặp lại hoặc bỏ sót.
 * 
 * @param p1 Cá thể cha/mẹ 1.
 * @param p2 Cá thể cha/mẹ 2.
 * @param rng Bộ sinh số ngẫu nhiên (Mersenne Twister).
 * @return Cá thể con (child) mang đặc tính của cả p1 và p2.
 */
Individual crossoverOX(const Individual& p1, const Individual& p2, mt19937& rng) {
    int n = p1.gene.size();
    Individual child;
    child.gene.assign(n, -1);
    
    if (n <= 1) {
        child.gene = p1.gene;
        return child;
    }

    uniform_int_distribution<int> dist(0, n - 1);
    int start = dist(rng);
    int end = dist(rng);
    if (start > end) swap(start, end);

    vector<bool> inChild(n, false);
    // Copy trực tiếp dải con từ p1 sang child
    for (int i = start; i <= end; ++i) {
        child.gene[i] = p1.gene[i];
        inChild[child.gene[i]] = true;
    }

    // Điền các gene còn thiếu từ p2
    int p2Idx = 0;
    for (int i = 0; i < n; ++i) {
        if (child.gene[i] == -1) {
            while (inChild[p2.gene[p2Idx]]) {
                p2Idx++;
            }
            child.gene[i] = p2.gene[p2Idx];
            inChild[p2.gene[p2Idx]] = true;
        }
    }
    
    return child;
}

/**
 * @brief Thực hiện phép đột biến đổi chỗ (Swap Mutation) trên một cá thể.
 * @details Hoán đổi vị trí của 2 điểm dừng ngẫu nhiên trong chuỗi gene dựa trên xác suất mutationRate.
 *          Giúp duy trì sự đa dạng của quần thể và ngăn thuật toán bị kẹt ở cực tiểu cục bộ.
 * 
 * @param ind Cá thể cần đột biến (sẽ bị thay đổi trực tiếp).
 * @param mutationRate Tỷ lệ/xác suất xảy ra đột biến trên mỗi gene.
 * @param rng Bộ sinh số ngẫu nhiên (Mersenne Twister).
 */
void mutate(Individual& ind, double mutationRate, mt19937& rng) {
    int n = ind.gene.size();
    if (n <= 1) return;
    uniform_real_distribution<double> realDist(0.0, 1.0);
    uniform_int_distribution<int> intDist(0, n - 1);

    for (int i = 0; i < n; ++i) {
        if (realDist(rng) < mutationRate) {
            int j = intDist(rng);
            swap(ind.gene[i], ind.gene[j]);
        }
    }
}

/**
 * @brief Khởi chạy thuật toán Di truyền để giải bài toán Người chào hàng (TSP).
 * @details Quần thể ban đầu được tạo ngẫu nhiên, sau đó trải qua quá trình đánh giá độ thích nghi,
 *          chọn lọc tinh anh (Elitism), lai ghép (OX) và đột biến (Swap) qua nhiều thế hệ 
 *          để tìm ra thứ tự đi qua các điểm dừng tốn ít thời gian nhất.
 * 
 * @param timeMatrix Ma trận chi phí thời gian giữa các điểm {S, Stop_1, ..., Stop_N, T}.
 * @param num_stops Số lượng điểm dừng trung gian.
 * @param numGenerations Số thế hệ tiến hóa (số vòng lặp tối đa).
 * @param popSize Kích thước quần thể (số lượng cá thể trong mỗi thế hệ).
 * @return vector<int> Chuỗi gene (thứ tự các điểm dừng) tối ưu nhất tìm được.
 */
vector<int> solveTSP_GA(const vector<vector<double>>& timeMatrix, int num_stops, int numGenerations, int popSize) {
    vector<int> bestSequence;
    
    // Nếu số lượng điểm dừng quá ít (<= 2), không cần dùng GA, trả về mảng tuần tự.
    if (num_stops <= 2) {
        for(int i=0; i<num_stops; ++i) bestSequence.push_back(i);
        return bestSequence;
    }

    random_device rd;
    mt19937 rng(rd());

    // Khởi tạo quần thể ngẫu nhiên
    vector<Individual> population(popSize);
    for (int i = 0; i < popSize; ++i) {
        population[i].gene.resize(num_stops);
        for (int j = 0; j < num_stops; ++j) population[i].gene[j] = j;
        shuffle(population[i].gene.begin(), population[i].gene.end(), rng);
        population[i].fitness = computeFitness(population[i].gene, timeMatrix);
    }

    double mutationRate = 0.1;

    // Vòng lặp tiến hóa
    for (int gen = 0; gen < numGenerations; ++gen) {
        // Sắp xếp quần thể theo độ thích nghi (fitness thấp nhất -> tốt nhất)
        sort(population.begin(), population.end(), [](const Individual& a, const Individual& b) {
            return a.fitness < b.fitness;
        });

        vector<Individual> newPop;
        
        // Phương pháp chọn lọc tinh anh (Elitism): Giữ lại 20% cá thể tốt nhất
        int eliteCount = max(1, popSize / 5);
        for (int i = 0; i < eliteCount; ++i) {
            newPop.push_back(population[i]);
        }

        // Lai ghép và đột biến để tạo ra các cá thể mới lấp đầy quần thể
        uniform_int_distribution<int> parentDist(0, popSize / 2);
        while ((int)newPop.size() < popSize) {
            Individual p1 = population[parentDist(rng)];
            Individual p2 = population[parentDist(rng)];
            Individual child = crossoverOX(p1, p2, rng);
            mutate(child, mutationRate, rng);
            child.fitness = computeFitness(child.gene, timeMatrix);
            newPop.push_back(child);
        }
        population = newPop;
    }

    // Đánh giá lần cuối để chọn ra cá thể tốt nhất sau toàn bộ quá trình tiến hóa
    sort(population.begin(), population.end(), [](const Individual& a, const Individual& b) {
        return a.fitness < b.fitness;
    });

    return population[0].gene;
}
