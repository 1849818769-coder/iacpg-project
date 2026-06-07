import subprocess
import time
import socket
import os
from typing import Optional, Any
from cpgqls_client import CPGQLSClient, import_code_query, workspace_query

# 尝试导入 psutil，如果没有则使用备用方案
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class JoernClient:
    """
    可复用的 Joern 客户端类（基于 cpgqls-client）
    
    特性：
    - 自动检测并复用已运行的服务器（8080端口）
    - 可以动态加载不同的代码/CPG
    - 显式关闭服务器
    """
    
    # 类级别变量：跟踪服务器状态
    _server_process: Optional[subprocess.Popen] = None
    _server_running: bool = False
    
    def __init__(self, joern_bin: str = "joern", joern_parse_bin: str = "joern-parse",
                 host: str = "127.0.0.1", port: int = 8080, 
                 auth_credentials: Optional[tuple] = None,
                 output_subdir: str = "joern"):
        """
        初始化 Joern 客户端
        
        Args:
            joern_bin: Joern 可执行文件路径
            joern_parse_bin: Joern parse 命令路径
            host: 服务器主机地址
            port: 服务器端口
            auth_credentials: 认证凭据 (username, password)，可选
            output_subdir: 输出文件保存的子目录名（相对于项目目录），默认为 "joern"
        """
        self.joern_bin = joern_bin
        self.joern_parse_bin = joern_parse_bin
        self.host = host
        self.port = port
        self.server_endpoint = f"{host}:{port}"
        self.auth_credentials = auth_credentials
        self.output_subdir = output_subdir  # 输出子目录名
        self.current_project: Optional[str] = None
        self.current_project_path: Optional[str] = None  # 当前项目的路径
        self.client: Optional[CPGQLSClient] = None
        
        # 确保服务器运行并创建客户端
        self.ensure_server()
    
    def get_output_dir(self) -> Optional[str]:
        """
        获取输出目录路径
        
        Returns:
            输出目录路径，如果项目路径未设置则返回 None
        """
        if self.current_project_path:
            output_dir = os.path.join(self.current_project_path, self.output_subdir)
            os.makedirs(output_dir, exist_ok=True)  # 确保目录存在
            return output_dir
        return None
    
    def _is_server_running(self) -> bool:
        """检查服务器是否正在运行"""
        try:
            # 先检查端口是否开放
            with socket.create_connection((self.host, self.port), timeout=1):
                # 端口开放，尝试发送一个健康检查请求确认是 Joern 服务器
                try:
                    import requests
                    # 尝试访问 Joern 的查询端点或根路径
                    resp = requests.get(f"http://{self.server_endpoint}/", timeout=2)
                    return resp.status_code in (200, 404, 405)  # 405 Method Not Allowed 也表示服务器在运行
                except Exception:
                    # 如果请求失败，但端口开放，可能是服务器还在启动中
                    # 尝试访问 /query 端点（POST 方法）
                    try:
                        import requests
                        resp = requests.post(f"http://{self.server_endpoint}/query", json={"query": ""}, timeout=2)
                        # 即使查询失败，只要不是连接错误，就说明服务器在运行
                        return True
                    except Exception:
                        return True  # 端口开放就认为服务器可能在运行
        except OSError:
            return False
    
    def _wait_for_port(self, timeout: int = 30) -> bool:
        """等待端口可用"""
        start = time.time()
        while time.time() - start < timeout:
            if self._is_server_running():
                return True
            time.sleep(1)
        return False
    
    def ensure_server(self):
        """确保服务器正在运行（如果未运行则启动）并创建客户端"""
        # 如果服务器已运行且客户端已创建，直接返回
        if JoernClient._server_running and self._is_server_running() and self.client:
            # print("[*] 复用已运行的 Joern 服务器和客户端")
            return
        
        # 检查服务器是否已在运行
        if self._is_server_running():
            print("[*] 检测到 Joern 服务器已在运行（8080端口），复用现有服务器")
            JoernClient._server_running = True
            # 创建客户端连接
            if not self.client:
                self.client = CPGQLSClient(
                    self.server_endpoint,
                    auth_credentials=self.auth_credentials
                )
            return
        
        # 启动新服务器
        print("[*] 启动 Joern REST 服务器...")
        JoernClient._server_process = subprocess.Popen(
            [self.joern_bin, "--server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        if self._wait_for_port(timeout=30):
            JoernClient._server_running = True
            # 创建客户端连接
            self.client = CPGQLSClient(
                self.server_endpoint,
                auth_credentials=self.auth_credentials
            )
            print(f"[✓] Joern 服务器已就绪: {self.server_endpoint}")
        else:
            JoernClient._server_process = None
            raise RuntimeError("❌ Joern 服务器在 30 秒内未能启动")
    
    
    def _find_process_by_port(self, port: int):
        """查找占用指定端口的进程"""
        if HAS_PSUTIL:
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        for conn in proc.connections():
                            if conn.laddr.port == port:
                                return proc
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
            except Exception:
                pass
        else:
            # 备用方案：使用 lsof 或 netstat 命令
            try:
                # 尝试使用 lsof
                result = subprocess.run(
                    ['lsof', '-ti', f':{port}'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    pid = int(result.stdout.strip().split('\n')[0])
                    return pid
            except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
                try:
                    # 尝试使用 netstat + awk
                    result = subprocess.run(
                        ['netstat', '-tlnp'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if f':{port}' in line and 'LISTEN' in line:
                                # 提取 PID（格式可能不同）
                                parts = line.split()
                                if len(parts) > 6:
                                    pid_str = parts[-1].split('/')[0]
                                    try:
                                        return int(pid_str)
                                    except ValueError:
                                        pass
                except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
                    pass
        return None
    
    def _kill_process_by_port(self, port: int) -> bool:
        """强制关闭占用指定端口的进程"""
        proc_or_pid = self._find_process_by_port(port)
        if proc_or_pid is None:
            return False
        
        try:
            if HAS_PSUTIL and isinstance(proc_or_pid, psutil.Process):
                # 使用 psutil
                proc = proc_or_pid
                print(f"[*] 找到占用 {port} 端口的进程: PID={proc.pid}, 名称={proc.name()}")
                proc.terminate()  # 先尝试优雅关闭
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()  # 强制关闭
                    proc.wait(timeout=2)
                print(f"[✓] 已关闭进程 PID={proc.pid}")
                return True
            else:
                # 使用 kill 命令
                pid = proc_or_pid if isinstance(proc_or_pid, int) else proc_or_pid.pid
                print(f"[*] 找到占用 {port} 端口的进程: PID={pid}")
                # 先尝试 SIGTERM
                subprocess.run(['kill', '-TERM', str(pid)], timeout=2)
                time.sleep(1)
                # 检查进程是否还在运行
                try:
                    subprocess.run(['kill', '-0', str(pid)], check=True, timeout=1)
                    # 如果还在运行，强制 kill
                    subprocess.run(['kill', '-KILL', str(pid)], timeout=2)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    pass  # 进程已结束
                print(f"[✓] 已关闭进程 PID={pid}")
                return True
        except Exception as e:
            print(f"⚠️  无法关闭进程: {e}")
            return False
    
    def close(self, force: bool = False):
        """
        关闭服务器
        
        Args:
            force: 如果为 True，即使服务器不是由本程序启动的也尝试关闭（会强制kill占用端口的进程）
        """
        # 检查服务器是否还在运行
        if not self._is_server_running():
            print("[*] 服务器已停止")
            JoernClient._server_running = False
            JoernClient._server_process = None
            self.client = None
            self.current_project = None
            self.current_project_path = None
            return
        
        # 如果服务器不是由本程序启动的，默认不关闭（除非 force=True）
        if not JoernClient._server_process and not force:
            print("[*] 服务器不是由本程序启动的，跳过关闭（使用 force=True 强制关闭）")
            return
        
        print("[*] 关闭 Joern 服务器...")
        
        # 方法1: 尝试通过 REST API 关闭
        try:
            import requests
            requests.get(f"http://{self.server_endpoint}/admin/shutdown", timeout=5)
            time.sleep(2)  # 等待服务器关闭
            if not self._is_server_running():
                print("[✓] 通过 REST API 关闭服务器成功")
                JoernClient._server_running = False
                JoernClient._server_process = None
                self.client = None
                self.current_project = None
                self.current_project_path = None
                return
        except Exception as e:
            print(f"[*] REST API 关闭失败: {e}")
        
        # 方法2: 如果服务器进程是由本程序启动的，等待进程结束
        if JoernClient._server_process:
            try:
                JoernClient._server_process.terminate()
                try:
                    JoernClient._server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    JoernClient._server_process.kill()
                    JoernClient._server_process.wait(timeout=2)
                JoernClient._server_process = None
                if not self._is_server_running():
                    print("[✓] 通过进程管理关闭服务器成功")
                    JoernClient._server_running = False
                    self.client = None
                    self.current_project = None
                    self.current_project_path = None
                    return
            except Exception as e:
                print(f"[*] 进程管理关闭失败: {e}")
        
        # 方法3: 强制关闭占用端口的进程（如果 force=True）
        if force:
            if self._kill_process_by_port(self.port):
                time.sleep(1)
                if not self._is_server_running():
                    print("[✓] 关闭服务器成功")
                    JoernClient._server_running = False
                    JoernClient._server_process = None
                    self.client = None
                    self.current_project = None
                    self.current_project_path = None
                    return
        
        # 检查最终状态
        if self._is_server_running():
            print("⚠️  服务器可能仍在运行，请手动检查")
        else:
            print("[✓] Joern 服务器已关闭")
            JoernClient._server_running = False
            JoernClient._server_process = None
            self.client = None
            self.current_project = None
            self.current_project_path = None
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False


    def create_cpg(self, source_dir: str, cpg_path: Optional[str] = None) -> str:
        """
        从源码目录创建 CPG 文件
        
        Args:
            source_dir: 源码目录路径
            cpg_path: 输出的 CPG 文件路径，如果为 None 或相对路径，则保存到项目目录下的 joern 子目录
            
        Returns:
            CPG 文件路径
        """
        source_dir = os.path.abspath(source_dir)
        
        # 如果 cpg_path 未指定或是相对路径，保存到项目目录下的 joern 子目录
        if cpg_path is None:
            project_name = os.path.basename(source_dir.rstrip('/'))
            output_dir = os.path.join(source_dir, self.output_subdir)
            os.makedirs(output_dir, exist_ok=True)
            cpg_path = os.path.join(output_dir, f"{project_name}.cpg.bin.zip")
        elif not os.path.isabs(cpg_path):
            # 相对路径，保存到项目目录下的 joern 子目录
            output_dir = os.path.join(source_dir, self.output_subdir)
            os.makedirs(output_dir, exist_ok=True)
            cpg_path = os.path.join(output_dir, cpg_path)
        
        print(f"[*] 从 {source_dir} 创建 CPG 到 {cpg_path}...")
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(cpg_path) if os.path.dirname(cpg_path) else ".", exist_ok=True)
        
        result = subprocess.run(
            [self.joern_parse_bin, source_dir, "-o", cpg_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"❌ 创建 CPG 失败: {result.stderr}")
        
        print(f"[✓] CPG 创建成功: {cpg_path}")
        return cpg_path
    
    def import_code(self, code_path: str, project_name: Optional[str] = None) -> dict:
        """
        导入代码到 Joern 服务器（使用 import_code_query）
        
        Args:
            code_path: 代码路径（可以是目录或文件）
            project_name: 项目名称，如果为 None 则使用路径的 basename
            
        Returns:
            导入结果
        """
        self.ensure_server()
        
        # 获取绝对路径
        code_path = os.path.abspath(code_path)
        
        if project_name is None:
            project_name = os.path.basename(code_path.rstrip('/'))
        
        print(f"[*] 导入代码: {code_path} (项目: {project_name})")
        
        try:
            query = import_code_query(code_path, project_name)
            result = self.client.execute(query)
            
            # 检查结果
            if 'stdout' in result:
                print(f"[✓] 代码导入成功: {result.get('stdout', '')}")
            elif 'stderr' in result and result['stderr']:
                print(f"⚠️  导入警告: {result['stderr']}")
            
            self.current_project = project_name
            # 记录项目路径（如果是目录）
            if os.path.isdir(code_path):
                self.current_project_path = code_path
            else:
                self.current_project_path = os.path.dirname(code_path)
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"❌ 导入代码失败: {e}")
    
    def query(self, query_str: str, save_result: bool = False, output_file: Optional[str] = None) -> Any:
        """
        执行 CPGQL/Gremlin 查询
        
        Args:
            query_str: 查询语句（Gremlin 或 CPGQL）
            save_result: 是否保存查询结果到文件
            output_file: 输出文件路径，如果为 None 且 save_result=True，则保存到项目目录下
            
        Returns:
            查询结果
        """
        self.ensure_server()
        
        # print(f"[*] 执行查询: {query_str}")
        
        try:
            # 直接执行查询字符串
            result = self.client.execute(query_str)
            
            # 如果是 workspace_query 的结果，提取 stdout
            if isinstance(result, dict) and 'stdout' in result:
                query_result = result['stdout']
            else:
                query_result = result
            
            # 如果需要保存结果
            if save_result:
                self.save_result(query_result, output_file)
            
            # print("[✓] 查询完成")
            return query_result
                
        except Exception as e:
            raise RuntimeError(f"❌ 查询执行失败: {e}")
    
    def save_result(self, result: Any, output_file: Optional[str] = None) -> str:
        """
        保存查询结果到文件
        
        Args:
            result: 查询结果
            output_file: 输出文件路径，如果为 None，则保存到项目目录下的 joern 子目录，文件名为 query_result.json
            
        Returns:
            保存的文件路径
        """
        import json
        
        # 获取输出目录
        output_dir = self.get_output_dir()
        
        # 确定输出文件路径
        if output_file is None:
            if output_dir:
                output_file = os.path.join(output_dir, "query_result.json")
            else:
                output_file = "query_result.json"
        elif not os.path.isabs(output_file):
            # 相对路径，保存到项目目录下的 joern 子目录
            if output_dir:
                output_file = os.path.join(output_dir, output_file)
            else:
                output_file = output_file
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
        
        # 保存结果
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                if isinstance(result, str):
                    # 清理 ANSI 颜色代码
                    import re
                    cleaned_result = re.sub(r'\x1b\[[0-9;]*m', '', result)
                    
                    # 尝试解析为 JSON
                    try:
                        result_obj = json.loads(cleaned_result)
                        json.dump(result_obj, f, indent=2, ensure_ascii=False)
                    except json.JSONDecodeError:
                        # 如果不是 JSON，直接保存清理后的字符串
                        f.write(cleaned_result)
                else:
                    json.dump(result, f, indent=2, ensure_ascii=False)
            
            print(f"[✓] 查询结果已保存到: {output_file}")
            return output_file
        except Exception as e:
            raise RuntimeError(f"❌ 保存查询结果失败: {e}")
    
    def workspace_query(self) -> dict:
        """
        执行工作区查询（获取当前工作区信息）
        
        Returns:
            工作区查询结果
        """
        self.ensure_server()
        
        print("[*] 执行工作区查询...")
        
        try:
            query = workspace_query()
            result = self.client.execute(query)
            print("[✓] 工作区查询完成")
            return result
        except Exception as e:
            raise RuntimeError(f"❌ 工作区查询失败: {e}")


# === 使用示例 ===
if __name__ == "__main__":
    # 示例：顺序处理多个数据集
    # 可以通过 output_subdir 参数自定义输出目录名（默认为 "joern"）
    client = JoernClient(output_subdir="joern")  # 自动检测并复用已运行的服务器（如果8080端口已启用）
    
    try:
        # 数据集 1：从源码导入
        print("\n=== 处理数据集 1 ===")
        SOURCE_DIR = "/home/abb/test"
        
        # 方式1: 创建 CPG（会自动保存到项目目录下的 joern 子目录）
        cpg_path = client.create_cpg(SOURCE_DIR)  # 不指定路径，自动保存到 {SOURCE_DIR}/joern/
        print(f"CPG 文件保存在: {cpg_path}")
        # 方式2: 导入代码（记录项目路径）
        client.import_code(SOURCE_DIR, "test_project")
        
        # 执行查询并保存结果（会自动保存到项目目录下的 joern 子目录）
        result1 = client.query("cpg.method.name.l", save_result=True, output_file="methods.json")
        print(f"结果: {result1}")
        print(f"结果保存到: {client.get_output_dir()}/methods.json")
        


        # 数据集 2：处理另一个项目（服务器继续运行）
        print("\n=== 处理数据集 2 ===")
        # 可以导入不同的代码目录
        SOURCE_DIR2 = "./svp_simple_001"
        client.import_code(SOURCE_DIR2, "project2")
        
        # 查询：查找 svp_simple_001_001_global_array 在第35行之前的数据流
        print("\n=== 查询 svp_simple_001_001_global_array 在第35行之前的数据流 ===")
        
        # 使用 reachableByFlows 查找数据流路径
        # sink: 第35行使用该变量的地方
        # source: 第35行之前定义/使用该变量的地方
        query_str = """
        val sink = cpg.identifier.name("svp_simple_001_001_global_array")
          .filter(_.lineNumber.headOption.getOrElse(-1) == 35)
        val source = cpg.identifier.name("svp_simple_001_001_global_array")
          .filter(_.lineNumber.headOption.getOrElse(-1) < 35)
        sink.reachableByFlows(source).l
        """
        
        result2 = client.query(query_str, save_result=True, output_file="global_array_dataflow.json")
        print(f"结果保存到: {client.get_output_dir()}/global_array_dataflow.json")
        
        # 打印结果预览
        import json
        try:
            if isinstance(result2, str):
                data = json.loads(result2)
            else:
                data = result2
            print(f"\n找到 {len(data)} 个操作")
            if len(data) > 0:
                print("\n结果预览:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"解析结果时出错: {e}")
            print(f"结果预览: {str(result2)[:500]}...")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 处理完成，关闭服务器
        # 使用 force=True 强制关闭占用8080端口的进程
        # client.close(force=True)
        pass
