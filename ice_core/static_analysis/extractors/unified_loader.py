import os
import yaml
from functools import lru_cache
from typing import List, Tuple

@lru_cache(maxsize=1)
def load_patterns() -> Tuple[List[str], List[tuple], List[tuple], List[tuple], str, str]:
    """Load interrupt parsing patterns from YAML file."""
    # 获取 ice_core 目录的路径 (当前文件在 ice_core/static_analysis/extractors 下，向上跳两层)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ice_core_dir = os.path.dirname(os.path.dirname(current_dir))
    yaml_path = os.environ.get("INTERRUPT_INFO_YAML_PATH") or os.path.join(
        ice_core_dir, "knowledge_base", "interrupt_info.yml"
    )
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"interrupt rule YAML not found: {yaml_path}")
    
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    function_pattern_entries = [
        (p["pattern"], p.get("arch", "Generic"))
        for p in data.get("interrupt_function_patterns", [])
    ]
    function_patterns = [pattern for pattern, _ in function_pattern_entries]
    
    switch_patterns = [
        (p["pattern"], p["operation"], p["arch"], p["has_target"])
        for p in data.get("interrupt_switch_patterns", [])
    ]
    
    priority_patterns = [
        (p["pattern"], p["source_type"], p["arch"])
        for p in data.get("interrupt_priority_patterns", [])
    ]
    
    run_tasks_re = data.get("run_comment_patterns", {}).get("tasks", r'-tasks=([\w,]+)')
    run_priority_re = data.get("run_comment_patterns", {}).get("priority", r'-priority=([\d,]+)')
    
    return function_patterns, function_pattern_entries, switch_patterns, priority_patterns, run_tasks_re, run_priority_re

INTERRUPT_FUNCTION_PATTERNS, INTERRUPT_FUNCTION_PATTERN_ENTRIES, INTERRUPT_SWITCH_PATTERNS, INTERRUPT_PRIORITY_PATTERNS, _RUN_TASKS_RE, _RUN_PRIORITY_RE = load_patterns()
