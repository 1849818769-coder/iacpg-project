import os
import tree_sitter
from tree_sitter import Parser
import tree_sitter_c as tsc
import chardet
import shutil
import json
import logging


class ASTLanguage:
    """AST解析器初始化类"""
    def __init__(self):
        self.language = tree_sitter.Language(tsc.language())
        self.parser = Parser(self.language)


class FileCleaner:
    """代码清理工具类"""
    def clean_code(self, path, node):
        result_dict = []
        for index, child in enumerate(node.children):
            content = child.text.decode('utf-8').strip()
            if child.type == "comment":
                content = self._process_comment(content)
            elif child.type == "function_definition":
                content = self._process_function(content)
            elif child.type in ["struct_specifier", "type_definition", "enum_specifier"]:
                content = self._process_struct(content)
            
            result_dict.append({
                "path": path,
                "id": index, 
                "type": child.type, 
                "content": content,
                "name": self._get_node_name(child),
                "row_position": (child.start_point.row, child.end_point.row)
            })
        return result_dict
    
    def _process_comment(self, content):
        return '\n'.join([line.strip() for line in content.splitlines() if line.strip() != ''])
    
    def _process_function(self, content):
        lines = [line.strip() for line in content.splitlines() if line.strip() != '']
        return '\n'.join(lines)
    
    def _process_struct(self, content):
        return '\n'.join([line.strip() for line in content.splitlines() if line.strip() != ''])
    
    def _get_node_name(self, node):
        if node.type == "function_definition":
            return node.child_by_field_name('type').text.decode() + ' ' + node.child_by_field_name('declarator').text.decode()
        return ''


class PathWalker:
    """路径遍历工具类"""
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def walk_directory(self, start_path):
        if not os.path.exists(start_path):
            self.logger.error(f"The path {start_path} does not exist.")
            return {}
        
        path_dict = {}
        for root, dirs, files in os.walk(start_path):
            if files:
                path_dict[root] = [os.path.join(root, file) for file in files]
        return path_dict


class CallGraphBuilder:
    """函数调用关系构建类"""
    def build_call_graph(self, original_data):
        callers_map = {}
        for file_func in original_data:
            for item in file_func:
                func_name = item['func_name']
                for caller in item['call_func']:
                    if caller not in callers_map:
                        callers_map[caller] = set()
                    callers_map[caller].add(func_name)
        
        desired_data = []
        for func_name, callers in callers_map.items():
            desired_data.append({
                "func_name": func_name,
                "called_func": list(callers)
            })
        
        for file in original_data:
            for item in file:
                if item['func_name'] not in callers_map:
                    desired_data.append({
                        "func_name": item['func_name'],
                        "called_func": []
                    })
        
        return desired_data

