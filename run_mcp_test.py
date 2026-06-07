import sys
import json
from mcp_server import (
    interrupt_analyze,
    build_interrupt_facts,
    build_iacpg,
    iacpg_summary,
    iacpg_preemptions,
    iacpg_switches,
    iacpg_variable
)

path = "/home/rainyu/Study/Project/Python/AGENT_OPENCODE/iacpg/testfiles/MIBench/dataset/easy/easy_001_arm"

print("--- Stage 1 ---")
print(json.dumps(interrupt_analyze(path, "static"), indent=2))
print("--- Stage 2 ---")
print(json.dumps(build_interrupt_facts(path), indent=2))
print("--- Stage 3 ---")
print(json.dumps(build_iacpg(path), indent=2))
print("--- Stage 4 Summary ---")
print(json.dumps(iacpg_summary(path), indent=2))
print("--- Stage 4 Preemptions ---")
print(json.dumps(iacpg_preemptions(path), indent=2))
print("--- Stage 4 Switches ---")
print(json.dumps(iacpg_switches(path), indent=2))

