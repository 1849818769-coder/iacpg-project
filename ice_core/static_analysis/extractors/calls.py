"""
函数调用关系提取API
提供从源代码中提取函数调用关系的功能
"""
import re
from typing import List, Dict, Any


class FunctionCallExtractor:
    """函数调用关系提取器"""
    
    def __init__(self, interrupt_function_patterns: List[str], 
                 main_function_patterns: List[str], 
                 regular_function_patterns: List[str]):
        """
        初始化函数调用提取器
        
        Args:
            interrupt_function_patterns: 中断函数匹配模式列表
            main_function_patterns: 主函数匹配模式列表
            regular_function_patterns: 普通函数匹配模式列表
        """
        self.interrupt_function_patterns = interrupt_function_patterns
        self.main_function_patterns = main_function_patterns
        self.regular_function_patterns = regular_function_patterns
        self._init_patterns()
    
    def _init_patterns(self):
        """初始化函数调用匹配模式"""
        # 函数调用匹配模式
        self.function_call_patterns = [
            r'(\w+)\s*\(\s*[^)]*\s*\)',  # e.g: init(), delay_ms(100), calculate(a, b), printf("Hello")
        ]
        
        # 需要跳过的关键字（不是函数调用）
        self.skip_keywords = {'if', 'for', 'while', 'switch', 'sizeof'}
    
    def extract_function_calls(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        提取函数调用关系（支持跨行函数调用）
        
        Args:
            content: 源代码内容
            file_path: 文件路径
        
        Returns:
            函数调用列表，每个调用包含以下信息：
            - caller: 调用者函数名
            - called: 被调用函数名
            - file_path: 文件路径
            - line_number: 行号
            - code_line: 代码行内容
        """
        function_calls = []
        lines = content.split('\n')
        current_function = None
        
        # 合并所有函数匹配模式
        all_function_patterns = (
            self.interrupt_function_patterns + 
            self.main_function_patterns + 
            self.regular_function_patterns
        )
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            line_num = i + 1
            
            # 跟踪当前函数
            for pattern in all_function_patterns:
                func_match = re.search(pattern, line)
                if func_match:
                    current_function = func_match.group(1)
                    break
            
            if current_function is None:
                i += 1
                continue
            
            # 查找函数调用（支持跨行）
            # 首先尝试单行匹配
            found_single_line_call = False
            for pattern in self.function_call_patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    called_func = match.group(1)
                    
                    # 跳过当前函数名和关键字
                    if (called_func == current_function or 
                        called_func in self.skip_keywords):
                        continue
                    
                    call_info = {
                        "caller": current_function,
                        "called": called_func,
                        "file_path": file_path,
                        "line_number": line_num,
                        "code_line": line
                    }
                    
                    function_calls.append(call_info)
                    found_single_line_call = True
            
            # 如果单行没有找到完整的函数调用，检查是否有未闭合的函数调用（跨行情况）
            if not found_single_line_call:
                # 查找函数名后跟开括号但没有闭括号的情况
                func_call_start_pattern = r'(\w+)\s*\('
                match = re.search(func_call_start_pattern, line)
                if match:
                    func_name = match.group(1)
                    # 跳过当前函数名和关键字
                    if func_name != current_function and func_name not in self.skip_keywords:
                        # 计算括号匹配
                        paren_count = line.count('(') - line.count(')')
                        if paren_count > 0:
                            # 有未闭合的括号，继续读取后续行直到括号闭合
                            call_lines = [line]
                            start_line_num = line_num
                            j = i + 1
                            while j < len(lines) and paren_count > 0:
                                next_line = lines[j].strip()
                                call_lines.append(next_line)
                                paren_count += next_line.count('(') - next_line.count(')')
                                j += 1
                            
                            # 合并多行代码
                            full_call_code = ' '.join(call_lines)
                            
                            # 验证是否真的是函数调用（有闭合括号）
                            if paren_count == 0:
                                call_info = {
                                    "caller": current_function,
                                    "called": func_name,
                                    "file_path": file_path,
                                    "line_number": start_line_num,
                                    "code_line": full_call_code
                                }
                                function_calls.append(call_info)
                            
                            # 跳过已处理的行（j-1是因为j在循环后会+1，然后i += 1会再+1）
                            i = j - 1
            
            i += 1
        
        return function_calls

