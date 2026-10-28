from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parent.parent

EVALUATION_DIR = PROJECT_DIR / "results" / "evaluation"
FIGURE_DIR = PROJECT_DIR / "results" / "figures"

FIGURE_DIR.mkdir(parents=True, exist_ok=True)

summary = json.loads(
    (EVALUATION_DIR / "summary_metrics.json").read_text(
        encoding="utf-8"
    )
)

records = json.loads(
    (EVALUATION_DIR / "per_seed_metrics.json").read_text(
        encoding="utf-8"
    )
)

methods = ["kmeans", "louvain"]
method_names = ["K-means", "Louvain"]
colors = ["#8A9BA8", "#2878B5"]

fig, axes = plt.subplots(
    1, 2,
    figsize=(9, 4.6),
    constrained_layout=True,
)

for ax, metric, title in zip(
    axes,
    ["q", "nmi"],
    ["Modularity Q", "NMI with departments"],
):
    means = np.array([
        summary[method][metric]["mean"]
        for method in methods
    ])

    stds = np.array([
        summary[method][metric]["std"]
        for method in methods
    ])

    positions = np.arange(len(methods))

    ax.bar(
        positions,
        means,
        yerr=stds,
        capsize=6,
        width=0.55,
        color=colors,
        edgecolor="white",
        error_kw={"elinewidth": 1.3},
        zorder=2,
    )

    # 小圆点表示五次实际结果，横向错开以避免重叠。
    offsets = np.linspace(-0.12, 0.12, len(records))

    for position, method in enumerate(methods):
        values = [
            row[f"{method}_{metric}"]
            for row in records
        ]

        ax.scatter(
            position + offsets,
            values,
            color="black",
            s=20,
            zorder=3,
        )

    ax.set_xticks(positions, method_names)
    ax.set_title(title, fontsize=12)
    ax.set_ylabel("Score")
    ax.grid(axis="y", alpha=0.25, zorder=0)
    ax.set_axisbelow(True)
    ax.axhline(0, color="#555555", linewidth=0.8)

    # Q 允许为负，纵轴下限随实际结果调整。
    observed = [
        row[f"{method}_{metric}"]
        for row in records
        for method in methods
    ]

    lower = min(0.0, float(np.min(means - stds)), min(observed))
    upper = max(0.0, float(np.max(means + stds)), max(observed))
    span = max(upper - lower, 0.1)

    if metric == "nmi":
        # NMI 使用包含 0 到 1 的坐标范围。
        ax.set_ylim(min(0.0, lower - 0.02), max(1.05, upper + 0.08))
    else:
        ax.set_ylim(
            lower - 0.08 * span if lower < 0 else 0,
            upper + 0.22 * span,
        )

    for position, method in enumerate(methods):
        method_values = [
            row[f"{method}_{metric}"]
            for row in records
        ]

        label_y = max(
            means[position] + stds[position],
            max(method_values),
        )

        ax.annotate(
            f"{means[position]:.4f}",
            xy=(position, label_y),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            fontsize=10,
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

fig.suptitle(
    "Mean ± sample SD across 5 seeds; dots show individual runs",
    fontsize=11,
)

output_path = FIGURE_DIR / "metrics_comparison.png"

fig.savefig(
    output_path,
    dpi=300,
    facecolor="white",
)

plt.close(fig)

print(f"对比图已生成：{output_path}")