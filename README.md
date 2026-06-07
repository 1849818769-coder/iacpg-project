# IACPG Artifact

IACPG is an interrupt-aware extension of Code Property Graphs (CPGs) for diagnosing concurrency defects in embedded interrupt-driven C programs. It enriches a standard CPG with interrupt-specific facts and overlay edges, including ISR roles, masking scopes, preemption relationships, and cross-context shared accesses. The released workflow uses Claude Code skills as a structured diagnostic verifier over the generated IACPG evidence.

This repository contains the code, dataset, Claude Code skills, scripts, and result snapshots used for the submitted IACPG paper.

中文版说明见 [README_zh.md](README_zh.md).

## Repository Layout

```text
.
├── ice_core/                  # Static interrupt fact extraction and IACPG construction support
├── scripts/                   # Build, evaluation, baseline, and reproducibility scripts
├── .claude/skills/            # Claude Code workflows for IACPG and CPG-only diagnosis
├── testfiles/MiBench/         # 96 benchmark instances and meta labels
├── results/                   # Paper result snapshots and ablation summaries
├── paper/new_paper/           # LaTeX source used for the submitted paper variant
├── docs/                      # Dataset and reproducibility notes
├── mcp_server.py              # MCP server exposing IACPG/Joern query tools to Claude Code
└── environment.yml            # Original Conda environment snapshot
```

Generated analysis outputs such as `improved_interrupt_analysis/`, Joern exports, tool-call logs, and caches are intentionally not committed. They can be regenerated from the source benchmarks.

## Requirements

The artifact was developed and tested in WSL/Linux with:

- Python 3.11.
- Joern CLI for CPG import/export.
- Java 17 for Joern.
- Claude Code CLI for the skill-based diagnosis workflow.
- An Anthropic-compatible LLM endpoint for Claude Code.

The scripts assume the project root is on `PYTHONPATH`. The helper wrapper `scripts/with_local_env.sh` is provided for the author's local micromamba layout under `$HOME/.local/iacpg`. If your environment is different, either adapt the wrapper or export the variables manually:

```bash
export PYTHONPATH="$PWD:$PYTHONPATH"
export JOERN_HOME=/path/to/joern-cli
export JAVA_HOME=/path/to/jdk-17
export PATH="$JOERN_HOME:$JAVA_HOME/bin:$PATH"
```

Python dependencies can be installed from the lightweight requirement list:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For an exact snapshot of the original research environment, see `environment.yml`.

## Quick Start

Run a single IACPG build on one benchmark case:

```bash
bash scripts/with_local_env.sh python scripts/build_iacpg.py \
  testfiles/MiBench/AtomicityViolation/simple_001/arm
```

Run the Claude Code IACPG diagnosis workflow:

```bash
export ANTHROPIC_BASE_URL="https://your-anthropic-compatible-endpoint"
export ANTHROPIC_AUTH_TOKEN="your_api_key"
export ANTHROPIC_MODEL="MiniMax-M2.7"

bash scripts/run_case_claude.sh \
  testfiles/MiBench/AtomicityViolation/simple_001/arm
```

Run the CPG-only baseline workflow:

```bash
bash scripts/run_case_claude.sh \
  testfiles/MiBench/AtomicityViolation/simple_001/arm cpg
```

The workflows write generated outputs under each case directory, for example:

```text
testfiles/MiBench/AtomicityViolation/simple_001/arm/improved_interrupt_analysis/
```

## Reproducing Paper Metrics

Evaluate semantic extraction accuracy:

```bash
bash scripts/with_local_env.sh python scripts/eval_rq1.py \
  --output results/rq1_reproduced.json
```

Evaluate query and evidence metrics:

```bash
bash scripts/with_local_env.sh python scripts/eval_rq2.py \
  --output results/rq2_reproduced.json
```

Evaluate end-to-end defect diagnosis:

```bash
bash scripts/with_local_env.sh python scripts/eval_rq3.py \
  --output results/rq3_reproduced.json
```

The committed `results/` directory includes the snapshots used in the paper, including extraction ablations and the IACPG static-checker ablation.

More details are in [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## Dataset

The benchmark is under `testfiles/MiBench/` and contains four defect families across four ISAs:

- Atomicity Violation.
- Interrupt-aware Buffer Overflow / Array OOB.
- Interrupt-aware Divide-by-Zero.
- Multi-word Data Race.

Each instance has a source file and a YAML meta label under the corresponding `meta/` directory. See [docs/DATASET.md](docs/DATASET.md) for source and label details.

## Claude Code Skills

The release includes two project skills:

- `.claude/skills/defect-detection/SKILL.md`: IACPG-based diagnosis.
- `.claude/skills/defect-detection-cpg/SKILL.md`: CPG-only baseline diagnosis.

These skills call the tools exposed by `mcp_server.py`. They are intended to be used through Claude Code or the provided shell wrapper.

## Notes

- SpecChecker-Int is not bundled because it is an external tool; scripts for running it are included for reproducibility.
- API keys, local Claude settings, generated workspaces, and raw tool-call logs are excluded.
- This repository is an artifact release for research reproduction, not a polished end-user product.
