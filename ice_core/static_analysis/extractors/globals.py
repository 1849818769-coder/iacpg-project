"""
全局变量提取API
提供从源代码中提取全局变量的功能
"""
import re
import tree_sitter
from tree_sitter import Parser
import tree_sitter_c as tsc
import chardet
from typing import List, Dict, Any


class GlobalVariableExtractor:
    """全局变量提取器"""

    def __init__(self):
        """初始化全局变量提取器"""
        # 初始化tree-sitter
        self.language = tree_sitter.Language(tsc.language())
        self.parser = Parser(self.language)

    def _detect_encoding(self, file_path: str) -> str:
        """检测文件编码"""
        try:
            with open(file_path, 'rb') as f:
                result = chardet.detect(f.read(4096))
            return result.get('encoding', 'utf-8') or 'utf-8'
        except:
            return 'utf-8'

    def extract_global_variables(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        提取全局变量

        Args:
            content: 源代码内容
            file_path: 文件路径

        Returns:
            全局变量列表，每个变量包含以下信息：
            - name: 变量名
            - type: 变量类型
            - data_structure: 数据结构类型（array, pointer, struct, union, enum, primitive）
            - declaration: 变量声明
            - file_path: 文件路径
            - line_number: 行号
            - is_interrupt_related: 是否与中断相关
            - initial_value: 初始化值（如果存在）
        """
        global_variables = []

        # 解析代码为AST
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node

        # 遍历AST查找全局变量声明
        self._extract_from_ast(root_node, content, file_path, global_variables)

        return global_variables

    def _get_full_type(self, declaration_node) -> str:
        """获取声明的完整类型（包括修饰符）"""
        type_parts = []

        for child in declaration_node.children:
            if child.type in ['type_qualifier', 'storage_class_specifier']:
                type_parts.append(child.text.decode('utf-8').strip())
            elif child.type in ['primitive_type', 'type_identifier', 'sized_type_specifier']:
                type_parts.append(child.text.decode('utf-8').strip())
            elif child.type == 'struct_specifier' or child.type == 'union_specifier' or child.type == 'enum_specifier':
                # 处理结构体、联合体、枚举
                type_text = child.text.decode('utf-8').strip()
                # 只保留类型定义的关键部分
                if child.type == 'struct_specifier':
                    type_parts.append('struct')
                    # 尝试获取结构体名称
                    for subchild in child.children:
                        if subchild.type == 'type_identifier':
                            type_parts.append(subchild.text.decode('utf-8').strip())
                            break
                elif child.type == 'union_specifier':
                    type_parts.append('union')
                elif child.type == 'enum_specifier':
                    type_parts.append('enum')
                break  # 找到主要类型后停止

        return ' '.join(type_parts)

    def _extract_from_ast(self, node, content: str, file_path: str, global_variables: List[Dict[str, Any]]):
        """从AST中提取全局变量"""
        if node.type == 'declaration':
            # 检查是否是全局变量声明（不在函数内部）
            if not self._is_inside_function(node):
                self._process_declaration_node(node, content, file_path, global_variables)
        else:
            # 递归遍历子节点
            for child in node.children:
                self._extract_from_ast(child, content, file_path, global_variables)

    def _is_inside_function(self, node) -> bool:
        """检查节点是否在函数内部"""
        current = node.parent
        while current:
            if current.type == 'function_definition':
                return True
            current = current.parent
        return False

    def _process_declaration_node(self, node, content: str, file_path: str, global_variables: List[Dict[str, Any]]):
        """处理声明节点，提取所有变量"""
        # 获取完整的类型（包括修饰符）
        full_type = self._get_full_type(node)

        # 处理声明节点中的所有声明器
        for child in node.children:
            if child.type == 'init_declarator':
                # 有初始化的声明器，如 "var = 0"
                var_info = self._extract_variable_info(child, full_type, node, content, file_path)
                if var_info:
                    # 检查是否已经存在相同名称的变量
                    existing_names = [v["name"] for v in global_variables]
                    if var_info["name"] not in existing_names:
                        global_variables.append(var_info)
            elif child.type == 'array_declarator':
                # 数组声明器，如 "arr[10000]"
                var_info = self._extract_array_variable_info(child, full_type, node, content, file_path)
                if var_info:
                    # 检查是否已经存在相同名称的变量
                    existing_names = [v["name"] for v in global_variables]
                    if var_info["name"] not in existing_names:
                        global_variables.append(var_info)
            elif child.type == 'pointer_declarator':
                # 指针声明器，如 "*ptr"
                var_name = self._get_declarator_name(child)
                if var_name:
                    declaration = node.text.decode('utf-8').strip()
                    line_number = node.start_point.row + 1
                    data_structure = 'pointer'

                    var_info = {
                        "name": var_name,
                        "type": full_type,
                        "data_structure": data_structure,
                        "declaration": declaration,
                        "file_path": file_path,
                        "line_number": line_number,
                        "initial_value": None
                    }

                    # 检查是否已经存在相同名称的变量
                    existing_names = [v["name"] for v in global_variables]
                    if var_name not in existing_names:
                        global_variables.append(var_info)
            elif child.type == 'identifier':
                # 简单的标识符声明，如 "int a, b, c;" 中的 a, b, c
                var_name = child.text.decode('utf-8').strip()
                declaration = node.text.decode('utf-8').strip()
                line_number = node.start_point.row + 1
                data_structure = self._analyze_data_structure_from_declaration(declaration)

                var_info = {
                    "name": var_name,
                    "type": full_type,
                    "data_structure": data_structure,
                    "declaration": declaration,
                    "file_path": file_path,
                    "line_number": line_number,
                    "initial_value": None  # 简单声明没有初始化值
                }

                # 检查是否已经存在相同名称的变量
                existing_names = [v["name"] for v in global_variables]
                if var_name not in existing_names:
                    global_variables.append(var_info)

    def _extract_variable_info(self, init_declarator_node, full_type: str, declaration_node, content: str, file_path: str) -> Dict[str, Any]:
        """从init_declarator节点提取变量信息"""
        try:
            # 获取变量名 - 在init_declarator中，第一个标识符就是变量名
            var_name = None
            initial_value = None

            for child in init_declarator_node.children:
                if child.type == 'identifier':
                    var_name = child.text.decode('utf-8').strip()
                elif child.type == '=':
                    # 找到等号，接下来应该是初始化值
                    continue
                elif child.type in ['number_literal', 'string_literal', 'initializer_list', 'cast_expression']:
                    # 这可能是初始化值
                    initial_value = child.text.decode('utf-8').strip()
                elif child.type == 'identifier' and var_name is None:
                    # 第一个标识符是变量名
                    var_name = child.text.decode('utf-8').strip()

            if not var_name:
                return None

            # 构建完整声明
            declaration = declaration_node.text.decode('utf-8').strip()

            # 确定行号
            line_number = declaration_node.start_point.row + 1

            # 分析数据结构类型
            data_structure = self._analyze_data_structure_from_declaration(declaration)

            return {
                "name": var_name,
                "type": full_type,
                "data_structure": data_structure,
                "declaration": declaration,
                "file_path": file_path,
                "line_number": line_number,
                "initial_value": initial_value
            }

        except Exception as e:
            print(f"提取变量信息失败: {e}")
            return None

    def _extract_array_variable_info(self, array_declarator_node, full_type: str, declaration_node, content: str, file_path: str) -> Dict[str, Any]:
        """从array_declarator节点提取数组变量信息"""
        try:
            # 获取变量名 - 在array_declarator中，第一个标识符就是变量名
            var_name = None

            for child in array_declarator_node.children:
                if child.type == 'identifier':
                    var_name = child.text.decode('utf-8').strip()
                    break

            if not var_name:
                return None

            # 构建完整声明
            declaration = declaration_node.text.decode('utf-8').strip()

            # 确定行号
            line_number = declaration_node.start_point.row + 1

            # 分析数据结构类型（数组）
            data_structure = 'array'

            return {
                "name": var_name,
                "type": full_type,
                "data_structure": data_structure,
                "declaration": declaration,
                "file_path": file_path,
                "line_number": line_number,
                "initial_value": None  # 数组声明通常没有初始化值，除非是初始化列表
            }

        except Exception as e:
            print(f"提取数组变量信息失败: {e}")
            return None

    def _get_declarator_name(self, declarator_node) -> str:
        """从声明器节点获取变量名"""
        if declarator_node.type == 'identifier':
            return declarator_node.text.decode('utf-8').strip()
        elif declarator_node.type == 'array_declarator':
            # 数组声明，如 arr[10]
            return self._get_declarator_name(declarator_node.child_by_field_name('declarator'))
        elif declarator_node.type == 'pointer_declarator':
            # 指针声明，如 *ptr
            return self._get_declarator_name(declarator_node.child_by_field_name('declarator'))
        elif declarator_node.type == 'function_declarator':
            # 函数声明，跳过（这应该在其他地方处理）
            return None
        else:
            # 其他情况，尝试查找标识符
            for child in declarator_node.children:
                if child.type == 'identifier':
                    return child.text.decode('utf-8').strip()
        return None


    def _analyze_data_structure_from_declaration(self, declaration: str) -> str:
        """从声明中分析数据结构类型"""
        declaration = declaration.strip()

        # 检查是否是数组
        if '[' in declaration and ']' in declaration:
            return 'array'

        # 检查是否是指针
        if '*' in declaration:
            return 'pointer'

        # 检查是否是结构体
        if declaration.startswith('struct '):
            return 'struct'

        # 检查是否是联合体
        if declaration.startswith('union '):
            return 'union'

        # 检查是否是枚举
        if declaration.startswith('enum '):
            return 'enum'

        # 检查是否是自定义类型（通过类型名推断）
        # 提取类型名（跳过修饰符如volatile, static, const）
        words = declaration.split()
        type_name = ""
        for word in words:
            if word not in ['volatile', 'static', 'const', 'extern']:
                type_name = word
                break

        # 检查是否是自定义类型（通常包含项目前缀）
        if type_name and ('svp_simple_' in type_name or '_union' in type_name or '_struct' in type_name):
            if '_union' in type_name:
                return 'union'
            elif '_struct' in type_name:
                return 'struct'
            else:
                # 通过类型名模式推断
                if 'union' in type_name.lower():
                    return 'union'
                elif 'struct' in type_name.lower():
                    return 'struct'

        # 默认是基本类型
        return 'primitive'