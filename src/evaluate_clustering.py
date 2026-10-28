from collections import defaultdict
from pathlib import Path
import json
import platform

import networkx as nx
import numpy as np
import sklearn
from sklearn.metrics import normalized_mutual_info_score


# ============================================================
# 1. 路径和评价规则
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
CLUSTER_DIR = PROJECT_DIR / "results" / "clustering"
EVALUATION_DIR = PROJECT_DIR / "results" / "evaluation"

EVALUATION_DIR.mkdir(parents=True, exist_ok=True)

SEEDS = [0, 1, 2, 3, 4]
Q_RESOLUTION = 1.0
NMI_AVERAGE_METHOD = "arithmetic"


# ============================================================
# 2. 读取固定节点顺序和网络
# ============================================================

nodes = [
    int(line.strip())
    for line in (
        PROCESSED_DIR / "analysis_nodes.txt"
    ).read_text(encoding="utf-8").splitlines()
    if line.strip()
]

if not nodes or len(nodes) != len(set(nodes)):
    raise ValueError("节点列表为空或包含重复编号")

node_set = set(nodes)

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
            raise ValueError(f"边文件第 {line_number} 行引用了未知节点")

        if source == target:
            raise ValueError(f"边文件第 {line_number} 行存在自环")

        if graph.has_edge(source, target):
            raise ValueError(f"边文件第 {line_number} 行有重复无向边")

        graph.add_edge(source, target)

if graph.number_of_edges() == 0 or not nx.is_connected(graph):
    raise ValueError("分析网络应当有边且连通")


# ============================================================
# 3. 读取真实部门标签，并按节点顺序对齐
# ============================================================

department_by_node = {}

with (PROCESSED_DIR / "analysis_labels.txt").open(
    "r", encoding="utf-8"
) as file:
    for line in file:
        if not line.strip():
            continue

        node, department = map(int, line.split())

        if node in department_by_node:
            raise ValueError(f"成员 {node} 出现重复部门记录")

        department_by_node[node] = department

if set(department_by_node) != node_set:
    raise ValueError("部门标签与分析节点集合不一致")

# 最关键的一步：按 nodes 的顺序取真实标签。
true_labels = [
    department_by_node[node]
    for node in nodes
]

print(f"评价节点数：{len(nodes)}")
print(f"评价无向边数：{graph.number_of_edges()}")
print(f"真实部门数：{len(set(true_labels))}")


# ============================================================
# 4. 将标签列表转换为社区集合
# ============================================================

def labels_to_communities(ordered_nodes, labels):
    """
    输入：
        nodes  = [0, 1, 2, 3]
        labels = [5, 5, 8, 8]

    输出：
        [{0, 1}, {2, 3}]
    """
    if len(labels) != len(ordered_nodes):
        raise ValueError("标签数量与节点数量不一致")

    if any(type(label) is not int or label < 0 for label in labels):
        raise ValueError("算法分组编号应为非负整数")

    groups = defaultdict(set)

    for node, label in zip(ordered_nodes, labels):
        groups[label].add(node)

    return list(groups.values())


# ============================================================
# 5. 逐次评价已保存的分组
# ============================================================

records = []