class ParserFunction:
    """解析函数类"""
    def __init__(self):

        self.function_parameters = []
        self.function_variable_list = []         # 局部变量定义
        self.function_variable = []      # 局部变量
        self.function_calls_list = []        # 调用函数名称
        self.function_all_variable_set = set()        # 函数全部变量
        self.comments = []

    def parse_array_declarator(self, array_type, child_node):
        if child_node.type == "identifier" :
            self.function_parameters.append({
                    "type": array_type, 
                    "parameter":  child_node.text.decode('utf-8').strip()})
        elif child_node.type == "array_declarator":
            self.parse_array_declarator(array_type, child_node.child_by_field_name('declarator'))  

    # 解析形参
    def parse_function_parameters(self, node):  
        for child in node.children:
            if child.type == 'parameter_declaration' and  (child.child_by_field_name('declarator') != None):
                if child.child_by_field_name('declarator').type == 'identifier':                   
                    self.function_parameters.append({
                        "type": child.child_by_field_name('type').text.decode('utf-8').strip(), 
                        "parameter":  child.child_by_field_name('declarator').text.decode('utf-8').strip()})
                        
                elif child.child_by_field_name('declarator').type == 'array_declarator':
                    array_type = child.child_by_field_name('type').text.decode('utf-8').strip()
                    self.parse_array_declarator(array_type, child.child_by_field_name('declarator'))
                    
                else:
                    self.function_parameters.append({
                        "type": child.child_by_field_name('type').text.decode('utf-8').strip(), 
                        "parameter": child.child_by_field_name('declarator').children[1].text.decode('utf-8').strip()})

        return self.function_parameters

    # 解析函数，包括局部变量和调用关系
    def parse_function_inside(self, node):
        # 解析局部变量 
        if node.type == 'declaration':
            self.function_variable_list.append(node.text.decode('utf-8').strip())
            if node.child_by_field_name('declarator').child_by_field_name('declarator') != None:
                self.function_variable.append({
                "type": node.child_by_field_name('type').text.decode('utf-8').strip(),
                "parameter": node.child_by_field_name('declarator').child_by_field_name('declarator').text.decode('utf-8').strip() 
                if node.child_by_field_name('declarator').child_by_field_name('declarator').type == 'identifier' 
                else node.child_by_field_name('declarator').child_by_field_name('declarator').children[1].text.decode('utf-8').strip()})
            else:
                for child in node.children:
                    if child.type == "identifier":
                        self.function_variable.append(
                            {
                                "type": node.child_by_field_name('type').text.decode('utf-8').strip(),
                                "parameter": child.text.decode("utf-8").strip()
                            }
                )
        if node.type == "comment":
            self.comments += (node.text.decode('utf-8').strip() + '\n')

        # 解析调用关系
        elif node.type == 'call_expression':
            if node.child_by_field_name('function').type == "identifier":
                self.function_calls_list.append(node.children[0].text.decode('utf-8').strip())
            for child in node.children:
                if child.type == 'parenthesized_expression' and child.children[1].type == 'identifier' and node.type == "call_expression":
                    print("Att: ", node.text)
                    continue
                elif child.type in ['(', ')', '[', ']', '{', '}']:
                    continue
                elif child.type == "argument_list":
                    for child_node in child.children:
                        if child_node.type == "identifier":
                            self.function_all_variable_set.add(child_node.text.decode('utf-8').strip())
                # self.parse_function_inside(child)

        # 解析全部变量 
        elif node.type == 'identifier':
            if node.text not in [b'TRUE32', b'FALSE32']:
                self.function_all_variable_set.add(node.text.decode('utf-8').strip())
        # 递归遍历子节点
        else:
            for child in node.children:
                if child.type == 'parenthesized_expression' and child.children[1].type == 'identifier' and node.type == "call_expression":
                    print("Att: ", node.text)
                    continue
                elif child.type in ['(', ')', '[', ']', '{', '}']:
                    continue
                
                self.parse_function_inside(child)
    
    def parse_function_global_variable(self):
        to_remove = set()
        for param in self.function_all_variable_set:
            for temp in self.function_variable + self.function_parameters:
                if param == temp['parameter']:
                    to_remove.add(param)

        # 去除元素
        self.function_global_variable_set = self.function_all_variable_set - to_remove

    def get_func_info(self):
        return [
            self.function_variable_list, 
            self.function_variable, 
            self.function_calls_list, 
            self.function_global_variable_set
            ]


class VariableCleaner:
    """变量清理工具类"""
    def clean_global_vars(self, all_data):
        for data in all_data:
            cleaned_content = [line for line in data['global_variable']['content'] if 'extern' not in line]
            data['global_variable']['nums'] = len(cleaned_content)
            data['global_variable']['content'] = cleaned_content
        return all_data


