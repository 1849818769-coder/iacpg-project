"""
变量操作提取器 - 提取C代码中的变量读写操作
"""
import re
import os
import tempfile
from typing import List, Dict, Any, Optional, Set
from pycparser import parse_file, c_ast
from pycparser.c_generator import CGenerator
from .globals import GlobalVariableExtractor


class VariableOperationExtractor:
    """变量操作提取器 - 提取C代码中的变量读写操作"""
    
    def __init__(self, global_variable_extractor: GlobalVariableExtractor,
                 interrupt_function_patterns: List[str],
                 main_function_patterns: List[str],
                 regular_function_patterns: List[str]):
        """
        初始化变量操作提取器

        Args:
            global_variable_extractor: 全局变量提取器实例
            interrupt_function_patterns: 中断函数匹配模式列表
            main_function_patterns: 主函数匹配模式列表
            regular_function_patterns: 普通函数匹配模式列表
        """
        self.global_variable_extractor = global_variable_extractor
        self.interrupt_function_patterns = interrupt_function_patterns
        self.main_function_patterns = main_function_patterns
        self.regular_function_patterns = regular_function_patterns

        # 初始化 pycparser 分析器
        self.pycparser_analyzer = PycParserVariableOperationAnalyzer()
    
    def extract_variable_operations(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        提取变量读写操作（使用 pycparser 语法树分析）
        
        Args:
            content: C代码内容
            file_path: 文件路径
            
        Returns:
            变量操作列表
        """
        # 获取全局变量列表
        global_vars = self._extract_global_variables(content, file_path)
        
        # 获取局部变量列表和指针映射关系
        local_variables, pointer_to_variable_map, global_pointer_to_local_map = \
            self._extract_local_variables_and_pointers(content, global_vars)
        
        # 使用 pycparser 分析器
        try:
            variable_operations = self.pycparser_analyzer.analyze_variable_operations_ast(
                content, file_path, global_vars, local_variables, 
                pointer_to_variable_map, global_pointer_to_local_map
            )
            
            return variable_operations if variable_operations else []
                
        except Exception as e:
            print(f"pycparser 分析失败: {e}")
            return []
    
    def _extract_global_variables(self, content: str, file_path: str) -> Set[str]:
        """提取全局变量列表"""
        global_vars = set()
        global_variable_info = self.global_variable_extractor.extract_global_variables(content, file_path)
        for var_info in global_variable_info:
            global_vars.add(var_info['name'])
        return global_vars
    
    def _extract_local_variables_and_pointers(self, content: str, global_vars: Set[str]) -> tuple:
        """
        提取局部变量列表和指针映射关系
        
        Args:
            content: C代码内容
            global_vars: 全局变量集合
            
        Returns:
            (local_variables, pointer_to_variable_map, global_pointer_to_local_map)
        """
        local_variables = set()
        pointer_to_variable_map = {}  # 存储指针变量到目标变量的映射
        global_pointer_to_local_map = {}  # 存储全局指针到局部变量的映射
        lines = content.split('\n')
        current_function = None
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # 跳过注释行和空行
            # 注意：不能简单地跳过以*开头的行，因为指针解引用操作也以*开头
            if line.startswith('//') or line.startswith('/*') or not line:
                continue
            
            # 跳过以*开头的注释行，但保留指针解引用操作
            if line.startswith('*') and not ('=' in line or '+' in line or '-' in line or '/' in line):
                continue
            
            # 跟踪当前函数
            for pattern in self.interrupt_function_patterns + self.main_function_patterns + self.regular_function_patterns:
                func_match = re.search(pattern, line)
                if func_match:
                    current_function = func_match.group(1)
                    local_variables.clear()  # 新函数开始，清空局部变量
                    # 清空当前函数的指针映射
                    pointer_to_variable_map = {k: v for k, v in pointer_to_variable_map.items() 
                                             if not k.startswith(f"{current_function}_")}
                    break
            
            if current_function is None:
                continue
            
            # 检测局部变量声明（包括指针类型）
            local_var_patterns = [
                # 基本类型声明
                r'int\s+(\w+)\s*;',  # int var;
                r'int\s+(\w+)\s*=\s*[^;]+;',  # int var = value;
                r'for\s*\(\s*int\s+(\w+)\s*=',  # for (int i = 0;
                r'(\w+)\s+(\w+)\s*;',  # type var;
                r'(\w+)\s+(\w+)\s*=\s*[^;]+;',  # type var = value;
                
                # 指针类型声明
                r'int\s*\*\s*(\w+)\s*;',  # int *p;
                r'int\s*\*\s*(\w+)\s*=\s*&\s*([a-zA-Z_]\w*)\s*;',  # int *p = &global_var;
                r'(\w+)\s*\*\s*(\w+)\s*;',  # type *p;
                r'(\w+)\s*\*\s*(\w+)\s*=\s*&\s*([a-zA-Z_]\w*)\s*;',  # type *p = &global_var;
                r'volatile\s+int\s*\*\s*(\w+)\s*;',  # volatile int *p;
                r'volatile\s+int\s*\*\s*(\w+)\s*=\s*&\s*([a-zA-Z_]\w*)\s*;',  # volatile int *p = &global_var;
            ]
            
            # 检测全局指针到局部变量的赋值
            global_pointer_assignment_patterns = [
                r'(\w+)\s*=\s*&\s*([a-zA-Z_]\w*)\s*;',  # global_pointer = &local_var;
            ]
            
            for pattern in local_var_patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    if 'for' in pattern:
                        var_name = match.group(1).strip()
                        local_variables.add(var_name)
                    elif 'int\s*\*\s*(\w+)\s*=\s*&\s*([a-zA-Z_]\w*)' in pattern:
                        # 指针初始化：int *p = &global_var;
                        pointer_name = match.group(1).strip()
                        target_var = match.group(2).strip()
                        local_variables.add(pointer_name)
                        pointer_to_variable_map[f"{current_function}_{pointer_name}"] = target_var
                    elif '(\w+)\s*\*\s*(\w+)\s*=\s*&\s*([a-zA-Z_]\w*)' in pattern:
                        # 类型指针初始化：type *p = &global_var;
                        pointer_name = match.group(2).strip()
                        target_var = match.group(3).strip()
                        local_variables.add(pointer_name)
                        pointer_to_variable_map[f"{current_function}_{pointer_name}"] = target_var
                    elif 'volatile\s+int\s*\*\s*(\w+)\s*=\s*&\s*([a-zA-Z_]\w*)' in pattern:
                        # volatile指针初始化：volatile int *p = &global_var;
                        pointer_name = match.group(1).strip()
                        target_var = match.group(2).strip()
                        local_variables.add(pointer_name)
                        pointer_to_variable_map[f"{current_function}_{pointer_name}"] = target_var
                    elif match.lastindex >= 2:
                        var_name = match.group(2).strip()
                        local_variables.add(var_name)
                    else:
                        var_name = match.group(1).strip()
                        local_variables.add(var_name)
            
            # 检测全局指针到局部变量的赋值
            for pattern in global_pointer_assignment_patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    global_pointer = match.group(1).strip()
                    local_var = match.group(2).strip()
                    
                    # 检查是否是全局指针指向局部变量
                    if global_pointer in global_vars and local_var in local_variables:
                        # 建立全局指针到局部变量的映射
                        global_pointer_to_local_map[f"{current_function}_{global_pointer}"] = {
                            "local_var": local_var,
                            "function": current_function,
                            "line": line_num
                        }
        
        return local_variables, pointer_to_variable_map, global_pointer_to_local_map


class PycParserVariableOperationAnalyzer:
    """基于 pycparser 的变量操作分析器"""
    
    def __init__(self):
        try:
            self.c_ast = c_ast
            # 使用 pycparser 自带的 CGenerator 将 AST 节点还原为 C 表达式
            # 这样可以避免出现 Cast(...) 这种 AST 文本形式，统一得到“i 表达式”形式的字符串
            self.generator = CGenerator()
            self.pycparser_available = True
        except ImportError:
            self.pycparser_available = False
            print("警告: pycparser 不可用")
    
    def analyze_variable_operations_ast(self, content: str, file_path: str, global_vars: set, 
                                       local_vars: set, pointer_to_variable_map: dict = None, 
                                       global_pointer_to_local_map: dict = None) -> List[Dict[str, Any]]:
        """使用 pycparser 分析变量读写操作"""
        if not self.pycparser_available:
            return []
        
        try:
            # 预处理C代码（添加必要的头文件声明）
            preprocessed_content, line_offset = self._preprocess_content_with_offset(content)
            
            # 写入临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(preprocessed_content)
                temp_file_path = temp_file.name
            
            try:
                # 获取项目根目录，用于解析相对路径的include
                project_root = os.path.dirname(os.path.dirname(file_path))
                include_paths = [
                    '-I/usr/include/fake_libc_include',
                    f'-I{project_root}',
                    f'-I{os.path.dirname(file_path)}'
                ]
                
                ast = parse_file(temp_file_path, use_cpp=True, cpp_args=include_paths)
                
                # 创建访问器，传入行号偏移量、指针映射以及 CGenerator
                visitor = VariableOperationVisitor(
                    global_vars,
                    local_vars,
                    file_path,
                    line_offset,
                    pointer_to_variable_map,
                    global_pointer_to_local_map,
                    self.generator,
                )
                visitor.visit(ast)
                
                return visitor.variable_operations
                
            finally:
                # 清理临时文件
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    
        except Exception as e:
            print(f"pycparser 解析失败: {e}")
            return []
    
    def _preprocess_content_with_offset(self, content):
        """预处理C代码内容并返回行号偏移量"""
        # 某些测试用例仅通过 common.h 间接声明基础函数，但源码本身未显式包含 <stdint.h>。
        # pycparser 在这种情况下无法识别 int16_t/int64_t 等标准整型别名，导致变量操作抽取直接失败。
        # 统一补一行标准头文件即可保持解析稳定；line_offset 用于恢复原始源码行号。
        shim = "#include <stdint.h>\n"
        return shim + content, 1


class VariableOperationVisitor(object):
    """变量操作访问器"""
    
    def __init__(self, global_vars, local_vars, file_path, line_offset=0, 
                 pointer_to_variable_map=None, global_pointer_to_local_map=None,
                 generator: Optional[CGenerator] = None):
        self.c_ast = c_ast
        self.global_vars = global_vars
        self.local_vars = local_vars
        self.file_path = file_path
        self.line_offset = line_offset  # 行号偏移量
        self.pointer_to_variable_map = pointer_to_variable_map or {}  # 指针到变量的映射
        self.global_pointer_to_local_map = global_pointer_to_local_map or {}  # 全局指针到局部变量的映射
        self.variable_operations = []
        self.current_function = None
        self.current_line = 1
        # 用于将 AST 节点还原为标准 C 表达式的生成器
        self.generator = generator
        
    def visit(self, node):
        """访问节点"""
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)
    
    def generic_visit(self, node):
        """通用访问方法"""
        for c_name, c in node.children():
            self.visit(c)
    
    def visit_FuncDef(self, node):
        """访问函数定义"""
        self.current_function = node.decl.name
        self.generic_visit(node)
        self.current_function = None

    def visit_Decl(self, node):
        """访问变量声明，提取初始化表达式中的变量读取操作"""
        if not self.current_function:
            self.generic_visit(node)
            return

        # 处理变量声明中的初始化表达式（如：int var = value;）
        if hasattr(node, 'init') and node.init is not None:
            self._find_read_variables(node.init)

        # 继续处理其他部分
        self.generic_visit(node)

    def visit_FuncCall(self, node):
        """访问函数调用，提取参数中的变量读取操作
        
        注意：
        - 函数调用参数中使用全局变量，等价于对该全局变量的读操作
        - 这里专门调用 _find_read_variables 处理参数，避免依赖 visit_ID
        """
        if not self.current_function:
            self.generic_visit(node)
            return
        
        # 处理函数调用参数中的变量（参数传递是读操作）
        if hasattr(node, 'args') and node.args:
            for arg in node.args:
                # 递归处理参数中的变量
                self._find_read_variables(arg)
        
        # 继续处理其他部分
        self.generic_visit(node)
    
    def visit_ID(self, node):
        """访问标识符（变量名）- 简化版本，主要处理独立的变量引用"""
        # 在这个简化版本中，我们不处理 ID，而是依赖其他特定的访问方法
        # 这样可以避免重复计算和父子节点关系的复杂性
        pass
    
    def visit_Assignment(self, node):
        """访问赋值表达式"""
        if not self.current_function:
            self.generic_visit(node)
            return
            
        # 检查是否已经在switch语句中处理过（避免重复处理）
        if hasattr(self, '_in_switch_context') and self._in_switch_context:
            # 在switch上下文中，跳过常规处理，因为已经在visit_Switch中处理了
            self.generic_visit(node)
            return
        
        # 定义复合赋值操作符映射（在函数开始处定义，以便后续使用）
        op_map = {
            '+=': '+',
            '-=': '-',
            '*=': '*',
            '/=': '/',
            '%=': '%',
            '<<=': '<<',
            '>>=': '>>',
            '&=': '&',
            '^=': '^',
            '|=': '|'
        }
            
        try:
            # 处理左值（写操作）
            left_var_info = self._extract_variable_from_node(node.lvalue)
            if left_var_info and (self._is_global_variable(left_var_info['base_name']) or 
                                  left_var_info.get('is_local_pointer', False) or 
                                  left_var_info.get('is_global_pointer', False)):
                line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                
                # 检查是否是复合赋值操作符（如 +=, -=, *= 等）
                # 在 pycparser 中，复合赋值操作符可能被解析为 Assignment 节点，其中 op 是 '+=' 等
                
                # 获取 value：如果是复合赋值，构建完整表达式；否则只取右值
                if node.op in op_map:
                    # 复合赋值：var += 1 -> var + 1
                    left_text = self._get_node_text(node.lvalue)
                    right_text = self._get_node_text(node.rvalue)
                    binary_op = op_map[node.op]
                    value = f"{left_text} {binary_op} {right_text}"
                else:
                    # 普通赋值：只取右值
                    value = self._get_node_text(node.rvalue)
                
                operation = {
                    "operation_type": "write",
                    "variable": left_var_info['base_name'],
                    "variable_expression": left_var_info['full_expression'],
                    "index": left_var_info['index'],
                    "value": value,
                    "line_number": line_num,
                    "function": self.current_function,
                    "code_line": self._get_assignment_text(node),
                    "file_path": self.file_path
                }
                
                # 添加成员信息（如果是结构体/联合体成员访问）
                if left_var_info.get('member'):
                    operation['member'] = left_var_info['member']
                # 如果是局部指针，添加额外信息
                if left_var_info.get('is_local_pointer', False):
                    operation['pointer_name'] = left_var_info.get('pointer_name', '')
                    operation['is_pointer_deref'] = True
                # 如果是全局指针，添加额外信息
                elif left_var_info.get('is_global_pointer', False):
                    operation['pointer_name'] = left_var_info.get('pointer_name', '')
                    operation['is_pointer_deref'] = True
                    operation['is_global_pointer'] = True
                    operation['target_function'] = left_var_info.get('target_function', '')
                self.variable_operations.append(operation)
            
            # 处理左值中的索引和成员访问中的变量（读操作）
            # 例如：array[index] = value 中，index是读操作
            # 例如：struct.member = value 中，如果member是通过变量索引访问的
            
            # 使用专门的辅助方法处理左值内部的读操作（避免将左值基变量误判为读）
            if isinstance(node.lvalue, (self.c_ast.ArrayRef, self.c_ast.StructRef)):
                self._find_read_variables_in_lvalue(node.lvalue)

            # 对于复合赋值，左值本身也需要被读取（例如 array[index] += 1，则 array[index] 也要算一次读）
            if node.op in op_map:
                if isinstance(node.lvalue, self.c_ast.ArrayRef):
                    var_info = self._extract_variable_from_node(node.lvalue)
                    if var_info and self._is_global_variable(var_info['base_name']):
                        line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                        read_operation = {
                            "operation_type": "read",
                            "variable": var_info['base_name'],
                            "variable_expression": var_info['full_expression'],
                            "index": var_info['index'],
                            "value": None,
                            "line_number": line_num,
                            "function": self.current_function,
                            "code_line": self._get_node_text(node.lvalue),
                            "file_path": self.file_path
                        }
                        self.variable_operations.append(read_operation)
                elif isinstance(node.lvalue, self.c_ast.StructRef):
                    var_info = self._extract_variable_from_node(node.lvalue)
                    if var_info and self._is_global_variable(var_info['base_name']):
                        line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                        read_operation = {
                            "operation_type": "read",
                            "variable": var_info['base_name'],
                            "variable_expression": var_info['full_expression'],
                            "index": None,
                            "member": var_info.get('member'),
                            "value": None,
                            "line_number": line_num,
                            "function": self.current_function,
                            "code_line": self._get_node_text(node.lvalue),
                            "file_path": self.file_path
                        }
                        self.variable_operations.append(read_operation)

            elif isinstance(node.lvalue, self.c_ast.UnaryOp) and node.lvalue.op == '*':
                # 处理指针解引用：*ptr = value 中，ptr是读操作
                self._find_read_variables(node.lvalue.expr)
                # 对于复合赋值，左值本身也需要被读取
                if node.op in op_map:
                    var_info = self._extract_variable_from_node(node.lvalue)
                    if var_info and (self._is_global_variable(var_info['base_name']) or 
                                    var_info.get('is_local_pointer', False) or 
                                    var_info.get('is_global_pointer', False)):
                        line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                        read_operation = {
                            "operation_type": "read",
                            "variable": var_info['base_name'],
                            "variable_expression": var_info['full_expression'],
                            "index": None,
                            "value": None,
                            "line_number": line_num,
                            "function": self.current_function,
                            "code_line": self._get_node_text(node.lvalue),
                            "file_path": self.file_path
                        }
                        if var_info.get('is_local_pointer', False):
                            read_operation['pointer_name'] = var_info.get('pointer_name', '')
                            read_operation['is_pointer_deref'] = True
                        elif var_info.get('is_global_pointer', False):
                            read_operation['pointer_name'] = var_info.get('pointer_name', '')
                            read_operation['is_pointer_deref'] = True
                            read_operation['is_global_pointer'] = True
                            read_operation['target_function'] = var_info.get('target_function', '')
                        self.variable_operations.append(read_operation)
            elif isinstance(node.lvalue, self.c_ast.ID):
                # 对于简单的变量（非数组、非结构体、非指针），如果是复合赋值，左值本身也需要被读取
                if node.op in op_map and self._is_global_variable(node.lvalue.name):
                    line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                    read_operation = {
                        "operation_type": "read",
                        "variable": node.lvalue.name,
                        "variable_expression": node.lvalue.name,
                        "index": None,
                        "value": None,
                        "line_number": line_num,
                        "function": self.current_function,
                        "code_line": self._get_node_text(node.lvalue),
                        "file_path": self.file_path
                    }
                    self.variable_operations.append(read_operation)
            
            # 处理右值中的变量（读操作）
            self._find_read_variables(node.rvalue)
            
        except Exception as e:
            print(f"访问赋值表达式时出错: {e}")
            self.generic_visit(node)
    
    def visit_UnaryOp(self, node):
        """访问一元操作符（如++、--）"""
        if not self.current_function:
            self.generic_visit(node)
            return
            
        # 自增自减操作是写操作
        if node.op in ['++', '--', 'p++', 'p--']:
            var_info = self._extract_variable_from_node(node.expr)
            if var_info and self._is_global_variable(var_info['base_name']):
                line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                
                # 获取正确的操作值
                if node.op == 'p++':
                    op_value = "++"
                elif node.op == 'p--':
                    op_value = "--"
                else:
                    op_value = node.op
                
                operation = {
                    "operation_type": "write",
                    "variable": var_info['base_name'],
                    "variable_expression": var_info['full_expression'],
                    "index": var_info['index'],
                    "value": op_value,
                    "line_number": line_num,
                    "function": self.current_function,
                    "code_line": self._get_node_text(node),
                    "file_path": self.file_path
                }
                self.variable_operations.append(operation)
        
        self.generic_visit(node)
    
    def visit_ArrayRef(self, node):
        """访问数组引用 - 简化版本"""
        # 数组访问的读写判断将由 Assignment 和 _find_read_variables 处理
        # 这里不需要单独处理，避免重复
        self.generic_visit(node)
    
    def visit_StructRef(self, node):
        """访问结构体/联合体成员引用 - 简化版本"""
        # 结构体成员访问的读写判断将由 Assignment 和 _find_read_variables 处理
        # 这里不需要单独处理，避免重复
        self.generic_visit(node)
    
    def visit_Expr(self, node):
        """访问表达式语句（如 var++;）"""
        if not self.current_function:
            self.generic_visit(node)
            return
            
        try:
            # 处理表达式中的变量操作
            if isinstance(node.expr, self.c_ast.UnaryOp):
                # 处理 ++ 和 -- 操作
                unary_op = node.expr
                if unary_op.op in ['p++', 'p--', '++', '--']:
                    # 提取变量信息
                    var_info = self._extract_variable_from_node(unary_op.expr)
                    if var_info and self._is_global_variable(var_info['base_name']):
                        line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                        # 获取正确的操作值
                        if unary_op.op == 'p++':
                            op_value = "++"
                        elif unary_op.op == 'p--':
                            op_value = "--"
                        else:
                            op_value = unary_op.op
                        
                        operation = {
                            "operation_type": "write",
                            "variable": var_info['base_name'],
                            "variable_expression": var_info['full_expression'],
                            "index": None,
                            "value": op_value,
                            "line_number": line_num,
                            "function": self.current_function,
                            "code_line": self._get_node_text(node.expr),
                            "file_path": self.file_path
                        }
                        self.variable_operations.append(operation)
            
            # 继续处理其他部分
            self.generic_visit(node)
        except Exception as e:
            print(f"处理表达式语句时出错: {e}")
            self.generic_visit(node)
    
    def visit_If(self, node):
        """访问条件语句"""
        if not self.current_function:
            self.generic_visit(node)
            return
            
        # 处理条件表达式中的变量（读操作）
        if hasattr(node, 'cond'):
            self._find_read_variables(node.cond)
        
        # 继续处理其他部分
        self.generic_visit(node)
    
    def visit_While(self, node):
        """访问循环语句"""
        if not self.current_function:
            self.generic_visit(node)
            return
            
        # 处理条件表达式中的变量（读操作）
        if hasattr(node, 'cond'):
            self._find_read_variables(node.cond)
        
        # 继续处理其他部分
        self.generic_visit(node)
    
    def visit_Return(self, node):
        """访问return语句，提取返回表达式中的读操作
        
        例如：
            return svp_simple_029_001_tm_blocks[tm_name];
        这里对全局数组的访问应被视为一次读操作。
        """
        if not self.current_function:
            self.generic_visit(node)
            return
        
        try:
            if hasattr(node, 'expr') and node.expr is not None:
                # 对返回表达式中的变量进行读操作提取
                self._find_read_variables(node.expr)
        except Exception as e:
            print(f"处理return语句时出错: {e}")
        
        # 继续遍历子节点
        self.generic_visit(node)
    
    def visit_For(self, node):
        """访问for循环语句"""
        if not self.current_function:
            self.generic_visit(node)
            return
            
        # 处理条件表达式中的变量（读操作）
        if hasattr(node, 'cond'):
            self._find_read_variables(node.cond)
        
        # 继续处理其他部分
        self.generic_visit(node)
    
    def visit_TernaryOp(self, node):
        """访问三元运算符 (condition ? true_value : false_value)"""
        if not self.current_function:
            self.generic_visit(node)
            return
            
        # 获取三元运算符的条件文本
        condition_text = self._get_node_text(node.cond)
        
        # 处理条件表达式中的变量（读操作）
        if hasattr(node, 'cond'):
            self._find_read_variables_with_condition(node.cond, f"({condition_text})")
        
        # 处理true_value中的变量（读操作，条件为true）
        if hasattr(node, 'iftrue'):
            self._find_read_variables_with_condition(node.iftrue, f"({condition_text})")
        
        # 处理false_value中的变量（读操作，条件为false）
        if hasattr(node, 'iffalse'):
            self._find_read_variables_with_condition(node.iffalse, f"!({condition_text})")
        
        # 继续处理其他部分
        self.generic_visit(node)
    
    def visit_Switch(self, node):
        """访问switch语句"""
        if not self.current_function:
            self.generic_visit(node)
            return

        # 设置switch上下文标志
        self._in_switch_context = True

        try:
            # 处理条件表达式中的变量（读操作）
            if hasattr(node, 'cond'):
                self._find_read_variables(node.cond)

            # 获取switch条件
            switch_condition = self._get_node_text(node.cond)

            # 处理switch语句体中的变量操作
            if hasattr(node, 'stmt'):
                self._process_switch_body(node.stmt, switch_condition)

            # 继续处理其他部分
            self.generic_visit(node)
        finally:
            # 清除switch上下文标志
            self._in_switch_context = False
    
    def _process_switch_body(self, stmt, switch_condition):
        """处理switch语句体中的变量操作"""
        if isinstance(stmt, self.c_ast.Compound):
            # 处理复合语句（包含多个语句）
            for child in stmt.block_items:
                self._process_switch_statement(child, switch_condition)
        else:
            # 处理单个语句
            self._process_switch_statement(stmt, switch_condition)
    
    def _process_switch_statement(self, stmt, switch_condition):
        """处理switch语句体中的单个语句"""
        if isinstance(stmt, self.c_ast.Case):
            # 处理case语句
            case_value = self._get_node_text(stmt.expr) if stmt.expr else "default"
            case_condition = f"{switch_condition} == {case_value}"
            
            # 处理case语句体
            if stmt.stmts:
                for child_stmt in stmt.stmts:
                    self._process_statement_with_condition(child_stmt, case_condition)
        elif isinstance(stmt, self.c_ast.Default):
            # 处理default语句
            default_condition = "default"
            
            # 处理default语句体
            if stmt.stmts:
                for child_stmt in stmt.stmts:
                    self._process_statement_with_condition(child_stmt, default_condition)
        else:
            # 处理其他语句（如break）
            self.visit(stmt)
    
    def _process_statement_with_condition(self, stmt, condition):
        """处理带有条件的语句"""
        if isinstance(stmt, self.c_ast.Assignment):
            # 处理赋值语句
            self._process_assignment_with_condition(stmt, condition)
        else:
            # 处理其他语句
            self.visit(stmt)
    
    def _process_assignment_with_condition(self, node, condition):
        """处理带有条件的赋值语句"""
        try:
            # 处理左值（写操作）
            left_var_info = self._extract_variable_from_node(node.lvalue)
            if left_var_info and (self._is_global_variable(left_var_info['base_name']) or 
                                  left_var_info.get('is_local_pointer', False) or 
                                  left_var_info.get('is_global_pointer', False)):
                line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                operation = {
                    "operation_type": "write",
                    "variable": left_var_info['base_name'],
                    "variable_expression": left_var_info['full_expression'],
                    "index": left_var_info['index'],
                    "value": self._get_node_text(node.rvalue),
                    "line_number": line_num,
                    "function": self.current_function,
                    "code_line": self._get_assignment_text(node),
                    "file_path": self.file_path,
                    "condition": condition
                }
                
                # 添加成员信息（如果是结构体/联合体成员访问）
                if left_var_info.get('member'):
                    operation['member'] = left_var_info['member']
                # 如果是局部指针，添加额外信息
                if left_var_info.get('is_local_pointer', False):
                    operation['pointer_name'] = left_var_info.get('pointer_name', '')
                    operation['is_pointer_deref'] = True
                # 如果是全局指针，添加额外信息
                elif left_var_info.get('is_global_pointer', False):
                    operation['pointer_name'] = left_var_info.get('pointer_name', '')
                    operation['is_pointer_deref'] = True
                    operation['is_global_pointer'] = True
                    operation['target_function'] = left_var_info.get('target_function', '')
                self.variable_operations.append(operation)
            
            # 处理右值中的变量（读操作）
            self._find_read_variables_with_condition(node.rvalue, condition)
            
        except Exception as e:
            print(f"处理带条件的赋值表达式时出错: {e}")
    
    def _find_read_variables_with_condition(self, node, condition):
        """递归查找读取的变量，并添加条件信息"""
        if not node:
            return
            
        try:
            if isinstance(node, self.c_ast.ID):
                var_name = node.name
                if self._is_global_variable(var_name):
                    line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                    operation = {
                        "operation_type": "read",
                        "variable": var_name,
                        "variable_expression": var_name,
                        "index": None,
                        "value": None,
                        "line_number": line_num,
                        "function": self.current_function,
                        "code_line": self._get_node_text(node),
                        "file_path": self.file_path,
                        "condition": condition
                    }
                    self.variable_operations.append(operation)
            elif isinstance(node, self.c_ast.UnaryOp) and node.op == '*':
                # 处理指针解引用的读取操作
                var_info = self._extract_variable_from_node(node)
                if var_info and (self._is_global_variable(var_info['base_name']) or 
                                var_info.get('is_local_pointer', False) or 
                                var_info.get('is_global_pointer', False)):
                    line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                    operation = {
                        "operation_type": "read",
                        "variable": var_info['base_name'],
                        "variable_expression": var_info['full_expression'],
                        "index": var_info.get('index'),
                        "value": None,
                        "line_number": line_num,
                        "function": self.current_function,
                        "code_line": self._get_node_text(node),
                        "file_path": self.file_path,
                        "condition": condition
                    }
                    
                    # 添加指针映射关系信息
                    if var_info.get('is_pointer_deref', False):
                        operation['is_pointer_deref'] = True
                        operation['pointer_name'] = var_info.get('pointer_name', '')
                        if var_info.get('is_global_pointer', False):
                            operation['is_global_pointer'] = True
                            operation['target_function'] = var_info.get('target_function', '')
                    
                    self.variable_operations.append(operation)
            elif isinstance(node, self.c_ast.ArrayRef):
                # 处理数组访问的读取操作
                var_info = self._extract_variable_from_node(node)
                if var_info and (self._is_global_variable(var_info['base_name']) or 
                                var_info.get('is_local_pointer', False) or 
                                var_info.get('is_global_pointer', False)):
                    line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                    operation = {
                        "operation_type": "read",
                        "variable": var_info['base_name'],
                        "variable_expression": var_info['full_expression'],
                        "index": var_info.get('index'),
                        "value": None,
                        "line_number": line_num,
                        "function": self.current_function,
                        "code_line": self._get_node_text(node),
                        "file_path": self.file_path,
                        "condition": condition
                    }
                    
                    # 添加指针映射关系信息
                    if var_info.get('is_pointer_deref', False):
                        operation['is_pointer_deref'] = True
                        operation['pointer_name'] = var_info.get('pointer_name', '')
                        if var_info.get('is_global_pointer', False):
                            operation['is_global_pointer'] = True
                            operation['target_function'] = var_info.get('target_function', '')
                    
                    self.variable_operations.append(operation)
            elif isinstance(node, self.c_ast.StructRef):
                # 处理结构体/联合体成员访问的读取操作
                var_info = self._extract_variable_from_node(node)
                if var_info and (self._is_global_variable(var_info['base_name']) or 
                                var_info.get('is_local_pointer', False) or 
                                var_info.get('is_global_pointer', False)):
                    line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                    operation = {
                        "operation_type": "read",
                        "variable": var_info['base_name'],
                        "variable_expression": var_info['full_expression'],
                        "index": None,
                        "member": var_info.get('member'),
                        "value": None,
                        "line_number": line_num,
                        "function": self.current_function,
                        "code_line": self._get_node_text(node),
                        "file_path": self.file_path,
                        "condition": condition
                    }
                    
                    # 添加指针映射关系信息
                    if var_info.get('is_pointer_deref', False):
                        operation['is_pointer_deref'] = True
                        operation['pointer_name'] = var_info.get('pointer_name', '')
                        if var_info.get('is_global_pointer', False):
                            operation['is_global_pointer'] = True
                            operation['target_function'] = var_info.get('target_function', '')
                    
                    self.variable_operations.append(operation)
            else:
                # 递归处理其他节点类型
                for child_name, child_node in node.children():
                    self._find_read_variables_with_condition(child_node, condition)
        except Exception as e:
            print(f"处理变量操作时出错: {e}")
    
    def _extract_variable_from_node(self, node):
        """从节点提取变量信息"""
        if isinstance(node, self.c_ast.ID):
            return {
                'base_name': node.name,
                'full_expression': node.name,
                'index': None,
                'is_pointer_deref': False
            }
        elif isinstance(node, self.c_ast.UnaryOp) and node.op == '*':
            # 处理指针解引用: *pointer
            base_info = self._extract_variable_from_node(node.expr)
            if base_info:
                # 检查是否是局部指针指向全局变量
                pointer_key = f"{self.current_function}_{base_info['base_name']}"
                if pointer_key in self.pointer_to_variable_map:
                    # 这是局部指针解引用，映射到实际的全局变量
                    target_var = self.pointer_to_variable_map[pointer_key]
                    return {
                        'base_name': target_var,  # 返回实际的目标变量
                        'full_expression': f"*{base_info['base_name']}",
                        'index': None,
                        'is_pointer_deref': True,
                        'pointer_name': base_info['base_name'],  # 保存原始指针名
                        'is_local_pointer': True
                    }
                elif pointer_key in self.global_pointer_to_local_map:
                    # 这是全局指针指向局部变量的解引用
                    mapping_info = self.global_pointer_to_local_map[pointer_key]
                    target_var = mapping_info["local_var"]
                    return {
                        'base_name': target_var,  # 返回实际的局部变量
                        'full_expression': f"*{base_info['base_name']}",
                        'index': None,
                        'is_pointer_deref': True,
                        'pointer_name': base_info['base_name'],  # 保存原始指针名
                        'is_global_pointer': True,
                        'target_function': mapping_info["function"]
                    }
                else:
                    # 普通指针解引用
                    return {
                        'base_name': base_info['base_name'],
                        'full_expression': f"*{base_info['base_name']}",
                        'index': None,
                        'is_pointer_deref': True,
                        'is_local_pointer': False
                    }
        elif isinstance(node, self.c_ast.ArrayRef):
            # 递归获取数组基础变量
            base_info = self._extract_variable_from_node(node.name)
            if base_info:
                index_text = self._get_node_text(node.subscript) if node.subscript else None
                full_expr = f"{base_info['full_expression']}[{index_text}]" if index_text else base_info['full_expression']
                return {
                    'base_name': base_info['base_name'],
                    'full_expression': full_expr,
                    'index': index_text,
                    'is_pointer_deref': base_info.get('is_pointer_deref', False),
                    'is_local_pointer': base_info.get('is_local_pointer', False)
                }
        elif isinstance(node, self.c_ast.StructRef):
            # 处理结构体/联合体成员访问
            base_info = self._extract_variable_from_node(node.name)
            if base_info:
                member_name = node.field.name if hasattr(node.field, 'name') else str(node.field)
                full_expr = f"{base_info['full_expression']}.{member_name}"
                return {
                    'base_name': base_info['base_name'],
                    'full_expression': full_expr,
                    'index': None,
                    'member': member_name,
                    'is_pointer_deref': base_info.get('is_pointer_deref', False),
                    'is_local_pointer': base_info.get('is_local_pointer', False)
                }
        return None
    
    def _get_node_text(self, node):
        """获取节点的文本表示"""
        # 优先使用 CGenerator 统一还原为 C 表达式，避免出现 Cast(...) 这类 AST 文本
        if self.generator is not None:
            try:
                return self.generator.visit(node)
            except Exception:
                # 失败时退回到原有的手工逻辑
                pass

        if isinstance(node, self.c_ast.ID):
            return node.name
        elif isinstance(node, self.c_ast.Constant):
            return node.value
        elif isinstance(node, self.c_ast.ArrayRef):
            base = self._get_node_text(node.name)
            index = self._get_node_text(node.subscript) if node.subscript else ''
            return f"{base}[{index}]"
        elif isinstance(node, self.c_ast.StructRef):
            base = self._get_node_text(node.name)
            member = node.field.name if hasattr(node.field, 'name') else str(node.field)
            return f"{base}.{member}"
        elif isinstance(node, self.c_ast.BinaryOp):
            left = self._get_node_text(node.left)
            right = self._get_node_text(node.right)
            return f"{left} {node.op} {right}"
        elif isinstance(node, self.c_ast.UnaryOp):
            expr = self._get_node_text(node.expr)
            if node.op == '*':
                return f"*{expr}"  # 指针解引用
            elif node.op in ['++', '--']:
                return f"{node.op}{expr}"
            elif node.op == 'p++':
                return f"{expr}++"  # 后置递增
            elif node.op == 'p--':
                return f"{expr}--"  # 后置递减
            else:
                return f"{node.op} {expr}"
        elif isinstance(node, self.c_ast.FuncCall):
            # 处理函数调用
            func_name = self._get_node_text(node.name)
            if node.args:
                args = []
                for arg in node.args:
                    args.append(self._get_node_text(arg))
                return f"{func_name}({', '.join(args)})"
            else:
                return f"{func_name}()"
        else:
            # 最后的兜底，保证不会抛异常
            return str(node)
    
    def _get_assignment_text(self, node):
        """获取赋值语句的文本"""
        left = self._get_node_text(node.lvalue)
        right = self._get_node_text(node.rvalue)
        return f"{left} {node.op} {right}"
    
    def _find_read_variables_in_lvalue(self, node):
        """
        专门处理左值表达式中的隐含读操作
        (例如提取 arr[i].f = 1 中的 i，但不提取 arr 或 f)
        """
        if isinstance(node, self.c_ast.ID):
            # 基础变量名作为左值，不读
            pass
        elif isinstance(node, self.c_ast.ArrayRef):
            # arr[i] -> i 要读
            self._find_read_variables(node.subscript)
            # 递归检查 arr 部分（例如 arr[j][i]）
            self._find_read_variables_in_lvalue(node.name)
        elif isinstance(node, self.c_ast.StructRef):
            if node.type == '->':
                # p->f -> p 需要读（因为要解引用指针）
                self._find_read_variables(node.name)
            else:
                # s.f -> s 只是左值的一部分，本身不读，但递归检查 s 内部（如 arr[i].f）
                self._find_read_variables_in_lvalue(node.name)
        elif isinstance(node, self.c_ast.UnaryOp) and node.op == '*':
            # *p -> p 需要读
            self._find_read_variables(node.expr)
        else:
            # 其他复杂情况，不做处理
            pass

    def _find_read_variables(self, node):
        """递归查找读取的变量"""
        if not node:
            return
            
        try:
            if isinstance(node, self.c_ast.ID):
                var_name = node.name
                if self._is_global_variable(var_name):
                    line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset

                    # 使用AST节点的坐标信息进行精确去重，避免过滤掉同一行内的多个相同变量读取
                    coord_info = getattr(node, 'coord', None)
                    if coord_info:
                        # 使用行列坐标作为唯一标识，允许同一行内的多个相同变量读取
                        operation_key = (var_name, "read", self.current_function, coord_info.line, coord_info.column)
                    else:
                        # 如果没有坐标信息，使用节点的内存地址
                        operation_key = (var_name, "read", self.current_function, line_num, id(node))

                    # 检查是否已经记录过完全相同的操作（基于坐标的精确匹配）
                    if hasattr(self, '_recorded_operations'):
                        if operation_key in self._recorded_operations:
                            # 这是真正的重复（相同的坐标），跳过
                            return
                        self._recorded_operations.add(operation_key)
                    else:
                        self._recorded_operations = set()
                        self._recorded_operations.add(operation_key)

                    operation = {
                        "operation_type": "read",
                        "variable": var_name,
                        "variable_expression": var_name,
                        "index": None,
                        "value": None,
                        "line_number": line_num,
                        "function": self.current_function,
                        "code_line": self._get_node_text(node),
                        "file_path": self.file_path
                    }
                    self.variable_operations.append(operation)
            elif isinstance(node, self.c_ast.UnaryOp) and node.op == '*':
                # 处理指针解引用的读取操作
                var_info = self._extract_variable_from_node(node)
                if var_info and (self._is_global_variable(var_info['base_name']) or 
                                var_info.get('is_local_pointer', False) or 
                                var_info.get('is_global_pointer', False)):
                    line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                    operation = {
                        "operation_type": "read",
                        "variable": var_info['base_name'],
                        "variable_expression": var_info['full_expression'],
                        "index": None,
                        "value": None,
                        "line_number": line_num,
                        "function": self.current_function,
                        "code_line": self._get_node_text(node),
                        "file_path": self.file_path
                    }
                    # 如果是局部指针，添加额外信息
                    if var_info.get('is_local_pointer', False):
                        operation['pointer_name'] = var_info.get('pointer_name', '')
                        operation['is_pointer_deref'] = True
                    # 如果是全局指针，添加额外信息
                    elif var_info.get('is_global_pointer', False):
                        operation['pointer_name'] = var_info.get('pointer_name', '')
                        operation['is_pointer_deref'] = True
                        operation['is_global_pointer'] = True
                        operation['target_function'] = var_info.get('target_function', '')
                    self.variable_operations.append(operation)
            elif isinstance(node, self.c_ast.ArrayRef):
                var_info = self._extract_variable_from_node(node)
                if var_info and self._is_global_variable(var_info['base_name']):
                    line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                    operation = {
                        "operation_type": "read",
                        "variable": var_info['base_name'],
                        "variable_expression": var_info['full_expression'],
                        "index": var_info['index'],
                        "value": None,
                        "line_number": line_num,
                        "function": self.current_function,
                        "code_line": self._get_node_text(node),
                        "file_path": self.file_path
                    }
                    self.variable_operations.append(operation)
            elif isinstance(node, self.c_ast.StructRef):
                var_info = self._extract_variable_from_node(node)
                if var_info and self._is_global_variable(var_info['base_name']):
                    line_num = (getattr(node, 'coord').line if hasattr(node, 'coord') and node.coord else self.current_line) - self.line_offset
                    operation = {
                        "operation_type": "read",
                        "variable": var_info['base_name'],
                        "variable_expression": var_info['full_expression'],
                        "index": None,
                        "member": var_info.get('member'),
                        "value": None,
                        "line_number": line_num,
                        "function": self.current_function,
                        "code_line": self._get_node_text(node),
                        "file_path": self.file_path
                    }
                    self.variable_operations.append(operation)
            else:
                # 递归处理子节点
                for child_name, child in node.children():
                    self._find_read_variables(child)
                    
        except Exception as e:
            print(f"查找读取变量时出错: {e}")
    
    def _is_global_variable(self, var_name):
        """判断是否是全局变量"""
        return var_name in self.global_vars and var_name not in self.local_vars


# 便利函数
def extract_variable_operations(content: str, file_path: str,
                                global_variable_extractor: GlobalVariableExtractor,
                                interrupt_function_patterns: List[str],
                                main_function_patterns: List[str],
                                regular_function_patterns: List[str]) -> List[Dict[str, Any]]:
    """
    提取变量操作的便利函数

    Args:
        content: C代码内容
        file_path: 文件路径
        global_variable_extractor: 全局变量提取器实例
        interrupt_function_patterns: 中断函数匹配模式列表
        main_function_patterns: 主函数匹配模式列表
        regular_function_patterns: 普通函数匹配模式列表

    Returns:
        变量操作列表
    """
    extractor = VariableOperationExtractor(
        global_variable_extractor,
        interrupt_function_patterns,
        main_function_patterns,
        regular_function_patterns
    )
    return extractor.extract_variable_operations(content, file_path)
