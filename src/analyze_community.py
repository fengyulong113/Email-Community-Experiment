from collections import Counter
from pathlib import Path
import json

import networkx as nx

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt


# ============================================================
# 1. 路径与固定的案例选择规则
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
CLUSTER_DIR = PROJECT_DIR / "results" / "clustering"
CASE_DIR = PROJECT_DIR / "results" / "case_study"
FIGURE_DIR = PROJECT_DIR / "results" / "figures"

CASE_DIR.mkdir(parents=True, exist_ok=True)
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

CASE_SEED = 0


# ============================================================
# 2. 读取节点、部门标签和已完成的分组
# ============================================================

nodes = [
    int(line.strip())
    for line in (
        PROCESSED_DIR / "analysis_nodes.txt"
    ).read_text(encoding="utf-8").splitlines()
    if line.strip()
]

if not nodes or len(nodes) != len(set(nodes)):
    raise ValueError("节点列表为空或存在重复编号")

node_set = set(nodes)

department_by_node = {}

with (PROCESSED_DIR / "analysis_labels.txt").open(
    "r", encoding="utf-8"
) as file:
    for line in file:
        if not line.strip():
            continue

        node, department = map(int, line.split())

        if node in department_by_node:
            raise ValueError(f"成员 {node} 出现重复标签")

        department_by_node[node] = department

if set(department_by_node) != node_set:
    raise ValueError("部门标签与分析节点集合不一致")

result = json.loads(
    (CLUSTER_DIR / f"seed_{CASE_SEED}.json").read_text(
        encoding="utf-8"
    )
)

if result["seed"] != CASE_SEED or result["nodes"] != nodes:
    raise ValueError("分组文件中的种子或节点顺序不一致")

louvain_labels = result["louvain_labels"]

if len(louvain_labels) != len(nodes):
    raise ValueError("Louvain 标签数量与节点数量不一致")

if any(type(label) is not int or label < 0 for label in louvain_labels):
    raise ValueError("社区编号应为非负整数")


# ============================================================
# 3. 选择人数最多的社区
# ============================================================

community_sizes = Counter(louvain_labels)

# 优先人数最多；若人数相同，优先编号较小。
selected_community = min(
    community_sizes,
    key=lambda community_id: (
        -community_sizes[community_id],
        community_id,
    ),
)

selected_nodes = [
    node
    for node, community_id in zip(nodes, louvain_labels)
    if community_id == selected_community
]

selected_count = len(selected_nodes)


# ============================================================
# 4. 统计部门构成
# ============================================================

# 整个分析网络中，各部门的人数。
department_totals = Counter(
    department_by_node[node]
    for node in nodes
)

# 当前社区中，各部门的人数。
case_department_counts = Counter(
    department_by_node[node]
    for node in selected_nodes
)

# 按社区内人数降序排列，同人数时按部门编号排序。
ordered_departments = sorted(
    case_department_counts.items(),
    key=lambda item: (-item[1], item[0]),
)

composition = []

for department, count in ordered_departments:
    department_total = department_totals[department]

    composition.append({
        "department_id": department,
        "members_in_community": count,
        "share_of_community": count / selected_count,
        "department_total_in_analysis_graph": department_total,
        "department_coverage": count / department_total,
    })

assert sum(
    row["members_in_community"]
    for row in composition
) == selected_count


# ============================================================
# 5. 保存并打印案例结果
# ============================================================

case_result = {
    "seed": CASE_SEED,
    "selection_rule": (
        "largest Louvain community; "
        "break ties by smaller community ID"
    ),
    "selected_community": selected_community,
    "community_size": selected_count,
    "share_of_analysis_nodes": selected_count / len(nodes),
    "department_count": len(composition),
    "community_sizes": dict(sorted(community_sizes.items())),
    "department_composition": composition,
}