class ASTNodeParser:
    """AST节点解析类"""
    def __init__(self, write_file, file_path):
        self.write_file = write_file
        self.file_path = file_path
        self.include = []
        self.define = []
        self.define_func = []
        self.define_if = []
        self.comment = []
        self.type_defs = []
        self.global_variables = []
        self.functions = []
        self.struct = []
        self.enum = []
        
        self.include_nums = 0
        self.define_nums = 0
        self.define_func_nums = 0
        self.define_if_nums = 0
        self.comment_nums = 0
        self.type_defs_nums = 0
        self.global_variables_nums = 0
        self.functions_nums = 0
        self.struct_nums = 0
        self.enum_nums = 0
        
        self.call_relation = []
        self.func_names = []
    

    def parse_node(self, node):
        for child in node.children:
            self._process_node(child)

    # 解析文件    
    def _process_node(self, node, flag = True):
        node_type = node.type
        content = node.text.decode('utf-8').strip()
        if node_type == 'preproc_include':
            self._handle_include(content)
        elif node_type == 'preproc_def':
            self._handle_define(content)
        elif node_type == 'preproc_function_def':
            self._handle_define_func(content)
        elif node_type == 'preproc_ifdef':
            if self.file_path.endswith('.h') and flag:
                for node in node.children:
                    self._process_node(node, False)
            self._handle_define_if(content)
        elif node_type == 'preproc_if':
            self._handle_define_if(content)
        elif node_type == 'type_definition':
            self._handle_type_def(content)
        elif node_type == 'comment':
            comment_line_list = [i.strip() for i in content.splitlines() if i.strip() != '']
            if len(comment_line_list) > 1:
                new_content = ''
                for cl in comment_line_list:
                    new_content += (cl + '\n')
                content = new_content
            self._handle_comment(content)
        elif node_type == 'struct_specifier':
            self._handle_struct(content)
        elif node_type == 'enum_specifier':
            self._handle_enum(content)
        elif node_type == 'declaration':
            self._handle_global_variable(node, content)
        elif node_type == 'function_definition':
            self._handle_function_definition(node, content)
    
    def _handle_include(self, content):
        self.include_nums += 1
        self.include.append(content) # 头文件列表

    def _handle_define(self, content):
        self.define_nums += 1
        self.define.append(content) # 宏变量

    def _handle_define_func(self, content):
        self.define_func_nums += 1
        self.define_func.append(content) # 宏定义函数

    def _handle_define_if(self, content):  
        self.define_if_nums += 1
        self.define_if.append(content) 

    def _handle_type_def(self, content):
        self.type_defs_nums += 1
        self.type_defs.append(content)

    def _handle_comment(self, content):
        self.comment_nums += 1
        self.comment.append(content)
    
    def _handle_struct(self, content):
        self.struct_nums += 1
        self.struct.append(content) # 结构体变量列表
    def _handle_enum(self, content):
        self.enum_nums += 1
        self.enum.append(content)

    def _handle_global_variable(self, node, content):
        if node.child_by_field_name("declarator").type != 'function_declarator':
            self.global_variables_nums += 1
            self.global_variables.append(content) # 全局变量列表

    # 解析函数
    def _handle_function_definition(self, node, content):
        self.functions_nums += 1 
        function_variable_list = []         # 局部变量定义
        function_variable = []      # 局部变量
        function_calls_list = []        # 调用函数名称
        function_all_variable_set = set()        # 函数全部变量
        function_parameters = []        # 形参
        function_declararor = node.child_by_field_name('declarator').child_by_field_name('parameters')       
        parserfunction = ParserFunction()

        # 解析形参
        if function_declararor is not None:
            function_parameters = parserfunction.parse_function_parameters(function_declararor)
            # self.parse_function_parameters()
        elif node.child_by_field_name("declarator").type == "pointer_declarator": # 指针类型处理
            if node.child_by_field_name("declarator").child_by_field_name("declarator").child_by_field_name('parameters') is not None:
                function_declararor = node.child_by_field_name("declarator").child_by_field_name("declarator").child_by_field_name('parameters')
            else:
                function_declararor =  node.child_by_field_name("declarator").child_by_field_name("declarator").child_by_field_name("declarator").child_by_field_name('parameters')
            if function_declararor is not None:
                parserfunction.parse_function_parameters(function_declararor)            
            else:
                print("指针类型函数声明, 形参异常!")

        elif node.children[1].type == "ERROR" and node.children[1].text == b'struct':
            self.struct_nums += 1
            content = node.text.decode('utf-8').strip()
            comment_line_list = [i.strip() for i in content.splitlines() if i.strip() != '']
            if len(comment_line_list) > 1:
                new_content = ''
                for cl in comment_line_list:
                    new_content += (cl + '\n')
                content = new_content
            else:
                content = content
            self.struct.append(content) # 结构体变量列表
            return
        else:
            print("形参处理异常!!!")
            return

        body_node = node.child_by_field_name('body')
        
        # 解析全部变量，调用关系等
        parserfunction.parse_function_inside(body_node)
        parserfunction.parse_function_global_variable()

        [function_variable_list, function_variable, function_calls_list, function_global_variable_set] = parserfunction.get_func_info()
 
        fun_name = node.child_by_field_name('declarator').children[0].text.decode('utf-8').strip() if node.child_by_field_name('declarator').type == 'function_declarator' else node.child_by_field_name('declarator').child_by_field_name('declarator').children[0].text.decode('utf-8').strip()

        C_file_path = f"{self.write_file}/{fun_name}.c"
        with open(C_file_path, 'w', encoding='utf-8') as file:
            file.write(node.text.decode('utf-8').strip())

        self.call_relation.append({
            "func_name": fun_name,
            "call_func": list(function_calls_list)
            })

        func_content = {
            "func_name": fun_name,
            "func_code": node.text.decode('utf-8').strip(),
            "global_variable": list(function_global_variable_set),
            "func_variable": function_variable,
            "func_parameter": function_parameters,
            "func_file": self.file_path,
            "start_line": node.start_point.row + 1,
            "end_line": node.end_point.row + 1,
            "call_func": list(function_calls_list)
        }
        self.func_names.append(fun_name)
        self.functions.append(func_content)
        if func_content is not None and self.write_file != "":
            with open(self.write_file + fun_name + ".json",  'w') as f:
                json.dump(func_content, f, ensure_ascii=False, indent=4)


    def get_result(self):
        result_dict = {
            "path": self.file_path,
            "include": {"nums": self.include_nums, "content": self.include},
            "define": {"nums": self.define_nums, "content": self.define},
            "define_func": {"nums": self.define_func_nums, "content": self.define_func},
            "define_if": {"nums": self.define_if_nums, "content": self.define_if},
            "comment": {"nums": self.comment_nums, "content": self.comment},
            "type_def": {"nums": self.type_defs_nums, "content": self.type_defs},
            "global_variable": {"nums": self.global_variables_nums, "content": self.global_variables},
            "struct": {"nums": self.struct_nums, "content": self.struct},
            "enum": {"nums": self.enum_nums, "content": self.enum},
            "function": {"nums": self.functions_nums, "content": self.functions}
            }

        return result_dict