for seed in SEEDS:
    result_path = CLUSTER_DIR / f"seed_{seed}.json"

    result = json.loads(
        result_path.read_text(encoding="utf-8")
    )

    if result["seed"] != seed:
        raise ValueError(f"seed={seed} 文件内的种子编号不一致")

    # 不只检查人数，还要检查节点顺序。
    if result["nodes"] != nodes:
        raise ValueError(
            f"seed={seed} 的节点列表或顺序与当前数据不一致"
        )

    louvain_labels = result["louvain_labels"]
    kmeans_labels = result["kmeans_labels"]

    louvain_communities = labels_to_communities(
        nodes, louvain_labels
    )

    kmeans_communities = labels_to_communities(
        nodes, kmeans_labels
    )

    if len(louvain_communities) != result["louvain_community_count"]:
        raise ValueError(f"seed={seed} 的 Louvain 社区数记录不一致")

    if len(kmeans_communities) != result["kmeans_actual_k"]:
        raise ValueError(f"seed={seed} 的 K-means 组数记录不一致")

    # 两种方法在同一个图上、按同一个定义计算 Q。
    louvain_q = nx.community.modularity(
        graph,
        louvain_communities,
        weight=None,
        resolution=Q_RESOLUTION,
    )

    kmeans_q = nx.community.modularity(
        graph,
        kmeans_communities,
        weight=None,
        resolution=Q_RESOLUTION,
    )

    # 分别比较“算法分组”和“真实部门”。
    louvain_nmi = normalized_mutual_info_score(
        true_labels,
        louvain_labels,
        average_method=NMI_AVERAGE_METHOD,
    )

    kmeans_nmi = normalized_mutual_info_score(
        true_labels,
        kmeans_labels,
        average_method=NMI_AVERAGE_METHOD,
    )

    values = [louvain_q, kmeans_q, louvain_nmi, kmeans_nmi]

    if not np.all(np.isfinite(values)):
        raise ValueError(f"seed={seed} 存在非有限指标值")

    row = {
        "seed": seed,
        "louvain_k": len(louvain_communities),
        "kmeans_k": len(kmeans_communities),
        "louvain_q": float(louvain_q),
        "kmeans_q": float(kmeans_q),
        "louvain_nmi": float(louvain_nmi),
        "kmeans_nmi": float(kmeans_nmi),
    }

    records.append(row)


# ============================================================
# 6. 汇总均值与样本标准差
# ============================================================

summary = {}

for method in ["louvain", "kmeans"]:
    summary[method] = {}

    for metric in ["q", "nmi"]:
        values = np.array(
            [row[f"{method}_{metric}"] for row in records],
            dtype=float,
        )

        summary[method][metric] = {
            "mean": float(np.mean(values)),
            "std": float(np.std(values, ddof=1)),
        }


# ============================================================
# 7. 保存原始精度的结果
# ============================================================

def save_json(filename, content):
    (EVALUATION_DIR / filename).write_text(
        json.dumps(content, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


save_json("per_seed_metrics.json", records)
save_json("summary_metrics.json", summary)

save_json("evaluation_config.json", {
    "node_count": len(nodes),
    "edge_count": graph.number_of_edges(),
    "department_count": len(set(true_labels)),
    "seeds": SEEDS,
    "q_weight": None,
    "q_resolution": Q_RESOLUTION,
    "nmi_average_method": NMI_AVERAGE_METHOD,
    "std_ddof": 1,
    "python_version": platform.python_version(),
    "networkx_version": nx.__version__,
    "numpy_version": np.__version__,
    "sklearn_version": sklearn.__version__,
})


# ============================================================
# 8. 生成便于填写 Word 的文本表格
# ============================================================

lines = [
    "每次实验结果",
    "seed\tLouvain组数\tK-means组数\tLouvain_Q\tK-means_Q"
    "\tLouvain_NMI\tK-means_NMI",
]

for row in records:
    lines.append(
        f"{row['seed']}\t"
        f"{row['louvain_k']}\t"
        f"{row['kmeans_k']}\t"
        f"{row['louvain_q']:.4f}\t"
        f"{row['kmeans_q']:.4f}\t"
        f"{row['louvain_nmi']:.4f}\t"
        f"{row['kmeans_nmi']:.4f}"
    )

lines.extend([
    "",
    "汇总结果：均值 ± 样本标准差",
    "方法\tQ\tNMI",
])

for method, display_name in [
    ("kmeans", "K-means"),
    ("louvain", "Louvain"),
]:
    q = summary[method]["q"]
    nmi = summary[method]["nmi"]

    lines.append(
        f"{display_name}\t"
        f"{q['mean']:.4f} ± {q['std']:.4f}\t"
        f"{nmi['mean']:.4f} ± {nmi['std']:.4f}"
    )

report_text = "\n".join(lines)

(EVALUATION_DIR / "report_tables.txt").write_text(
    report_text,
    encoding="utf-8",
)

print()
print(report_text)
print()
print(f"评价结果已保存：{EVALUATION_DIR}")