(CASE_DIR / "largest_community.json").write_text(
    json.dumps(case_result, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

with (CASE_DIR / "largest_community_members.txt").open(
    "w", encoding="utf-8"
) as file:
    file.write("node_id\tdepartment_id\n")

    for node in selected_nodes:
        file.write(f"{node}\t{department_by_node[node]}\n")

lines = [
    f"案例种子：{CASE_SEED}",
    f"Louvain 社区总数：{len(community_sizes)}",
    f"各社区人数：{dict(sorted(community_sizes.items()))}",
    f"选中的最大社区编号：{selected_community}",
    f"最大社区人数：{selected_count}",
    f"占分析节点比例：{selected_count / len(nodes):.2%}",
    f"涉及部门数：{len(composition)}",
    "",
    "部门编号\t社区内人数\t占社区比例"
    "\t分析网络中该部门总人数\t部门覆盖比例",
]

for row in composition:
    lines.append(
        f"{row['department_id']}\t"
        f"{row['members_in_community']}\t"
        f"{row['share_of_community']:.2%}\t"
        f"{row['department_total_in_analysis_graph']}\t"
        f"{row['department_coverage']:.2%}"
    )

report_text = "\n".join(lines)

(CASE_DIR / "case_report.txt").write_text(
    report_text,
    encoding="utf-8",
)

print(report_text)


# ============================================================
# 6. 绘制该社区的部门人数图
# ============================================================

department_names = [
    f"Dept {row['department_id']}"
    for row in composition
]

counts = [
    row["members_in_community"]
    for row in composition
]

figure_height = max(4.0, 0.32 * len(composition) + 1.7)

fig, ax = plt.subplots(
    figsize=(8.5, figure_height),
    constrained_layout=True,
)

positions = list(range(len(composition)))

bars = ax.barh(
    positions,
    counts,
    color="#2878B5",
    height=0.7,
)

ax.set_yticks(positions, department_names)
ax.invert_yaxis()

ax.set_xlabel("Number of members")
ax.set_title(
    f"Department composition of Louvain community "
    f"{selected_community}\n"
    f"seed={CASE_SEED}, n={selected_count}, "
    f"departments={len(composition)}"
)

ax.set_xlim(0, max(counts) * 1.35)
ax.grid(axis="x", alpha=0.25)
ax.set_axisbelow(True)

for bar, row in zip(bars, composition):
    ax.text(
        bar.get_width() + max(counts) * 0.015,
        bar.get_y() + bar.get_height() / 2,
        f"{row['members_in_community']} "
        f"({row['share_of_community']:.1%})",
        va="center",
        fontsize=9,
    )

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

composition_path = (
    FIGURE_DIR / "largest_community_departments.png"
)

fig.savefig(
    composition_path,
    dpi=300,
    facecolor="white",
)

plt.close(fig)


# ============================================================
# 7. 补画完整分析网络的示意图
# ============================================================

graph = nx.Graph()
graph.add_nodes_from(nodes)

with (PROCESSED_DIR / "analysis_edges.txt").open(
    "r", encoding="utf-8"
) as file:
    for line_number, line in enumerate(file, start=1):
        if not line.strip():
            continue

        source, target = map(int, line.split())

        if source not in node_set or target not in node_set:
            raise ValueError(f"第 {line_number} 行包含未知节点")

        if source == target or graph.has_edge(source, target):
            raise ValueError(f"第 {line_number} 行存在自环或重复边")

        graph.add_edge(source, target)

if not nx.is_connected(graph):
    raise ValueError("输入网络不是连通图")

print()
print("正在计算网络图布局，请等待……")

# 固定布局种子，便于同一环境下复现图片。
# 布局只用于确定画面位置，不修改分组。
positions = nx.spring_layout(
    graph,
    seed=42,
    iterations=80,
    weight=None,
    method="force",
)

fig, ax = plt.subplots(figsize=(9, 8))

nx.draw_networkx_edges(
    graph,
    positions,
    ax=ax,
    edge_color="#9AA4AE",
    alpha=0.12,
    width=0.35,
)

nx.draw_networkx_nodes(
    graph,
    positions,
    nodelist=nodes,
    ax=ax,
    node_size=13,
    node_color="#2878B5",
    edgecolors="none",
    alpha=0.9,
)

ax.set_title(
    "Email communication network\n"
    f"{graph.number_of_nodes()} nodes, "
    f"{graph.number_of_edges()} undirected edges"
)

ax.set_axis_off()

network_path = FIGURE_DIR / "analysis_network.png"

fig.savefig(
    network_path,
    dpi=300,
    bbox_inches="tight",
    facecolor="white",
)

plt.close(fig)

print(f"案例结果：{CASE_DIR}")
print(f"部门构成图：{composition_path}")
print(f"网络示意图：{network_path}")