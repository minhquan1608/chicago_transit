#!/usr/bin/env python3
import os
import networkx as nx
import math
import json
from pathlib import Path

# Thử import osmnx, nếu lỗi thì thoát an toàn
try:
    import osmnx as ox
except ImportError:
    print("Vui lòng cài đặt osmnx: pip install osmnx")
    exit(1)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ASSETS_DIR = ROOT_DIR / "data" / "assets"
GRAPH_FILE = ASSETS_DIR / "data_graph.txt"
RAIL_STATIONS_FILE = ASSETS_DIR / "cta_rail_stations.json"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def build_graph():
    print("Đang tải dữ liệu mạng lưới đường phố Chicago (chỉ lấy đường chính để tối ưu)...")
    # Lấy dữ liệu đường sá. network_type='drive' sẽ nhẹ hơn 'walk' rất nhiều, phù hợp để thử nghiệm A* chạy nhanh.
    # Trong môi trường thực tế, nếu RAM lớn có thể đổi thành 'all'.
    place_name = "Chicago, Illinois, USA"
    G = ox.graph_from_place(place_name, network_type='drive', simplify=False)
    print("Đang lọc thành phần liên thông mạnh lớn nhất để đảm bảo luôn có đường đi...")
    G = ox.truncate.largest_component(G, strongly=True)
    
    # Lấy thông tin các node và edge
    nodes = list(G.nodes(data=True))
    edges = list(G.edges(data=True))

    # Gán ID tuần tự cho node từ 0 đến N-1
    node_mapping = {}
    for idx, (node_id, data) in enumerate(nodes):
        node_mapping[node_id] = idx

    # Đọc thêm các ga tàu CTA nếu có
    rail_nodes = []
    rail_edges = []
    
    import json
    from shapely.geometry import shape, Point
    
    RAIL_LINES_FILE = ASSETS_DIR / "cta_rail_lines.geojson"
    
    if RAIL_STATIONS_FILE.exists() and RAIL_LINES_FILE.exists():
        try:
            with open(RAIL_STATIONS_FILE, 'r', encoding='utf-8') as f:
                stations_data = json.load(f)
            with open(RAIL_LINES_FILE, 'r', encoding='utf-8') as f:
                lines_data = json.load(f)
                
            # Tạo node cho các ga tàu
            station_mapping = {} # stop_id -> idx
            for st in stations_data:
                idx = len(node_mapping) + len(rail_nodes)
                station_mapping[st["stop_id"]] = idx
                rail_nodes.append((idx, st["lat"], st["lon"]))
                
                # Tìm node đường phố gần nhất để làm cầu nối đi bộ vào ga (Transfer)
                best_node = -1
                min_d = float('inf')
                # Để nhanh, chỉ duyệt 1000 node đầu tiên hoặc lấy node gần nhất
                # Trong thực tế có thể dùng KDTree, ở đây duyệt toàn bộ vì script build chạy 1 lần
                for node_id, data in nodes:
                    d = haversine(st["lat"], st["lon"], data['y'], data['x'])
                    if d < min_d:
                        min_d = d
                        best_node = node_mapping[node_id]
                
                if best_node != -1:
                    # Transfer edge: type=0 (walk). Thêm 60s thời gian đi xuống ga.
                    walk_time = (min_d / 1.3) + 60.0
                    rail_edges.append((idx, best_node, min_d, walk_time, 0))
                    rail_edges.append((best_node, idx, min_d, walk_time, 0))

            from shapely.ops import linemerge
            
            # Gộp các segment của cùng một route_id lại thành một đường duy nhất
            lines_by_route = {}
            for feature in lines_data.get("features", []):
                route_id = feature.get("properties", {}).get("route_id")
                if not route_id:
                    continue
                if route_id not in lines_by_route:
                    lines_by_route[route_id] = []
                lines_by_route[route_id].append(shape(feature["geometry"]))
            
            ROUTE_TYPES = {
                "Red": 1,
                "Blue": 2,
                "Brn": 3,
                "G": 4,
                "Org": 5,
                "P": 6,
                "Pink": 7,
                "Y": 8
            }
                
            # Tìm các cạnh tàu (Rail edges)
            for route_id, line_geoms in lines_by_route.items():
                rail_type = ROUTE_TYPES.get(route_id, 1)
                merged_line = linemerge(line_geoms)
                
                # Tìm các ga thuộc route_id này
                route_stations = []
                for st in stations_data:
                    if route_id in st.get("routes", []):
                        pt = Point(st["lon"], st["lat"])
                        proj = merged_line.project(pt)
                        route_stations.append((proj, st))
                
                # Sắp xếp các ga theo thứ tự trên line
                route_stations.sort(key=lambda x: x[0])
                route_stations = [x[1] for x in route_stations]
                
                import networkx as nx
                G_track = nx.Graph()
                if merged_line.geom_type == 'MultiLineString':
                    geoms = merged_line.geoms
                else:
                    geoms = [merged_line]
                
                for line in geoms:
                    line_coords = list(line.coords)
                    for j in range(len(line_coords) - 1):
                        d = haversine(line_coords[j][1], line_coords[j][0], line_coords[j+1][1], line_coords[j+1][0])
                        G_track.add_edge(line_coords[j], line_coords[j+1], weight=d)
                
                def get_closest_node(lon, lat):
                    min_d = float('inf')
                    best_n = None
                    for n in G_track.nodes:
                        d = haversine(lat, lon, n[1], n[0])
                        if d < min_d:
                            min_d = d
                            best_n = n
                    return best_n
                
                # Nối các ga liên tiếp
                for i in range(len(route_stations) - 1):
                    st1 = route_stations[i]
                    st2 = route_stations[i+1]
                    
                    n1 = get_closest_node(st1["lon"], st1["lat"])
                    n2 = get_closest_node(st2["lon"], st2["lat"])
                    
                    if n1 and n2 and nx.has_path(G_track, n1, n2):
                        coords = nx.shortest_path(G_track, n1, n2, weight='weight')
                    else:
                        coords = [(st1["lon"], st1["lat"]), (st2["lon"], st2["lat"])]
                            
                    prev_idx = station_mapping[st1["stop_id"]]
                    prev_lat, prev_lon = st1["lat"], st1["lon"]
                    
                    for pt in coords:
                        idx = len(node_mapping) + len(rail_nodes)
                        rail_nodes.append((idx, pt[1], pt[0]))
                        
                        dist = haversine(prev_lat, prev_lon, pt[1], pt[0])
                        if dist > 0:
                            rail_time = (dist / 15.0)
                            rail_edges.append((prev_idx, idx, dist, rail_time, rail_type))
                            rail_edges.append((idx, prev_idx, dist, rail_time, rail_type))
                        
                        prev_idx = idx
                        prev_lat, prev_lon = pt[1], pt[0]
                        
                    idx2 = station_mapping[st2["stop_id"]]
                    dist = haversine(prev_lat, prev_lon, st2["lat"], st2["lon"])
                    if dist > 0:
                        # Cộng 30s dừng ga cho cạnh cuối cùng nối vào ga st2
                        rail_time = (dist / 15.0) + 30.0
                        rail_edges.append((prev_idx, idx2, dist, rail_time, rail_type))
                        rail_edges.append((idx2, prev_idx, dist, rail_time, rail_type))
                    
        except Exception as e:
            print(f"Lỗi khi xử lý dữ liệu tàu: {e}")

    total_nodes = len(nodes) + len(rail_nodes)
    
    # Lọc các edge đường bộ hợp lệ
    valid_edges = []
    for u, v, data in edges:
        if u in node_mapping and v in node_mapping:
            weight = data.get('length', 0.0)
            if weight == 0.0:
                lat1, lon1 = G.nodes[u]['y'], G.nodes[u]['x']
                lat2, lon2 = G.nodes[v]['y'], G.nodes[v]['x']
                weight = haversine(lat1, lon1, lat2, lon2)
            # Walk edge: type=0
            walk_time = weight / 1.3
            valid_edges.append((node_mapping[u], node_mapping[v], weight, walk_time, 0))

    total_edges = len(valid_edges) + len(rail_edges)

    print(f"Đã trích xuất xong: {total_nodes} nodes, {total_edges} edges.")
    print(f"Đang lưu vào {GRAPH_FILE} ...")
    
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(GRAPH_FILE, 'w') as f:
        # Dòng 1: N M
        f.write(f"{total_nodes} {total_edges}\n")
        
        # In các Node đường bộ: ID Lat Lon
        for node_id, data in nodes:
            idx = node_mapping[node_id]
            f.write(f"{idx} {data['y']:.6f} {data['x']:.6f}\n")
            
        # In các Node tàu
        for idx, lat, lon in rail_nodes:
            f.write(f"{idx} {lat:.6f} {lon:.6f}\n")
            
        # In các Edge: u v distance_m time_sec type
        for u, v, dist, time_sec, t in valid_edges:
            f.write(f"{u} {v} {dist:.2f} {time_sec:.2f} {t}\n")
            
        for u, v, dist, time_sec, t in rail_edges:
            f.write(f"{u} {v} {dist:.2f} {time_sec:.2f} {t}\n")

    print("Hoàn tất!")

if __name__ == "__main__":
    build_graph()
