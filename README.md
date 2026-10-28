# 基于邮件网络的社区发现

本项目是“数据科学与知识工程”课程实验，使用真实机构邮件网络，对比 **Louvain 社区发现**与**基于邻接矩阵特征的 K-means 聚类**。研究的问题是：仅依据成员之间的邮件联系，能否发现结构紧密、并与真实部门具有一定对应关系的群体？

项目包含数据清洗、五次重复分组、Q 与 NMI 评价、结果绘图及代表性社区分析。运行结果可用于课程报告和 10 分钟答辩；Word 报告与 PPT 的编写不属于脚本自动生成范围。

## 数据与建模

数据来自 [Stanford SNAP email-Eu-core](https://snap.stanford.edu/data/email-Eu-core.html)，描述一家欧洲研究机构的匿名内部邮件联系。

| 文件 | 每行含义 | 用途 |
| --- | --- | --- |
| `email-Eu-core.txt` | `发送者编号 接收者编号` | 构建网络 |
| `email-Eu-core-department-labels.txt` | `成员编号 部门编号` | 分组完成后的评价与案例分析 |

原始数据有 1,005 个节点、25,571 条有向联系和 42 个部门。每条边表示至少发送过一封邮件，不表示邮件次数。真实部门标签不参与算法分组。

处理流程为：检查编号和标签 → 删除重复有向记录与自环 → 将双向联系合并为无向边 → 选取最大连通分量 → 保存固定节点顺序及对应标签。

当前处理结果：删除 642 条自环，将反向联系合并后得到 16,064 条无向边；排除 19 个孤立节点，最终保留 **986 个节点、16,064 条边和 42 个部门**，节点保留比例为 98.11%。

## 项目结构

```text
email-community-experiment/
├── README.md
├── run_all.sh                    # 一键运行五个实验阶段
├── requirements.txt             # 当前实验的直接依赖版本
├── .venv/                       # 本机 Python 环境，不应跨系统复制
├── data/
│   ├── raw/                     # 原始压缩包和解压后的文本
│   └── processed/               # 清洗后的边、节点顺序、标签及排除节点
├── notes/
│   └── 数据说明.md
├── src/
│   ├── prepare_data.py          # 清洗数据并构建分析网络
│   ├── run_clustering.py        # Louvain 与 K-means 配对运行
│   ├── evaluate_clustering.py   # 计算 Q、NMI 及汇总统计
│   ├── plot_metrics.py          # 生成指标对比图
│   └── analyze_community.py     # 最大社区分析与网络绘图
└── results/
    ├── preprocess_stats.json
    ├── clustering/              # 每个种子的分组与实验参数
    ├── evaluation/              # 每次指标、均值、标准差和报告表格
    ├── case_study/              # 案例成员及部门构成
    ├── figures/                 # 三张报告图片
    └── logs/                    # 一键脚本生成的运行日志
```

## 环境准备

已有结果记录的环境为 Python 3.13.13、NetworkX 3.7、NumPy 2.5.4、scikit-learn 1.9.1、Matplotlib 3.11.2。`requirements.txt` 固定这些直接依赖；pip 会安装其传递依赖。这不是所有底层依赖的完整锁定文件，不同平台或底层库仍可能影响数值与图形布局。

### Windows

在项目根目录的 PowerShell 中执行。已有可用 `.venv` 时，跳过创建命令：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如果只有 `py` 命令可用，将第一行改为 `py -m venv .venv`。

一键脚本需要 **Bash**。Windows 可使用 Git for Windows 附带的 Git Bash；不要用 PowerShell 的语法解释 `.sh` 文件。WSL 属于独立的 Linux 环境，应按 Linux 步骤重新创建环境，不复用 Windows 的 `.venv`。

### Linux 或 macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

如果指定版本无法安装，先检查 Python 版本、平台支持及 pip 的具体报错；不要为了让安装通过而直接升级所有依赖。修改依赖版本后，应重新运行并记录实际结果。

## 原始数据准备

运行前确认以下两个非空文件存在：

```text
data/raw/email-Eu-core.txt
data/raw/email-Eu-core-department-labels.txt
```

如果项目中已经包含它们，可直接运行。否则在项目根目录的 Bash 中下载并解压：

```bash
mkdir -p data/raw
curl -fL --retry 3 https://snap.stanford.edu/data/email-Eu-core.txt.gz \
  -o data/raw/email-Eu-core.txt.gz
curl -fL --retry 3 https://snap.stanford.edu/data/email-Eu-core-department-labels.txt.gz \
  -o data/raw/email-Eu-core-department-labels.txt.gz
gzip -dc data/raw/email-Eu-core.txt.gz > data/raw/email-Eu-core.txt
gzip -dc data/raw/email-Eu-core-department-labels.txt.gz > data/raw/email-Eu-core-department-labels.txt
```

也可以从官方页面手动下载并解压到上述位置。保留 `.gz` 原件；不要通过修改扩展名代替解压。下载和解压命令会覆盖对应文件，仅在准备原始数据时执行。

## 一键运行

在项目根目录的 **Git Bash 或其他 Bash 终端**中执行：

```bash
# 只检查数据文件、Python 和库，不运行实验
bash run_all.sh --check

# 按顺序运行全部五个阶段
bash run_all.sh
```

Windows 用户也可以在 PowerShell 中显式调用 Git Bash（如果 Git 安装在其他位置，请修改路径）：

```powershell
& 'C:\Program Files\Git\bin\bash.exe' ./run_all.sh --check
& 'C:\Program Files\Git\bin\bash.exe' ./run_all.sh
```

脚本优先使用项目的 `.venv/bin/python`，或在 Git Bash 下使用 `.venv/Scripts/python.exe`；找不到项目环境时才尝试 PATH 中的 `python3`、`python`。也可以显式指定解释器：

```bash
bash run_all.sh --python '.venv/Scripts/python.exe' --check
bash run_all.sh --python '/path/to/python'
bash run_all.sh --help
```

`--python` 只接收可执行文件路径或命令名，不接收附加参数；相对路径以项目根目录为基准。脚本会自动定位自身所在目录，因此也支持从其他工作目录使用脚本完整路径调用。请用 `bash run_all.sh`，不要用 `sh run_all.sh`。

脚本会：

1. 检查两个原始文本、五个 Python 文件及所需库。
2. 顺序执行预处理、分组、评价、指标绘图、案例分析。
3. 将各阶段输出同时显示在终端并保存到 `results/logs/`，日志文件名时间为 UTC。
4. 某个阶段返回非零退出码时立即停止，不继续运行后续阶段。

运行会覆盖 `data/processed/` 和 `results/` 中同名的生成文件，原始数据保持不变。中途失败可能留下本次的部分结果与上次的后续结果，因此只有看到 `All 5 stages completed.` 才表示本次完整结束。需要保留旧实验时，请先另行备份生成结果。脚本不会自动安装依赖或下载数据。

## 单独运行某个阶段

Windows PowerShell 中，按依赖顺序执行：

```powershell
.\.venv\Scripts\python.exe src/prepare_data.py
.\.venv\Scripts\python.exe src/run_clustering.py
.\.venv\Scripts\python.exe src/evaluate_clustering.py
.\.venv\Scripts\python.exe src/plot_metrics.py
.\.venv\Scripts\python.exe src/analyze_community.py
```

Linux/macOS 将解释器路径换成 `.venv/bin/python`。仅修改绘图样式时可单独运行对应绘图脚本；修改数据或分组参数后，应重新运行所有受影响的下游阶段。

## 实验设置

| 项目 | 设置 |
| --- | --- |
| 分析图 | 最大连通分量，无向、无权、无自环 |
| 重复实验 | 随机种子 0、1、2、3、4 |
| Louvain | resolution=1.0，threshold=1e-7，weight=None |
| K-means 特征 | 固定节点顺序的二值邻接矩阵行，不标准化、不降维 |
| K-means 组数 | 同次 Louvain 发现的社区数量 |
| K-means 其他参数 | k-means++，n_init=10，max_iter=300，tol=1e-4，algorithm=lloyd |
| 模块度 Q | 同一分析图，resolution=1.0，weight=None |
| NMI | 算法分组与真实部门，average_method=arithmetic |
| 汇总 | 五次均值与样本标准差，ddof=1 |
| 案例选择 | seed=0 的最大 Louvain 社区；并列时选编号较小者 |
| 网络布局 | spring_layout，seed=42，iterations=80，method=force |

核心参数位于 `src/run_clustering.py`、`src/evaluate_clustering.py` 和 `src/analyze_community.py` 顶部。修改实验种子时应同步修改分组与评价脚本，保证案例种子有对应结果。改变 Louvain 分辨率时，需明确区分算法目标参数与评价口径，不能混用不同定义的 Q 直接比较。

## 当前实验结果

下表来自项目已有的 `results/evaluation/summary_metrics.json`，显示为四位小数。它是当前实验记录，不是脚本必须达到的预设答案；重新运行后的实际输出为准。

| 方法 | Q 均值 ± 样本标准差 | NMI 均值 ± 样本标准差 |
| --- | --- | --- |
| K-means | 0.2215 ± 0.0124 | 0.2767 ± 0.0290 |
| Louvain | 0.4148 ± 0.0023 | 0.5796 ± 0.0177 |

在当前设置下，Louvain 在两项指标上均表现更好，且五次指标波动更小。它发现 7—8 个社区，少于真实的 42 个部门。seed=0 的最大社区编号为 3，含 250 名成员，涉及 29 个部门，说明该案例不能直接等同于一个正式部门。

解释结果时注意：Q 不是准确率；NMI=0.5796 也不代表 57.96% 的成员被正确分类。误差线表示样本标准差，不是置信区间。部门混合可能与跨部门通信或算法划分粒度有关，不能据此断言识别出了真实项目团队。结论限于当前数据和基线特征设计。

## 报告材料在哪里

| 材料 | 文件 |
| --- | --- |
| 数据清洗统计 | `results/preprocess_stats.json` |
| 每个成员的分组 | `results/clustering/seed_*_assignments.txt` |
| 实验环境和算法参数 | `results/clustering/experiment_config.json` |
| 五次指标和汇总表 | `results/evaluation/report_tables.txt` |
| 完整精度的逐次指标与汇总 | `results/evaluation/per_seed_metrics.json`、`summary_metrics.json` |
| 图 1 网络示意图 | `results/figures/analysis_network.png` |
| 图 2 指标对比图 | `results/figures/metrics_comparison.png` |
| 图 3 案例部门构成 | `results/figures/largest_community_departments.png` |
| 案例分析文本 | `results/case_study/case_report.txt` |

## 常见问题

- **提示找不到原始文件**：确认已经解压为 `.txt` 并放在 `data/raw/`，只有 `.gz` 不够。
- **提示库不存在**：用脚本实际选中的解释器执行 `-m pip install -r requirements.txt`，避免装到另一个环境。
- **出现 `$'\r'` 等 Bash 错误**：将 `run_all.sh` 保存为 UTF-8、LF 换行，不使用 CRLF。
- **虚拟环境无法启动**：检查创建它的 Python 是否还在原位置。项目移动或更换操作系统后应重新创建环境。
- **网络图阶段耗时较长**：最后一步会计算 986 个节点的布局，期间等待即可；可从日志检查正在运行的阶段。
- **结果与表中略有不同**：先核对数据、节点顺序、参数和软件版本。记录实际结果，不修改数据以迎合参考数值。

## 参考资料

- [Stanford SNAP 数据集与原始研究引用](https://snap.stanford.edu/data/email-Eu-core.html)
- [NetworkX Louvain 接口](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.louvain.louvain_communities.html)
- [scikit-learn K-means 接口](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html)
- [NetworkX 模块度](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.quality.modularity.html)
- [scikit-learn NMI](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.normalized_mutual_info_score.html)
