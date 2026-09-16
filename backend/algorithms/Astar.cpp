#include "Astar.h"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <limits>
#include <queue>
#include <utility>

using namespace std;

// Haversine distance
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

struct State {
  int u;
  double g;
  double f;
  bool operator>(const State &other) const { return f > other.f; }
};

struct ParentData {
  int u;
  int type;
  double dist;
};

AStarResult findPathAStar(const Graph &graph, int start, int target) {
  AStarResult res;
  res.found = false;
  res.total_distance = 0;
  res.total_time = 0;

  if (start < 0 || start >= (int)graph.nodes.size() || target < 0 ||
      target >= (int)graph.nodes.size()) {
    return res;
  }

  int n = (int)graph.nodes.size();
  vector<double> g_time(n, numeric_limits<double>::infinity());
  vector<ParentData> parent(n, {-1, -1, 0.0});

  priority_queue<State, vector<State>, greater<State>> pq;

  g_time[start] = 0;
  // max speed ~15m/s for admissible heuristic
  double h_start = haversine(graph.nodes[start].lat, graph.nodes[start].lon,
                             graph.nodes[target].lat, graph.nodes[target].lon) /
                   15.0;
  pq.push({start, 0, h_start});

  while (!pq.empty()) {
    State current = pq.top();
    pq.pop();

    int u = current.u;

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
      // Reverse path
      for (int i = 0; i < (int)res.path.size() / 2; ++i) {
        swap(res.path[i], res.path[(int)res.path.size() - 1 - i]);
      }
      return res;
    }

    if (current.g > g_time[u])
      continue;

    for (const auto &edge : graph.adj[u]) {
      int v = edge.to;
      if ((int)graph.blocked_nodes.size() > v && graph.blocked_nodes[v])
        continue;

      double time_cost = edge.time;
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
