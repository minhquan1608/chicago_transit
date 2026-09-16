#pragma once

#include <vector>
#include <string>
#include <unordered_map>

struct Node {
    int id;
    double lat;
    double lon;
};

struct Edge {
    int to;
    double distance;
    double time; // Time in seconds
    int type; // 0 = walk, 1 = rail
};

struct PathStep {
    int node_id;
    int type_from_prev; // -1 for first node, 0 = walk, 1 = rail
    double dist_from_prev;
};

struct AStarResult {
    bool found;
    double total_distance;
    double total_time;
    std::vector<PathStep> path;
};

struct BlockedSegment {
    double lat1, lon1, lat2, lon2;
    double buffer_m;
};

class Graph {
public:
    std::vector<Node> nodes;
    std::vector<std::vector<Edge>> adj;
    std::vector<bool> blocked_nodes;

    bool loadFromFile(const std::string& filename);
    int findNearestNode(double lat, double lon) const;
    void applyBlockedSegments(const std::vector<BlockedSegment>& segments);
};

AStarResult findPathAStar(const Graph& graph, int start, int target);
