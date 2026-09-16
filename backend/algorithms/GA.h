#pragma once

#include <vector>

struct Individual {
    std::vector<int> gene; // Sequence of stops
    double fitness;
};

// Given a time matrix (N_all x N_all) where index 0 is Start, indices 1..num_stops are stops, and index N_all-1 is Target.
// returns the best permutation of stops (indices 0 to num_stops-1).
std::vector<int> solveTSP_GA(const std::vector<std::vector<double>>& timeMatrix, int num_stops, int numGenerations = 100, int popSize = 50);
