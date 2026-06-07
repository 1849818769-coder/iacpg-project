"""
共享变量提取API
提供从分析结果中提取共享变量的功能
共享变量：在主函数和中断函数（包括嵌套函数）中都被访问的全局变量
"""
from typing import List, Dict, Any, Set


class SharedVariableExtractor:
    """共享变量提取器"""
    
    def __init__(self, analysis_results: Dict[str, Any]):
        """
        初始化共享变量提取器
        
        Args:
            analysis_results: 分析结果字典，包含：
                - file_details: 文件详细信息
                - functions: 函数信息（main_functions, interrupt_functions, regular_functions）
                - variable_operations: 变量操作列表
                - function_call_relations: 函数调用关系列表
        """
        self.analysis_results = analysis_results
    
    def identify_shared_variables(self) -> List[Dict[str, Any]]:
        """
        识别共享变量（全局变量在主函数和中断函数中的交集，包括嵌套函数）
        
        Returns:
            共享变量列表，每个变量包含以下信息：
            - name: 变量名
            - type: 变量类型
            - data_structure: 数据结构类型
            - declaration: 变量声明
            - file_path: 文件路径
            - line_number: 行号
            - is_interrupt_related: 是否与中断相关
            - initial_value: 初始值
            - access_count: 访问次数
        """
        # 获取所有全局变量（排除局部变量）
        all_global_vars = self._get_all_global_variables()
        
        # 获取主函数和中断函数名称
        main_interrupt_functions = self._get_main_interrupt_functions()
        
        # 获取被主函数和中断函数调用的嵌套函数（递归查找）
        nested_functions = self._get_nested_functions(main_interrupt_functions)
        
        # 获取主函数、中断函数和嵌套函数访问的变量
        main_interrupt_vars = self._get_accessed_variables(main_interrupt_functions, nested_functions)
        
        # 共享变量是全局变量和主函数/中断函数/嵌套函数访问变量的交集
        shared_vars = all_global_vars.intersection(main_interrupt_vars)
        
        # 构建共享变量详细信息
        shared_variables = []
        for var_name in shared_vars:
            var_info = self._find_variable_info(var_name)
            if var_info:
                shared_variables.append({
                    "name": var_name,
                    "type": var_info["type"],
                    "data_structure": var_info.get("data_structure", "unknown"),
                    "declaration": var_info["declaration"],
                    "file_path": var_info["file_path"],
                    "line_number": var_info["line_number"],
                    "is_interrupt_related": var_info.get("is_interrupt_related", False),
                    "initial_value": var_info.get("initial_value", None),
                    "access_count": self._count_variable_access(var_name)
                })
        
        return shared_variables
    
    def _get_all_global_variables(self) -> Set[str]:
        """获取所有全局变量（排除局部变量）"""
        all_global_vars = set()
        for file_detail in self.analysis_results.get("file_details", {}).values():
            for var in file_detail.get("global_variables", []):
                # 检查是否是真正的全局变量（不在函数内部声明）
                if self._is_truly_global_variable(var):
                    all_global_vars.add(var["name"])
        return all_global_vars
    
    def _get_main_interrupt_functions(self) -> Set[str]:
        """获取主函数和中断函数名称"""
        main_interrupt_functions = set()
        
        functions = self.analysis_results.get("functions", {})
        for func in functions.get("main_functions", []):
            main_interrupt_functions.add(func["name"])
        for func in functions.get("interrupt_functions", []):
            main_interrupt_functions.add(func["name"])
        
        return main_interrupt_functions
    
    def _get_nested_functions(self, main_interrupt_functions: Set[str]) -> Set[str]:
        """
        递归获取被主函数和中断函数调用的嵌套函数
        
        Args:
            main_interrupt_functions: 主函数和中断函数名称集合
        
        Returns:
            嵌套函数名称集合
        """
        nested_functions = set()
        visited = set()
        
        def find_nested(func_name: str):
            if func_name in visited:
                return
            visited.add(func_name)
            
            # 查找被当前函数调用的函数
            for relation in self.analysis_results.get("function_call_relations", []):
                if relation["caller"] == func_name:
                    called_func = relation["called"]
                    if called_func not in main_interrupt_functions:  # 不是主函数或中断函数
                        nested_functions.add(called_func)
                        find_nested(called_func)  # 递归查找更深层的嵌套
        
        # 从主函数和中断函数开始查找
        for func_name in main_interrupt_functions:
            find_nested(func_name)
        
        return nested_functions
    
    def _get_accessed_variables(self, main_interrupt_functions: Set[str], nested_functions: Set[str]) -> Set[str]:
        """
        获取主函数、中断函数和嵌套函数访问的变量
        
        Args:
            main_interrupt_functions: 主函数和中断函数名称集合
            nested_functions: 嵌套函数名称集合
        
        Returns:
            被访问的变量名称集合
        """
        main_interrupt_vars = set()
        all_functions = main_interrupt_functions.union(nested_functions)
        
        for operation in self.analysis_results.get("variable_operations", []):
            if operation["function"] in all_functions:
                main_interrupt_vars.add(operation["variable"])
        
        return main_interrupt_vars
    
    def _is_truly_global_variable(self, var_info: Dict[str, Any]) -> bool:
        """
        判断是否是真正的全局变量（不在函数内部声明）
        
        Args:
            var_info: 变量信息字典
        
        Returns:
            如果是真正的全局变量返回True，否则返回False
        """
        var_name = var_info["name"]
        var_line = var_info["line_number"]
        
        # 检查变量声明是否在函数内部
        for file_detail in self.analysis_results.get("file_details", {}).values():
            file_path = file_detail["file_path"]
            if var_info["file_path"] == file_path:
                # 检查所有函数的行号范围
                for func in file_detail.get("interrupt_functions", []):
                    if self._is_variable_in_function(var_name, var_line, func, file_path):
                        return False
                
                for func in file_detail.get("main_functions", []):
                    if self._is_variable_in_function(var_name, var_line, func, file_path):
                        return False
                
                for func in file_detail.get("regular_functions", []):
                    if self._is_variable_in_function(var_name, var_line, func, file_path):
                        return False
        
        return True
    
    def _is_variable_in_function(self, var_name: str, var_line: int, func: Dict[str, Any], file_path: str) -> bool:
        """
        检查变量是否在函数内部声明
        
        Args:
            var_name: 变量名
            var_line: 变量声明行号
            func: 函数信息字典
            file_path: 文件路径
        
        Returns:
            如果变量在函数内部返回True，否则返回False
        """
        func_line = func["line_number"]
        func_body = func.get("function_body", "")
        
        # 如果变量声明行号在函数行号之后，可能是在函数内部
        if var_line > func_line:
            # 简单检查：如果变量名在函数体中，且行号在函数范围内，则认为是局部变量
            if var_name in func_body:
                # 更精确的检查：计算函数体的结束行号
                func_end_line = self._get_function_end_line(func_line, func_body)
                if var_line <= func_end_line:
                    return True
        
        return False
    
    def _get_function_end_line(self, func_start_line: int, func_body: str) -> int:
        """
        获取函数结束行号
        
        Args:
            func_start_line: 函数开始行号
            func_body: 函数体内容
        
        Returns:
            函数结束行号
        """
        # 计算函数体中的换行符数量来估算结束行号
        line_count = func_body.count('\n')
        return func_start_line + line_count
    
    def _find_variable_info(self, var_name: str) -> Dict[str, Any]:
        """
        查找变量声明信息
        
        Args:
            var_name: 变量名
        
        Returns:
            变量信息字典，如果未找到返回None
        """
        for file_detail in self.analysis_results.get("file_details", {}).values():
            for var in file_detail.get("global_variables", []):
                if var["name"] == var_name:
                    return var
        return None
    
    def _count_variable_access(self, var_name: str) -> int:
        """
        统计变量的访问次数
        
        Args:
            var_name: 变量名
        
        Returns:
            访问次数
        """
        count = 0
        for operation in self.analysis_results.get("variable_operations", []):
            if operation["variable"] == var_name:
                count += 1
        return count


# 便捷函数
def identify_shared_variables(analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    便捷函数：识别共享变量
    
    Args:
        analysis_results: 分析结果字典
    
    Returns:
        共享变量列表
    """
    extractor = SharedVariableExtractor(analysis_results)
    return extractor.identify_shared_variables()

