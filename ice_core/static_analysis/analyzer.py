import os
import re
import json
import shutil
import sys
import os

# Add project root (the directory containing ice_core) to sys.path
# File: .../ice/ice_core/analysis/analyzer.py
# Dir:  .../ice/ice_core/analysis
# ../   .../ice/ice_core
# ../.. .../ice
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from ice_core.utils.ast_parser import CodeAnalyzer
from datetime import datetime
import chardet

from ice_core.static_analysis.extractors.shared_var import SharedVariableExtractor
from ice_core.static_analysis.extractors.operations import VariableOperationExtractor
from ice_core.static_analysis.extractors.calls import FunctionCallExtractor
from ice_core.static_analysis.extractors.globals import GlobalVariableExtractor
from ice_core.static_analysis.extractors.llm_interrupt_agent import InterruptInfoAgent
from ice_core.static_analysis.extractors.unified_parser import UnifiedInterruptParser, INTERRUPT_FUNCTION_PATTERNS, MAIN_FUNCTION_PATTERNS, REGULAR_FUNCTION_PATTERNS
class ImprovedInterruptModelAnalyzer:
    """改进版中断建模分析器 - 实现6个核心功能"""
    
    def __init__(self, project_path: str, output_dir: Optional[str] = None):
        self.project_path = project_path
        self.code_analyzer = CodeAnalyzer(project_path)
        
        # 存储路径配置
        self.output_path = output_dir or os.path.join(project_path, "improved_interrupt_analysis")
        os.makedirs(self.output_path, exist_ok=True)
        
        # 初始化各个提取器（它们自己定义模式）
        self.global_variable_extractor = GlobalVariableExtractor()
        
        # 从各个子模块获取模式
        self._init_patterns_from_modules()
        
        # 初始化需要模式参数的提取器
        self.variable_operation_extractor = VariableOperationExtractor(
            self.global_variable_extractor,
            self.interrupt_function_patterns,
            self.main_function_patterns,
            self.regular_function_patterns
        )
        
        self.function_call_extractor = FunctionCallExtractor(
            self.interrupt_function_patterns,
            self.main_function_patterns,
            self.regular_function_patterns
        )
        
        # 存储分析结果
        self.analysis_results = {}
    
    def _init_patterns_from_modules(self):
        """从各个子模块获取匹配模式"""
        self.interrupt_function_patterns = INTERRUPT_FUNCTION_PATTERNS
        self.main_function_patterns = MAIN_FUNCTION_PATTERNS
        self.regular_function_patterns = REGULAR_FUNCTION_PATTERNS
        self.interrupt_switch_patterns = []
        self.interrupt_priority_patterns = []
    
    def analyze_project(self, debug_mode: bool = False) -> Dict[str, Any]:
        """分析整个项目，实现5个核心功能"""
        print(f"开始分析项目: {self.project_path}")
        
        # 清理输出目录
        if os.path.exists(self.output_path):
            shutil.rmtree(self.output_path)
        os.makedirs(self.output_path, exist_ok=True)
        
        # 初始化结果结构
        self.analysis_results = {
            "project_info": {
                "project_path": self.project_path,
                "total_files": 0,
                "analyzed_files": []
            },
            "functions": {
                "interrupt_functions": [],
                "main_functions": [],
                "regular_functions": []
            },
            "function_call_relations": [],
            "shared_variables": [],
            "global_variables": [],
            "interrupt_priorities": {},
            "interrupt_switches": [],
            "variable_operations": [],
            "file_details": {}
        }
        
        # 遍历项目文件
        for root, dirs, files in os.walk(self.project_path):
            if debug_mode:
                print(f"搜索目录: {root}")
            
            for file in files:
                if file.endswith(('.c', '.h')):
                    file_path = os.path.join(root, file)
                    print(f"  分析文件: {file_path}")
                    
                    try:
                        # 分析单个文件
                        file_result = self._analyze_single_file(file_path, debug_mode)
                        
                        # 合并结果
                        self._merge_file_results(file_result)
                        
                        # 存储文件详情
                        if "file_details" not in self.analysis_results:
                            self.analysis_results["file_details"] = {}
                        self.analysis_results["file_details"][file_path] = file_result
                        self.analysis_results["project_info"]["analyzed_files"].append(file_path)
                        self.analysis_results["project_info"]["total_files"] += 1
                        
                        if debug_mode:
                            print(f"    中断函数: {len(file_result['interrupt_functions'])}")
                            print(f"    主函数: {len(file_result['main_functions'])}")
                            print(f"    普通函数: {len(file_result['regular_functions'])}")
                            print(f"    全局变量: {len(file_result['global_variables'])}")
                            
                    except Exception as e:
                        print(f"  分析文件 {file_path} 时出错: {e}")
                        if debug_mode:
                            import traceback
                            traceback.print_exc()
        
        # 后处理：构建完整的关系图
        self._post_process_analysis()
        
        # 保存分析结果
        self._save_analysis_results()
        
        # 生成全局JSON
        # self._generate_global_json()
        
        print(f"分析完成！结果保存到: {self.output_path}")
        return self.analysis_results 

    def _analyze_single_file(self, file_path: str, debug_mode: bool = False) -> Dict[str, Any]:
        """分析单个文件"""
        
        # 检测文件编码
        encoding = self._detect_encoding(file_path)
        
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            content = f.read()
        
        result = {
            "file_path": file_path,
            "interrupt_functions": [],
            "main_functions": [],
            "regular_functions": [],
            "global_variables": [],
            "function_calls": [],
            "interrupt_switches": [],
            "variable_operations": [],
            "func_names": []
        }
        
        ast_functions = None
        # 使用CodeAnalyzer分析代码结构
        try:
            code_result, call_relations, func_names = self.code_analyzer.analyze_file(
                file_path, "temp_interrupt_analysis"
            )
            
            result["func_names"] = func_names
            
            if code_result and isinstance(code_result, list) and len(code_result) > 0:
                ast_dict = code_result[0]
                if isinstance(ast_dict, dict) and "function" in ast_dict:
                    ast_functions = ast_dict["function"].get("content", [])
            
            # 清理临时文件
            temp_dir = os.path.join(self.project_path, "temp_interrupt_analysis")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
        except Exception as e:
            if debug_mode:
                print(f"    使用CodeAnalyzer分析时出错: {e}")
            result["func_names"] = []
        
        # 1. 识别函数类型（一次解析，统一输出）
        static_functions = UnifiedInterruptParser.extract_static_functions(content, file_path, ast_functions)
        result["interrupt_functions"] = static_functions["interrupt_functions"]
        result["main_functions"]      = static_functions["main_functions"]
        result["regular_functions"]   = static_functions["regular_functions"]
        
        # 2. 提取全局变量
        result["global_variables"] = self._extract_global_variables(content, file_path)
        
        # 3. 提取函数调用关系
        result["function_calls"] = self._extract_function_calls(content, file_path)
        
        # 4. 提取中断开关
        result["interrupt_switches"] = self._extract_interrupt_switches(content, file_path)
        
        # 5. 提取变量读写操作
        result["variable_operations"] = self._extract_variable_operations(content, file_path)
        
        return result
    
    def _extract_global_variables(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """提取全局变量（使用新的API）"""
        return self.global_variable_extractor.extract_global_variables(content, file_path)
    
    def _extract_function_calls(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """提取函数调用关系（使用新的API）"""
        return self.function_call_extractor.extract_function_calls(content, file_path)
    
    def _extract_interrupt_switches(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """提取中断开关操作（静态正则扫描）"""
        return UnifiedInterruptParser.extract_static_switches(content, file_path)
    
    def _extract_variable_operations(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """提取变量读写操作（使用新的API）"""
        return self.variable_operation_extractor.extract_variable_operations(content, file_path)
    
    def _merge_file_results(self, file_result: Dict[str, Any]):
        """合并文件分析结果"""
        # 确保functions字典存在
        if "functions" not in self.analysis_results:
            self.analysis_results["functions"] = {
                "interrupt_functions": [],
                "main_functions": [],
                "regular_functions": []
            }
        
        # 合并函数
        self.analysis_results["functions"]["interrupt_functions"].extend(file_result["interrupt_functions"])
        self.analysis_results["functions"]["main_functions"].extend(file_result["main_functions"])
        self.analysis_results["functions"]["regular_functions"].extend(file_result["regular_functions"])
        
        # 确保其他列表存在
        if "function_call_relations" not in self.analysis_results:
            self.analysis_results["function_call_relations"] = []
        if "interrupt_switches" not in self.analysis_results:
            self.analysis_results["interrupt_switches"] = []
        if "variable_operations" not in self.analysis_results:
            self.analysis_results["variable_operations"] = []
        if "global_variables" not in self.analysis_results:
            self.analysis_results["global_variables"] = []
            
        # 合并函数调用关系
        self.analysis_results["function_call_relations"].extend(file_result["function_calls"])

        # 合并中断开关
        self.analysis_results["interrupt_switches"].extend(file_result["interrupt_switches"])

        # 合并变量操作
        self.analysis_results["variable_operations"].extend(file_result["variable_operations"])

        # 合并全局变量
        self.analysis_results["global_variables"].extend(file_result["global_variables"])
    
    def _post_process_analysis(self):
        """后处理分析结果"""
        # 1. 去重普通函数（移除已经是中断函数的函数）
        self._deduplicate_regular_functions()
        
        # 2. 构建中断优先级
        self._build_interrupt_priorities()
        
        # 3. 识别共享变量
        self._identify_shared_variables()
        
        # 4. 构建函数调用关系图
        self._build_function_call_graph()
        
        # 5. 映射中断开关目标
        self._map_interrupt_switch_targets()
    
    def _map_interrupt_switch_targets(self):
        """将中断开关的 target（中断号或 IRQn 名）映射到具体的 ISR 函数名"""
        interrupt_functions = self.analysis_results.get("functions", {}).get("interrupt_functions", [])

        # 建立两张查找表
        # 1. 中断号（int） → [func_name, ...]
        by_number: dict = {}
        # 2. IRQn 名称关键词 → [func_name, ...]（ARM 风格，如 USART1_IRQn）
        by_irqn: dict = {}

        for func in interrupt_functions:
            name = func["name"]
            num = func.get("interrupt_number")
            if num is not None:
                by_number.setdefault(num, []).append(name)
                by_number.setdefault(str(num), []).append(name)
            # ARM IRQn 关键词：去掉常见后缀后匹配函数名片段
            irqn_key = name.lower().replace("_irqhandler", "").replace("_handler", "")
            by_irqn.setdefault(irqn_key, []).append(name)

        for sw in self.analysis_results.get("interrupt_switches", []):
            target = sw.get("target", "").strip()
            mapped: list = []

            if target == "" or target == "-1":
                # -1 或空 → 全局开关，映射所有 ISR
                mapped = [f["name"] for f in interrupt_functions]
            elif target.lstrip("-").isdigit():
                # 纯数字：按中断号查找
                mapped = by_number.get(int(target), by_number.get(target, []))
            else:
                # 名称（如 USART1_IRQn）：先精确匹配，再做关键词模糊匹配
                target_key = target.lower().replace("_irqn", "").replace("irqn_", "")
                for key, names in by_irqn.items():
                    if target_key in key or key in target_key:
                        mapped.extend(names)

            sw["mapped_targets"] = mapped
            sw["mapped_target_functions"] = mapped
    
    def _build_interrupt_priorities(self):
        """从已识别的中断函数构建优先级表"""
        priorities = {}
        for func in self.analysis_results.get("functions", {}).get("interrupt_functions", []):
            name = func["name"]
            priorities[name] = {
                "function_name":    name,
                "priority":         func.get("priority", 1),
                "type":             "interrupt",
                "source":           "static",
                "interrupt_number": func.get("interrupt_number"),
                "architecture":     func.get("architecture", "Generic"),
                "file_path":        func.get("file_path", ""),
                "line_number":      func.get("line_number", 0),
            }
        self.analysis_results["interrupt_priorities"] = priorities
    
    def _deduplicate_regular_functions(self):
        """去重普通函数，移除已经是中断函数的函数"""
        if "functions" not in self.analysis_results:
            return
        
        # 获取所有中断函数名称
        interrupt_function_names = {func["name"] for func in self.analysis_results["functions"]["interrupt_functions"]}
        
        # 过滤普通函数，移除与中断函数重复的函数
        original_regular_count = len(self.analysis_results["functions"]["regular_functions"])
        self.analysis_results["functions"]["regular_functions"] = [
            func for func in self.analysis_results["functions"]["regular_functions"]
            if func["name"] not in interrupt_function_names
        ]
        
        filtered_regular_count = len(self.analysis_results["functions"]["regular_functions"])
        if original_regular_count != filtered_regular_count:
            print(f"去重完成：从 {original_regular_count} 个普通函数中移除了 {original_regular_count - filtered_regular_count} 个重复的中断函数")
    
    def _identify_shared_variables(self):
        """识别共享变量（使用新的API）"""
        extractor = SharedVariableExtractor(self.analysis_results)
        self.analysis_results["shared_variables"] = extractor.identify_shared_variables()
    
    def _build_function_call_graph(self):
        """构建函数调用关系图"""
        call_graph = {
            "call_relations": self.analysis_results.get("function_call_relations", []),
            "called_relations": [],
            "function_hierarchy": {}
        }
        
        # 构建被调用关系
        callers_map = {}
        for relation in self.analysis_results.get("function_call_relations", []):
            caller = relation.get('caller', '')
            called = relation.get('called', '')
            
            if called not in callers_map:
                callers_map[called] = set()
            callers_map[called].add(caller)
        
        called_relations = []
        for func_name, callers in callers_map.items():
            called_relations.append({
                "func_name": func_name,
                "called_by": list(callers)
            })
        
        call_graph["called_relations"] = called_relations
        
        # 构建函数层次结构
        all_functions = set()
        callers = set()
        callees = set()
        
        for relation in self.analysis_results.get("function_call_relations", []):
            caller = relation.get('caller', '')
            called = relation.get('called', '')
            
            all_functions.add(caller)
            all_functions.add(called)
            callers.add(caller)
            callees.add(called)
        
        call_graph["function_hierarchy"] = {
            "root_functions": list(all_functions - callees),
            "leaf_functions": list(all_functions - callers)
        }
        
        self.analysis_results["function_call_graph"] = call_graph
    
    def _detect_encoding(self, file_path: str) -> str:
        """检测文件编码"""
        try:
            with open(file_path, 'rb') as f:
                result = chardet.detect(f.read(4096))
            return result.get('encoding', 'utf-8') or 'utf-8'
        except:
            return 'utf-8'
    
    def _save_analysis_results(self):
        """保存分析结果到文件"""
        
        # 1. 保存完整结果
        # full_result_file = os.path.join(self.output_path, "complete_analysis.json")
        # with open(full_result_file, 'w', encoding='utf-8') as f:
        #     json.dump(self.analysis_results, f, indent=2, ensure_ascii=False)
        
        # 2. 保存函数列表
        functions_file = os.path.join(self.output_path, "functions.json")
        with open(functions_file, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_results["functions"], f, indent=2, ensure_ascii=False)
        
        # 3. 保存函数调用关系
        call_relations_file = os.path.join(self.output_path, "function_call_relations.json")
        with open(call_relations_file, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_results["function_call_graph"], f, indent=2, ensure_ascii=False)
        
        # 4. 保存共享变量
        shared_vars_file = os.path.join(self.output_path, "shared_variables.json")
        with open(shared_vars_file, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_results["shared_variables"], f, indent=2, ensure_ascii=False)
        
        # 5. 保存中断优先级
        priorities_file = os.path.join(self.output_path, "interrupt_priorities.json")
        with open(priorities_file, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_results["interrupt_priorities"], f, indent=2, ensure_ascii=False)
        
        # 6. 保存中断开关
        switches_file = os.path.join(self.output_path, "interrupt_switches.json")
        with open(switches_file, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_results["interrupt_switches"], f, indent=2, ensure_ascii=False)
        
        # 7. 保存变量操作
        var_ops_file = os.path.join(self.output_path, "variable_operations.json")
        with open(var_ops_file, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_results["variable_operations"], f, indent=2, ensure_ascii=False)
        
        # 8. 全局变量文件路径
        global_vars_file = os.path.join(self.output_path, "global_variables.json")
        with open(global_vars_file, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_results["global_variables"], f, indent=2, ensure_ascii=False)
        
        print(f"\n分析结果已保存:")
        # print(f"  - 完整分析结果: {full_result_file}")
        print(f"  - 函数列表: {functions_file}")
        print(f"  - 函数调用关系: {call_relations_file}")
        print(f"  - 共享变量: {shared_vars_file}")
        print(f"  - 中断优先级: {priorities_file}")
        print(f"  - 中断开关: {switches_file}")
        print(f"  - 变量操作: {var_ops_file}")
        print(f"  - 全局变量: {global_vars_file}")

        
    
    def _generate_global_json(self):
        """生成全局JSON，只包含全局变量信息"""
        print("\n生成全局JSON...")
        
        try:
            # 使用CodeAnalyzer进行全局变量分析
            code_analyzer = CodeAnalyzer(self.project_path)
            
            # 分析所有文件
            all_files = []
            for root, dirs, files in os.walk(self.project_path):
                for file in files:
                    if file.endswith(('.c', '.h')):
                        all_files.append(os.path.join(root, file))
            
            # 收集全局变量信息
            global_variables = []
            
            # 分析每个文件的全局变量
            for file_path in all_files:
                try:
                    # 使用CodeAnalyzer分析文件结构
                    temp_slice_path = "temp_slice"
                    result, call_relations, func_names = code_analyzer.analyze_file(file_path, temp_slice_path)
                    
                    # 清理临时文件
                    temp_dir = os.path.join(self.project_path, temp_slice_path)
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                    
                    # 提取全局变量信息
                    code_structure = result[0]
                    global_vars = code_structure.get("global_variable", {})
                    
                    if global_vars.get("content"):
                        global_variables.append({
                            "path": file_path,
                            "global_variable": {
                                "nums": global_vars.get("nums", 0),
                                "content": global_vars.get("content", [])
                            }
                        })
                    
                except Exception as e:
                    print(f"  分析文件 {file_path} 时出错: {e}")
            
            # 构建简化的全局JSON
            global_analysis = {
                "metadata": {
                    "project_path": self.project_path,
                    "analysis_timestamp": self._get_timestamp(),
                    "total_files": len(all_files),
                    "analyzer_version": "2.0"
                },
                "global_variables": global_variables
            }
            
            # 保存全局JSON
            global_vars_file = os.path.join(self.output_path, "global_variables.json")
            with open(global_vars_file, 'w', encoding='utf-8') as f:
                json.dump(global_analysis, f, indent=2, ensure_ascii=False)
            
            print(f"  全局变量JSON已保存: {global_vars_file}")
            
        except Exception as e:
            print(f"生成全局JSON时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        return datetime.now().isoformat()


def analyze_project_for_modeling(project_path: str, debug_mode: bool = False) -> Dict[str, Any]:
    """分析项目用于中断建模的主函数"""
    analyzer = ImprovedInterruptModelAnalyzer(project_path)
    return analyzer.analyze_project(debug_mode)


if __name__ == "__main__":
    import sys
    
    # 获取项目根目录，以便定位 testfiles
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # ice_core/analysis/analyzer.py -> ice_core/analysis -> ice_core -> ice -> root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    
    # 默认测试路径
    default_test_path = os.path.join(project_root, "ice", "testfiles", "2.1_remarks", "svp_simple_001")
    
    # 如果路径不对，尝试调整
    if not os.path.exists(default_test_path):
         default_test_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "testfiles", "2.1_remarks", "svp_simple_001")

    target_path = sys.argv[1] if len(sys.argv) > 1 else default_test_path
    
    if os.path.exists(target_path):
        print(f"Running analysis on: {target_path}")
        analyze_project_for_modeling(target_path, debug_mode=True)
    else:
        print(f"Path not found: {target_path}")
