#!/usr/bin/env python3
"""Run Stage 1 analysis for a single case with optional custom output dir."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run Stage 1 analysis for one case.")
    parser.add_argument("--project-path", required=True, help="Case directory containing source files.")
    parser.add_argument("--output-dir", required=True, help="Directory for improved_interrupt_analysis outputs.")
    parser.add_argument("--mode", choices=["static", "agent"], default="static")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    project_path = str(Path(args.project_path).resolve())
    output_dir = str(Path(args.output_dir).resolve())

    if args.mode == "agent":
        from ice_core.static_analysis.agent_analyzer import ImprovedInterruptModelAnalyzer
    else:
        from ice_core.static_analysis.analyzer import ImprovedInterruptModelAnalyzer

    analyzer = ImprovedInterruptModelAnalyzer(project_path, output_dir=output_dir)
    result = analyzer.analyze_project(debug_mode=args.debug)
    print(
        json.dumps(
            {
                "status": "ok",
                "project_path": project_path,
                "output_dir": output_dir,
                "mode": args.mode,
                "functions": {
                    "interrupt": len(result.get("functions", {}).get("interrupt_functions", [])),
                    "main": len(result.get("functions", {}).get("main_functions", [])),
                    "regular": len(result.get("functions", {}).get("regular_functions", [])),
                },
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