class CodeAnalyzer:
    """主分析类"""
    def __init__(self, project_path):
        self.ast_language = ASTLanguage()
        self.file_cleaner = FileCleaner()
        self.path_walker = PathWalker()
        self.call_graph_builder = CallGraphBuilder()
        self.variable_cleaner = VariableCleaner()
        # 解析项目地址
        self.project_path = project_path

    def detect_encoding(self, file_path):
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read(4096))
        return result['encoding']
    
    def analyze_file(self, file_path, slice_path):
        encode = self.detect_encoding(file_path)
        with open(file_path, 'r', encoding=encode, errors='ignore') as f:
            content = f.read()
              
        write_file = os.path.join(self.project_path, slice_path, "functions/")
        os.makedirs(write_file, exist_ok=True)
               
        tree = self.ast_language.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
    
        ast_parser = ASTNodeParser(write_file, file_path)
        
        ast_parser.parse_node(root_node)
        
        clean_dict = self.file_cleaner.clean_code(file_path, root_node)
        
        return [ast_parser.get_result(), clean_dict], ast_parser.call_relation, ast_parser.func_names
    
    def called_expression(self, original_data):
        
        # Step 1: Create a dictionary to map function names to callers
        callers_map = {}
        for file_func in original_data:
            for item in file_func:
                func_name = item['func_name']
                for caller in item['call_func']:
                    if caller not in callers_map:
                        callers_map[caller] = set()
                    callers_map[caller].add(func_name)

        # Step 3: Create the new list in the desired format
        desired_data = []
        for func_name, callers in callers_map.items():
            desired_data.append({
                "func_name": func_name,
                "called_func": list(callers)
            })

        # Add functions that are not called by any other function
        for file in original_data:
            for item in file:
                if item['func_name'] not in callers_map:
                    desired_data.append({
                        "func_name": item['func_name'],
                        "called_func": []
                    })

        # Print the result
        # print(desired_data)
        return desired_data

    def code_slice_main(self):
        filter_type_list = ['.h', '.c', '.C', '.H']
        slice_path = "../split_code"
        
        if os.path.exists(os.path.join(self.project_path, slice_path)):
            shutil.rmtree(os.path.join(self.project_path, slice_path))
        
        path_dict = self.path_walker.walk_directory(self.project_path)
        results = []
        global_var = []
        call_relations = []
        function_names = []
        struct_var = []
        define_funcs = []
        all_info = []
        type_def = []
        define = []
        for root, files in path_dict.items():
            for file in files:
                if os.path.splitext(file)[1] in filter_type_list:

                    res, call, func_names = self.analyze_file(file, slice_path)
                    results.append(res)
                    function_names.extend(func_names)
                    data = res[0]
                    call_relations.append(call)
                    
                    # 结果处理逻辑...
                    file_global_var = {}
                    file_global_var["path"] = file
                    file_global_var["global_variable"] = data.get('global_variable', {})
                    global_var.append(file_global_var)
                    
                    file_struct_var = {}
                    file_struct_var["path"] = file
                    file_struct_var["struct"] = data.get('struct', {})
                    struct_var.append(file_struct_var)

                    file_define_funcs = {}
                    file_define_funcs["path"] = file
                    file_define_funcs["define_func"] = data.get('define_func', {})
                    define_funcs.append(file_define_funcs)

                    file_info = {}
                    file_info["path"] = file
                    file_info["global_variable"] = data.get('global_variable', {})
                    file_info["struct"] = data.get('struct', {})
                    file_info["define"] = data.get('define', {})
                    all_info.append(file_info)

                    type_def_info = {}
                    type_def_info["path"] = file
                    type_def_info["type_def"] = data.get('type_def', {})
                    type_def.append(type_def_info)

                    file_define = {}
                    file_define["path"] = file
                    file_define["define"] = data.get("define", {})
                    define.append(file_define)

        functions = {
            "resCode": 0,
            "message": "success",
            "func_list": function_names
        }

        # 结果保存
        result_dir = os.path.join(self.project_path, slice_path, "summary/")
        if not os.path.exists(result_dir):
            os.makedirs(result_dir, exist_ok=True)
        
        func_list_file = os.path.join(result_dir, 'functions.json')
        with open(func_list_file, 'w') as f:
            json.dump(functions, f, ensure_ascii=False, indent=4)
        
        type_def_file = os.path.join(result_dir, 'type_def.json')
        with open(type_def_file, 'w') as f:
            json.dump(type_def, f, ensure_ascii=False, indent=4)

        def_file = os.path.join(result_dir, 'define.json')
        with open(def_file, 'w') as f:
            json.dump(define, f, ensure_ascii=False, indent=4)

        global_var_file = os.path.join(result_dir, 'global_var.json')
        with open(global_var_file, 'w') as f:
            json.dump(global_var, f, ensure_ascii=False, indent=4)

        clean_global_var_file = os.path.join(result_dir, 'clean_global_var.json')
        clean_global_var = self.variable_cleaner.clean_global_vars(global_var)
        # Write the updated JSON data to a new file
        with open(clean_global_var_file, 'w') as outfile:
            json.dump(clean_global_var, outfile, ensure_ascii=False, indent=4)

        call_express_file = os.path.join(result_dir, 'call_express.json')
        with open(call_express_file, 'w') as f:
            json.dump(call_relations, f, ensure_ascii=False, indent=4)

        called_relation = self.called_expression(call_relations)
        called_relation_file = os.path.join(result_dir, 'called_relation.json')
        with open(called_relation_file, 'w') as f:
            json.dump(called_relation, f, ensure_ascii=False, indent=4)

        struct_var_file = os.path.join(result_dir, 'struct_var.json')
        with open(struct_var_file, 'w') as f:
            json.dump(struct_var, f, ensure_ascii=False, indent=4)

        define_funcs_file = os.path.join(result_dir, 'define_funcs.json')
        with open(define_funcs_file, 'w') as f:
            json.dump(define_funcs, f, ensure_ascii=False, indent=4)
        
        all_info_file = os.path.join(result_dir, 'all_info.json')
        with open(all_info_file, 'w') as f:
            json.dump(all_info, f, ensure_ascii=False, indent=4)
        
        summarize_data_list = [json.loads(json.dumps(data[0])) for data in results]
        clean_data_list = [json.loads(json.dumps(data[1])) for data in results]
        
        # 使用pickle将数据写入二进制文件
        summarize_file = os.path.join(result_dir, 'summarize'+'.json')

        with open(summarize_file, 'w') as f:
            json.dump(summarize_data_list, f, ensure_ascii=False, indent=4)
            # pickle.dump(summarize_data_list, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        clean_file = os.path.join(result_dir, 'clean' + '.json')

        with open(clean_file,'w') as f:
            json.dump(clean_data_list, f, ensure_ascii=False, indent=4)
            # pickle.dump(clean_data_list, f, protocol=pickle.HIGHEST_PROTOCOL)

if __name__ == "__main__":
    project_path = r"./testfiles/2.1_remarks/svp_simple_032"
    analyzer = CodeAnalyzer(project_path)
    rslt = analyzer.code_slice_main()