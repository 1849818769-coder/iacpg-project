#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量清理数据集中生成的 improved_interrupt_analysis 文件/目录
"""

import os
import shutil
import sys
from pathlib import Path


def get_project_paths(base_dir: str, start_num: int = 1, end_num: int = 32) -> list:
    """
    获取项目路径列表
    
    Args:
        base_dir: 基础目录路径
        start_num: 起始项目编号
        end_num: 结束项目编号
        
    Returns:
        项目路径列表
    """
    project_paths = []
    for num in range(start_num, end_num + 1):
        project_name = f"svp_simple_{num:03d}"
        project_path = os.path.join(base_dir, project_name)
        if os.path.exists(project_path):
            project_paths.append((num, project_name, project_path))
    return project_paths


def clean_analysis_results(base_dir: str, start_num: int = 1, end_num: int = 31, 
                          dry_run: bool = False, confirm: bool = True):
    """
    批量清理 improved_interrupt_analysis 目录
    
    Args:
        base_dir: 基础目录路径（testfiles/2.1_remarks）
        start_num: 起始项目编号
        end_num: 结束项目编号
        dry_run: 如果为 True，只显示将要删除的内容，不实际删除
        confirm: 如果为 True，删除前需要用户确认
    """
    # 获取项目路径
    project_paths = get_project_paths(base_dir, start_num, end_num)
    
    if not project_paths:
        print(f"未找到项目编号 {start_num} 到 {end_num} 的项目")
        return
    
    # 收集要删除的目录
    to_delete = []
    total_size = 0
    
    print("=" * 80)
    print("扫描要清理的目录...")
    print("=" * 80)
    
    for num, project_name, project_path in project_paths:
        analysis_dir = os.path.join(project_path, "improved_interrupt_analysis")
        if os.path.exists(analysis_dir):
            # 计算目录大小
            dir_size = sum(
                os.path.getsize(os.path.join(dirpath, filename))
                for dirpath, dirnames, filenames in os.walk(analysis_dir)
                for filename in filenames
            )
            total_size += dir_size
            to_delete.append((num, project_name, analysis_dir, dir_size))
            print(f"  [{num:03d}] {project_name}: {analysis_dir} ({dir_size / 1024 / 1024:.2f} MB)")
        else:
            print(f"  [{num:03d}] {project_name}: 未找到 improved_interrupt_analysis 目录")
    
    if not to_delete:
        print("\n没有找到需要清理的目录")
        return
    
    print("\n" + "=" * 80)
    print(f"总计: {len(to_delete)} 个目录，总大小: {total_size / 1024 / 1024:.2f} MB")
    print("=" * 80)
    
    if dry_run:
        print("\n[DRY RUN] 仅显示，不会实际删除")
        return
    
    # 确认删除
    if confirm:
        print("\n⚠️  警告: 此操作将永久删除上述所有目录！")
        response = input("确认删除? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("操作已取消")
            return
    
    # 执行删除
    print("\n开始清理...")
    print("-" * 80)
    
    success_count = 0
    error_count = 0
    
    for num, project_name, analysis_dir, dir_size in to_delete:
        try:
            shutil.rmtree(analysis_dir)
            print(f"  ✓ [{num:03d}] {project_name}: 已删除 ({dir_size / 1024 / 1024:.2f} MB)")
            success_count += 1
        except Exception as e:
            print(f"  ✗ [{num:03d}] {project_name}: 删除失败 - {e}")
            error_count += 1
    
    print("-" * 80)
    print(f"\n清理完成:")
    print(f"  成功: {success_count}")
    print(f"  失败: {error_count}")
    print("=" * 80)


def main():
    """主函数"""
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.join(script_dir, "../testfiles", "2.1_remarks")
    
    # 解析命令行参数
    start_num = 1
    end_num = 36
    dry_run = False
    no_confirm = False
    
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg == "--dry-run":
                dry_run = True
            elif arg == "--no-confirm" or arg == "-y":
                no_confirm = True
            elif arg.startswith("--start="):
                try:
                    start_num = int(arg.split("=")[1])
                except ValueError:
                    print(f"无效的起始编号: {arg}")
                    sys.exit(1)
            elif arg.startswith("--end="):
                try:
                    end_num = int(arg.split("=")[1])
                except ValueError:
                    print(f"无效的结束编号: {arg}")
                    sys.exit(1)
            elif arg in ["-h", "--help"]:
                print("用法: python clean_analysis_results.py [选项]")
                print("\n选项:")
                print("  --start=N      起始项目编号 (默认: 1)")
                print("  --end=N        结束项目编号 (默认: 32)")
                print("  --dry-run      仅显示将要删除的内容，不实际删除")
                print("  --no-confirm   跳过确认提示 (使用 -y 也可以)")
                print("  -h, --help     显示帮助信息")
                print("\n示例:")
                print("  python clean_analysis_results.py --start=1 --end=10")
                print("  python clean_analysis_results.py --dry-run")
                print("  python clean_analysis_results.py --no-confirm")
                sys.exit(0)
    
    if not os.path.exists(base_dir):
        print(f"错误: 基础目录不存在: {base_dir}")
        sys.exit(1)
    
    clean_analysis_results(
        base_dir=base_dir,
        start_num=start_num,
        end_num=end_num,
        dry_run=dry_run,
        confirm=not no_confirm
    )


if __name__ == "__main__":
    main()

