from pathlib import Path
import json
import platform

import networkx as nx


# ============================================================
# 1. 定位文件
# ============================================================

# 当前脚本位于 项目目录/src/prepare_data.py
PROJECT_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
RESULTS_DIR = PROJECT_DIR / "results"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

EDGE_FILE = RAW_DIR / "email-Eu-core.txt"
LABEL_FILE = RAW_DIR / "email-Eu-core-department-labels.txt"


def read_pairs(path):
    """读取两列非负整数，保留原始记录顺序。"""
    records = []

    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            # 忽略空行和注释行。
            if not line or line.startswith("#"):
                continue

            fields = line.split()

            if len(fields) != 2:
                raise ValueError(
                    f"{path.name} 第 {line_number} 行不是两列：{line}"
                )

            try:
                first, second = map(int, fields)
            except ValueError as error:
                raise ValueError(
                    f"{path.name} 第 {line_number} 行含非整数：{line}"
                ) from error

            if first < 0 or second < 0:
                raise ValueError(
                    f"{path.name} 第 {line_number} 行出现负数：{line}"
                )

            records.append((first, second))

    if not records:
        raise ValueError(f"{path.name} 没有有效记录")

    return records


# ============================================================
# 2. 读取并检查部门标签
# ============================================================

label_records = read_pairs(LABEL_FILE)

# labels 的结构是：
# {成员编号: 部门编号}
labels = {}

for member_id, department_id in label_records:
    if member_id in labels:
        raise ValueError(
            f"成员 {member_id} 出现重复部门记录，请先检查标签文件"
        )

    labels[member_id] = department_id


# ============================================================
# 3. 读取联系，检查两个文件是否能正确关联
# ============================================================

raw_edges = read_pairs(EDGE_FILE)

edge_nodes = {
    node
    for source, target in raw_edges
    for node in (source, target)
}

label_nodes = set(labels)

# 缺失部门标签的节点
missing_label_nodes = edge_nodes - label_nodes

if missing_label_nodes:
    raise ValueError(
        "以下成员缺少部门标签："
        f"{sorted(missing_label_nodes)[:20]}"
    )

# 仅在标签表中出现的节点
label_only_nodes = label_nodes - edge_nodes


# ============================================================
# 4. 边数据清洗: 去重、删除自环、无向化
# ============================================================

# 去重
unique_directed_edges = set(raw_edges)
duplicate_record_count = (
    len(raw_edges) - len(unique_directed_edges)
)

# 统计自环
self_loop_count = sum(
    source == target
    for source, target in unique_directed_edges
)

# 去重去自环后的有向边
directed_edges_without_loops = {
    (source, target)
    for source, target in unique_directed_edges
    if source != target
}

# 无向边
undirected_edges = {
    (min(source, target), max(source, target))
    for source, target in directed_edges_without_loops
}

# 无向化合并的反向边数
direction_merge_count = (
    len(directed_edges_without_loops)
    - len(undirected_edges)
)


# ============================================================
# 5. 构建完整无向图，选取最大连通分量
# ============================================================

graph = nx.Graph()

# 添加节点全集，避免没有剩余边的节点消失。
all_nodes = edge_nodes | label_nodes
graph.add_nodes_from(sorted(all_nodes))

# 添加处理后的无向边。
graph.add_edges_from(sorted(undirected_edges))

# 将全部连通分量按大小降序排列。若大小相同，优先选择最小成员编号更小的分量。
components = sorted(
    nx.connected_components(graph),
    key=lambda nodes: (-len(nodes), min(nodes)),
)

# 取最大连通分量
largest_component_nodes = components[0]

analysis_graph = graph.subgraph(
    largest_component_nodes
).copy()

# 大连同分量的节点和边按顺序保存。
analysis_nodes = sorted(analysis_graph.nodes())

analysis_edges = sorted(
    (min(source, target), max(source, target))
    for source, target in analysis_graph.edges()
)

# 被排除的节点
excluded_nodes = sorted(
    set(graph.nodes()) - set(analysis_nodes)
)


# ============================================================
# 6. 检查处理结果，保存算法输入
# ============================================================

assert not analysis_graph.is_directed(), "分析图仍然是有向图"
assert nx.number_of_selfloops(analysis_graph) == 0, "仍有自环"
assert nx.is_connected(analysis_graph), "分析图不是连通图"
assert all(node in labels for node in analysis_nodes), "存在缺失标签"

# 核对边数的处理过程能否对上。
assert (
    len(raw_edges)
    - duplicate_record_count
    - self_loop_count
    - direction_merge_count
    == graph.number_of_edges()
), "边数统计不一致"

# 保存最终无向边表。
with (PROCESSED_DIR / "analysis_edges.txt").open(
    "w", encoding="utf-8"
) as file:
    for source, target in analysis_edges:
        file.write(f"{source} {target}\n")

# 保存最终节点顺序。
with (PROCESSED_DIR / "analysis_nodes.txt").open(
    "w", encoding="utf-8"
) as file:
    for node in analysis_nodes:
        file.write(f"{node}\n")

# 保存同一节点集合对应的部门标签。
with (PROCESSED_DIR / "analysis_labels.txt").open(
    "w", encoding="utf-8"
) as file:
    for node in analysis_nodes:
        file.write(f"{node} {labels[node]}\n")

# 保存被排除的成员
with (PROCESSED_DIR / "excluded_nodes.txt").open(
    "w", encoding="utf-8"
) as file:
    for node in excluded_nodes:
        file.write(f"{node}\n")


# ============================================================
# 7. 输出统计
# ============================================================

stats = {
    "原始联系记录数": len(raw_edges),
    "原始联系中的节点数": len(edge_nodes),
    "部门标签记录数": len(label_records),
    "原始部门数": len(set(labels.values())),
    "缺失部门标签的节点数": len(missing_label_nodes),
    "仅在标签表中出现的节点数": len(label_only_nodes),
    "删除的重复有向记录数": duplicate_record_count,
    "去重后删除的自环数": self_loop_count,
    "去重去自环后的有向边数": len(directed_edges_without_loops),
    "无向化合并的反向联系数": direction_merge_count,
    "完整无向图节点数": graph.number_of_nodes(),
    "完整无向图边数": graph.number_of_edges(),
    "完整无向图孤立节点数": nx.number_of_isolates(graph),
    "完整无向图连通分量数": len(components),
    "最大连通分量节点数": analysis_graph.number_of_nodes(),
    "最大连通分量边数": analysis_graph.number_of_edges(),
    "排除节点数": len(excluded_nodes),
    "保留节点比例": (
        analysis_graph.number_of_nodes()
        / graph.number_of_nodes()
    ),
    "最终保留的部门数": len({
        labels[node] for node in analysis_nodes
    }),
    "Python版本": platform.python_version(),
    "NetworkX版本": nx.__version__,
}

stats_path = RESULTS_DIR / "preprocess_stats.json"

stats_path.write_text(
    json.dumps(stats, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

for name, value in stats.items():
    if name == "保留节点比例":
        print(f"{name}：{value:.2%}")
    else:
        print(f"{name}：{value}")

print()
print("数据处理完成。")
print(f"算法输入目录：{PROCESSED_DIR}")
print(f"统计结果文件：{stats_path}")