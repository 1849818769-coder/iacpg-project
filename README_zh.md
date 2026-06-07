# IACPG 项目说明

IACPG 是面向嵌入式中断驱动 C 程序的中断感知代码属性图（Code Property Graph, CPG）扩展。它在标准 CPG 之上加入 ISR 角色、中断屏蔽范围、抢占关系和跨上下文共享访问等语义事实与图边，用于支持中断并发缺陷的结构化诊断。

本仓库是 IACPG 小论文对应的公开 artifact，包含核心代码、数据集、Claude Code skills、复现实验脚本和结果快照。

## 目录结构

```text
.
├── ice_core/                  # 中断语义提取与 IACPG 构建核心代码
├── scripts/                   # 构建、评测、基线和消融实验脚本
├── .claude/skills/            # Claude Code 缺陷诊断工作流
├── testfiles/MiBench/         # 96 个跨 ISA benchmark 用例和 YAML 标签
├── results/                   # 论文结果快照和消融实验结果
├── paper/new_paper/           # 投稿版本 LaTeX 源码片段
├── docs/                      # 数据集和复现实验说明
├── mcp_server.py              # 提供 IACPG/Joern 查询工具的 MCP server
└── environment.yml            # 原始 Conda 环境快照
```

仓库中不包含每个用例的生成产物，例如 `improved_interrupt_analysis/`、Joern graph export、工具调用日志和缓存。这些文件可以通过脚本重新生成。

## 环境要求

建议环境：

- Python 3.11。
- Joern CLI。
- Java 17。
- Claude Code CLI。
- 一个 Anthropic-compatible 的 LLM API endpoint。

如果使用作者本地环境布局，可以直接使用：

```bash
bash scripts/with_local_env.sh python <script.py> [args...]
```

如果你的环境不同，可以手动设置：

```bash
export PYTHONPATH="$PWD:$PYTHONPATH"
export JOERN_HOME=/path/to/joern-cli
export JAVA_HOME=/path/to/jdk-17
export PATH="$JOERN_HOME:$JAVA_HOME/bin:$PATH"
```

安装 Python 依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

如需尽量复现作者环境，可参考 `environment.yml`。

## 快速运行

构建单个用例的 IACPG：

```bash
bash scripts/with_local_env.sh python scripts/build_iacpg.py \
  testfiles/MiBench/AtomicityViolation/simple_001/arm
```

运行 IACPG + Claude Code skill 诊断：

```bash
export ANTHROPIC_BASE_URL="https://your-anthropic-compatible-endpoint"
export ANTHROPIC_AUTH_TOKEN="your_api_key"
export ANTHROPIC_MODEL="MiniMax-M2.7"

bash scripts/run_case_claude.sh \
  testfiles/MiBench/AtomicityViolation/simple_001/arm
```

运行 CPG-only 基线：

```bash
bash scripts/run_case_claude.sh \
  testfiles/MiBench/AtomicityViolation/simple_001/arm cpg
```

运行后，每个用例的结果会写入对应目录下的：

```text
improved_interrupt_analysis/
```

## 复现实验结果

RQ1，中断语义提取精度：

```bash
bash scripts/with_local_env.sh python scripts/eval_rq1.py \
  --output results/rq1_reproduced.json
```

RQ2，查询效率和证据质量：

```bash
bash scripts/with_local_env.sh python scripts/eval_rq2.py \
  --output results/rq2_reproduced.json
```

RQ3，端到端缺陷诊断效果：

```bash
bash scripts/with_local_env.sh python scripts/eval_rq3.py \
  --output results/rq3_reproduced.json
```

更多说明见 [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md)。

## 数据集

数据集位于 `testfiles/MiBench/`，覆盖四类中断并发相关缺陷：

- Atomicity Violation。
- Interrupt-aware Buffer Overflow / Array OOB。
- Interrupt-aware Divide-by-Zero。
- Multi-word Data Race。

每个用例包含 C 源文件和对应的 YAML meta 标签。数据来源和标签格式见 [docs/DATASET.md](docs/DATASET.md)。

## Claude Code Skills

本项目使用 Claude Code 的 project skill 作为结构化诊断验证器：

- `.claude/skills/defect-detection/SKILL.md`：IACPG 版本。
- `.claude/skills/defect-detection-cpg/SKILL.md`：CPG-only 基线版本。

这些 skill 会调用 `mcp_server.py` 暴露的工具。请注意，Codex 或普通 Python 程序不会自动触发这些 skill，必须通过 Claude Code 或对应 wrapper 调用。

## 打包 MCP Server

如果不想在 Claude Code MCP 配置中直接写 `python mcp_server.py`，可以用 PyInstaller 打包成可执行文件，然后在 MCP 配置里引用这个可执行文件：

```bash
python -m PyInstaller --clean --noconfirm packaging/iacpg_mcp.spec
```

Windows 需要在 Windows Python 下打包，生成 `dist\\iacpg-mcp\\iacpg-mcp.exe`；Linux/WSL 下会生成 Linux 可执行文件。详细说明见 [docs/PACKAGING.md](docs/PACKAGING.md)，配置模板见 `config/`。

为了方便使用，仓库中也提供了 Windows 打包产物 `packaged/iacpg-mcp-windows.zip`。这个包只包含 MCP server、Python 依赖、`ice_core/` 和 `scripts/`，不包含 Joern 或 Java。所有依赖 Joern 的工具仍然要求在同一个运行环境中配置好 Joern。论文实验使用的是 Linux/WSL + 外部 Joern 的脚本工作流，这仍然是推荐的复现方式。

## 注意事项

- 本仓库不包含 SpecChecker-Int 工具本体，只保留了运行脚本。
- 本仓库不包含 Joern 和 Java，需要通过 `JOERN_HOME`、`JAVA_HOME` 和 `PATH` 单独配置。
- API key、本地 Claude 配置、生成 workspace 和原始工具调用日志均已排除。
- 本仓库用于论文复现和研究参考，不是面向终端用户的完整产品。
