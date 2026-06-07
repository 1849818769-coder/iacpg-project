# Reproducibility Guide

This document summarizes the main artifact workflows.

## 1. Build IACPG For One Case

```bash
bash scripts/with_local_env.sh python scripts/build_iacpg.py \
  testfiles/MiBench/AtomicityViolation/simple_001/arm
```

Expected generated directory:

```text
testfiles/MiBench/AtomicityViolation/simple_001/arm/improved_interrupt_analysis/
```

## 2. Run Claude Code Diagnosis

IACPG mode:

```bash
bash scripts/run_case_claude.sh \
  testfiles/MiBench/AtomicityViolation/simple_001/arm
```

CPG-only mode:

```bash
bash scripts/run_case_claude.sh \
  testfiles/MiBench/AtomicityViolation/simple_001/arm cpg
```

The IACPG skill is stored in `.claude/skills/defect-detection/`.
The CPG-only baseline skill is stored in `.claude/skills/defect-detection-cpg/`.

## 3. Batch Runs

The repository includes batch scripts used during the paper experiments:

```bash
bash scripts/batch_run_claude.sh
```

Before running large batches, check the script parameters and make sure your LLM API endpoint and Joern environment are configured.

## 4. Evaluation Scripts

RQ1:

```bash
bash scripts/with_local_env.sh python scripts/eval_rq1.py \
  --output results/rq1_reproduced.json
```

RQ2:

```bash
bash scripts/with_local_env.sh python scripts/eval_rq2.py \
  --output results/rq2_reproduced.json
```

RQ3:

```bash
bash scripts/with_local_env.sh python scripts/eval_rq3.py \
  --output results/rq3_reproduced.json
```

## 5. Result Snapshots

The `results/` directory contains paper result snapshots:

- `rq1.json`: semantic extraction metrics.
- `rq1_llm.json`: pure-LLM extraction baseline.
- `rq2.json`: query/evidence metrics.
- `rq3.json`: end-to-end diagnosis metrics.
- `rq1_extraction_ablation_ark_20260516_135113/`: extraction-layer ablation.
- `iacpg_static_checker_20260516_160502/`: static-checker ablation.
- `rq3_hybrid_claude_rerun_20260516_160218/`: selected hybrid rerun summary.

Raw logs and generated per-case artifacts are not committed to keep the repository compact.
