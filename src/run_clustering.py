from collections import Counter
from pathlib import Path
import json
import platform

import networkx as nx
import numpy as np
import sklearn
from sklearn.cluster import KMeans


# ============================================================
# 1. 路径和实验参数
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
RESULTS_DIR = PROJECT_DIR / "results"
CLUSTER_DIR = RESULTS_DIR / "clustering"

CLUSTER_DIR.mkdir(parents=True, exist_ok=True)

NODE_FILE = PROCESSED_DIR / "analysis_nodes.txt"
EDGE_FILE = PROCESSED_DIR / "analysis_edges.txt"

SEEDS = [0, 1, 2, 3, 4]

LOUVAIN_RESOLUTION = 1.0
LOUVAIN_THRESHOLD = 1e-7

KMEANS_N_INIT = 10
KMEANS_MAX_ITER = 300
KMEANS_TOL = 1e-4


# ============================================================
# 2. 加载固定的节点顺序和边
# ============================================================

nodes = [
    int(line.strip())
    for line in NODE_FILE.read_text(encoding="utf-8").splitlines()
    if line.strip()
]

if not nodes:
    raise ValueError("节点文件为空")

if len(nodes) != len(set(nodes)):
    raise ValueError("节点文件中出现重复成员编号")

node_set = set(nodes)

graph = nx.Graph()
graph.add_nodes_from(nodes)

with EDGE_FILE.open("r", encoding="utf-8") as file:
    for line_number, line in enumerate(file, start=1):
        line = line.strip()

        if not line:
            continue

        fields = line.split()

        if len(fields) != 2:
            raise ValueError(f"边文件第 {line_number} 行不是两列")

        source, target = map(int, fields)

        if source not in node_set or target not in node_set:
            raise ValueError(
                f"边文件第 {line_number} 行引用了节点表之外的成员"
            )

        if source == target:
            raise ValueError(
                f"边文件第 {line_number} 行存在自环"
            )

        if graph.has_edge(source, target):
            raise ValueError(
                f"边文件第 {line_number} 行存在重复无向边"
            )

        graph.add_edge(source, target)

if not nx.is_connected(graph):
    raise ValueError("输入网络不是连通图，请检查第二步结果")

print(f"输入节点数：{graph.number_of_nodes()}")
print(f"输入无向边数：{graph.number_of_edges()}")


# ============================================================
# 3. 构建 K-means 使用的邻接矩阵
# ============================================================

X = nx.to_numpy_array(
    graph,
    nodelist=nodes,
    dtype=np.float64,
    weight=None,
)

assert X.shape == (len(nodes), len(nodes))
assert np.array_equal(X, X.T), "无向图矩阵应当对称"
assert np.all(np.diag(X) == 0), "主对角线应为 0"
assert np.all((X == 0) | (X == 1)), "矩阵只能含 0 和 1"

# 无向图中，每条边在矩阵中出现两次。
assert int(X.sum()) == 2 * graph.number_of_edges()

print(f"邻接矩阵形状：{X.shape}")
print(f"邻接矩阵元素之和：{int(X.sum())}")


# ============================================================
# 4. 整理社区编号和检查分组结果的辅助函数
# ============================================================

def communities_to_labels(communities, ordered_nodes):
    """
    将 Louvain 的社区集合转换成与节点顺序一致的标签列表。
    社区按最小成员编号排序，只是为了让输出编号更明确。
    """

    ordered_communities = sorted(
        communities,
        key=lambda community: min(community),
    )

    node_to_cluster = {}

    for cluster_id, community in enumerate(ordered_communities):
        for node in community:
            if node in node_to_cluster:
                raise ValueError(f"成员 {node} 被分到多个社区")

            node_to_cluster[node] = cluster_id

    if set(node_to_cluster) != set(ordered_nodes):
        raise ValueError("Louvain 结果未完整覆盖输入节点")

    return [
        node_to_cluster[node]
        for node in ordered_nodes
    ]


def get_cluster_sizes(cluster_labels):
    """返回各组人数，按照组编号排列。"""
    counts = Counter(cluster_labels)

    return {
        str(cluster_id): counts[cluster_id]
        for cluster_id in sorted(counts)
    }


# ============================================================
# 5. 运行 5 次配对实验
# ============================================================

summary = []

for seed in SEEDS:
    print()
    print(f"开始运行 seed={seed}")

    # ---------- Louvain ----------

    communities = nx.community.louvain_communities(
        graph,
        weight=None,
        resolution=LOUVAIN_RESOLUTION,
        threshold=LOUVAIN_THRESHOLD,
        seed=seed,
    )

    louvain_labels = communities_to_labels(
        communities,
        nodes,
    )

    louvain_k = len(communities)

    # ---------- K-means ----------

    model = KMeans(
        n_clusters=louvain_k,
        init="k-means++",
        n_init=KMEANS_N_INIT,
        max_iter=KMEANS_MAX_ITER,
        tol=KMEANS_TOL,
        random_state=seed,
        algorithm="lloyd",
    )

    kmeans_labels = model.fit_predict(X).tolist()
    kmeans_actual_k = len(set(kmeans_labels))

    # ---------- 输出检查 ----------

    assert len(louvain_labels) == len(nodes)
    assert len(kmeans_labels) == len(nodes)

    louvain_sizes = get_cluster_sizes(louvain_labels)
    kmeans_sizes = get_cluster_sizes(kmeans_labels)

    assert sum(louvain_sizes.values()) == len(nodes)
    assert sum(kmeans_sizes.values()) == len(nodes)

    if kmeans_actual_k != louvain_k:
        print(
            "注意：K-means 实际非空组数与目标 K 不一致，"
            "请保留此提示并检查。"
        )

    if model.n_iter_ >= KMEANS_MAX_ITER:
        print(
            "注意：K-means 达到最大迭代次数，"
            "需要检查是否充分收敛。"
        )

    # ---------- 保存本次结果 ----------

    result = {
        "seed": seed,
        "nodes": nodes,
        "louvain_labels": louvain_labels,
        "kmeans_labels": kmeans_labels,
        "louvain_community_count": louvain_k,
        "kmeans_target_k": louvain_k,
        "kmeans_actual_k": kmeans_actual_k,
        "louvain_cluster_sizes": louvain_sizes,
        "kmeans_cluster_sizes": kmeans_sizes,
        "kmeans_n_iter": int(model.n_iter_),
    }

    result_path = CLUSTER_DIR / f"seed_{seed}.json"

    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 额外保存便于直接阅读的三列表格。
    assignment_path = CLUSTER_DIR / f"seed_{seed}_assignments.txt"

    with assignment_path.open("w", encoding="utf-8") as file:
        file.write("node_id\tlouvain_cluster\tkmeans_cluster\n")

        for node, lou_label, km_label in zip(
            nodes, louvain_labels, kmeans_labels
        ):
            file.write(f"{node}\t{lou_label}\t{km_label}\n")

    summary.append({
        "seed": seed,
        "louvain_community_count": louvain_k,
        "kmeans_target_k": louvain_k,
        "kmeans_actual_k": kmeans_actual_k,
        "kmeans_n_iter": int(model.n_iter_),
    })

    print(
        f"Louvain 社区数：{louvain_k}；"
        f"K-means 目标组数：{louvain_k}；"
        f"K-means 实际组数：{kmeans_actual_k}"
    )
    print(f"Louvain 各组人数：{list(louvain_sizes.values())}")
    print(f"K-means 各组人数：{list(kmeans_sizes.values())}")
    print(f"K-means 所选结果的迭代次数：{model.n_iter_}")


# ============================================================
# 6. 保存汇总和配置
# ============================================================

(CLUSTER_DIR / "run_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

config = {
    "python_version": platform.python_version(),
    "networkx_version": nx.__version__,
    "numpy_version": np.__version__,
    "sklearn_version": sklearn.__version__,
    "node_count": graph.number_of_nodes(),
    "edge_count": graph.number_of_edges(),
    "seeds": SEEDS,
    "feature": "binary adjacency rows without scaling",
    "k_rule": "use Louvain community count from the same seed",
    "louvain": {
        "weight": None,
        "resolution": LOUVAIN_RESOLUTION,
        "threshold": LOUVAIN_THRESHOLD,
    },
    "kmeans": {
        "init": "k-means++",
        "n_init": KMEANS_N_INIT,
        "max_iter": KMEANS_MAX_ITER,
        "tol": KMEANS_TOL,
        "algorithm": "lloyd",
    },
}

(CLUSTER_DIR / "experiment_config.json").write_text(
    json.dumps(config, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print()
print("第三步完成：5 次配对分组结果已保存。")
print(f"结果目录：{CLUSTER_DIR}")
print("本脚本未读取真实部门标签，也未计算 Q 和 NMI。")