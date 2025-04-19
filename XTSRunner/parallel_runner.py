"""
并行运行模块

该模块负责并行运行三个仓库组的测试，包括:
1. 创建多个进程分别处理不同仓库组
2. 管理进程间的资源竞争
3. 合并测试结果和报告

使用方法:
    from parallel_runner import run_parallel_tests
    run_parallel_tests(args)

参数:
    args: 包含运行参数的对象，通常从命令行或交互式输入获取
"""
import json
import os
import subprocess
import sys
import multiprocessing
from io import TextIOWrapper
from functools import partial
from colorama import Fore
from config import set_sdk_version, set_release_mode, SDK_API_MAPPING, HTML_REPORT_DIR, PROJECT_DIR

# 导入或定义generate_merged_html_report函数
try:
    from ReportGenerator import generate_html_report as generate_merged_html_report
except ImportError:
    def generate_merged_html_report(results, output_path, title="合并测试报告"):
        """
        生成合并的HTML报告
        
        参数:
            results: 合并后的测试结果
            output_path: 输出文件路径
            title: 报告标题
        """
        try:
            # 创建一个简单的HTML报告
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    
    <div class="summary">
        <h2>测试摘要</h2>
        <p>总库数: {results["total_libs"]}</p>
        <p>通过库数: <span class="passed">{results["passed_libs"]}</span></p>
        <p>失败库数: <span class="failed">{results["failed_libs"]}</span></p>
        <p>通过率: {round(results["passed_libs"] / results["total_libs"] * 100, 2) if results["total_libs"] > 0 else 0}%</p>
        
        <p>总测试数: {results["total"]}</p>
        <p>通过测试数: <span class="passed">{results["passed"]}</span></p>
        <p>失败测试数: <span class="failed">{results["failed"]}</span></p>
        <p>测试通过率: {round(results["passed"] / results["total"] * 100, 2) if results["total"] > 0 else 0}%</p>
    </div>
    
    <h2>库测试结果</h2>
    <table>
        <tr>
            <th>仓库组</th>
            <th>库名称</th>
            <th>状态</th>
            <th>通过测试</th>
            <th>失败测试</th>
            <th>总测试数</th>
        </tr>
    """
            
            # 添加每个库的结果
            for lib in results["libraries"]:
                status_class = "passed" if lib["status"] == "passed" else "failed"
                html_content += f"""
        <tr>
            <td>{lib.get("repo_type", "未知")}</td>
            <td>{lib["name"]}</td>
            <td class="{status_class}">{lib["status"]}</td>
            <td>{lib.get("passed", 0)}</td>
            <td>{lib.get("failed", 0)}</td>
            <td>{lib.get("total", 0)}</td>
        </tr>
    """
            
            # 完成HTML
            html_content += """
    </table>
</body>
</html>
"""
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 写入HTML文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            print(f"已生成合并HTML报告: {output_path}")
            
        except Exception as e:
            print(f"生成合并HTML报告时出错: {str(e)}")


def run_parallel_tests(args=None):
    """并行运行三个仓库组的测试"""
    # 获取当前脚本路径
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if args and args.sdk_version:
        sdk_version = args.sdk_version
        set_sdk_version(sdk_version)
    else:
        while True:
            print("\n可用的SDK版本:")
            for i, version in enumerate(SDK_API_MAPPING.keys(), 1):
                print(f"{i}. {version}")
            
            sdk_choice = input("请选择SDK版本 (输入序号): ").strip()
            try:
                sdk_idx = int(sdk_choice) - 1
                if 0 <= sdk_idx < len(SDK_API_MAPPING):
                    sdk_version = list(SDK_API_MAPPING.keys())[sdk_idx]
                    set_sdk_version(sdk_version)
                    break
                else:
                    print("无效的选择，请重新输入")
            except ValueError:
                print("请输入有效的数字")
    
    if args and args.release_mode:
        release_mode = args.release_mode
        set_release_mode(release_mode == 'y')
    else:
        while True:
            release_mode = input("是否开启release模式编译? (y/n): ").strip().lower()
            if release_mode in ['y', 'n']:
                set_release_mode(release_mode == 'y')
                break
            print("请输入 'y' 或 'n'")

    # 询问用户选择并行方式
    print("\n请选择并行运行的方式:")
    print("1. 使用批处理文件启动三个命令行窗口")
    print("2. 使用Python多进程并行执行")
    print("3. 生成命令供用户在PyCharm中手动执行")
    
    choice = input("请输入选择 (1/2/3): ").strip()
    
    # 定义仓库组列表
    groups = ["openharmony-sig", "openharmony-tpc", "openharmony_tpc_samples"]
    
    if choice == "1":
        create_and_run_batch_file(base_dir, groups, sdk_version, release_mode)
    elif choice == "2":
        run_with_multiprocessing(base_dir, groups, sdk_version, release_mode)
    else:
        print_commands_for_manual_execution(base_dir, groups, sdk_version, release_mode)

def create_and_run_batch_file(base_dir, groups, sdk_version, release_mode):
    """创建并运行批处理文件"""
    # 创建批处理文件
    bat_file = os.path.join(base_dir, "run_parallel.bat")
    with open(bat_file, 'w', encoding='utf-8') as f:  # type: TextIOWrapper
        f.write("@echo off\n")
        f.write("echo 启动三个进程分别运行三种仓库类型的库...\n\n")
        
        # 添加三个组的命令
        for group in groups:
            # 使用 base_dir 作为传递给 run.py 的 --output-dir
            log_file = os.path.join(base_dir, "logs", f"{group}.log") # 将日志也放入输出目录
            os.makedirs(os.path.dirname(log_file), exist_ok=True) # 确保日志目录存在

            cmd = f'start "运行 {group}" cmd /c "python "{base_dir}\\run.py" --group {group} --output-dir "{base_dir}" --sdk-version {sdk_version} --release-mode {release_mode} > "{log_file}" 2>&1"'
            f.write(f"{cmd}\n")
        
        f.write("\necho 已启动三个进程，请查看各自的日志文件了解运行情况\n")
        f.write("echo 批处理文件执行完毕\n")
    
    print(f"已创建批处理文件: {bat_file}")
    
    # 运行批处理文件
    run_bat = input("是否立即运行批处理文件? (y/n): ").strip().lower()
    if run_bat == 'y':
        print("正在运行批处理文件...")
        subprocess.Popen(bat_file, shell=True)
        print("批处理文件已启动，请查看各自的日志文件了解运行情况")


def run_group(base_dir, repo_group, sdk_version, release_mode):
    """执行单个仓库组的测试"""
    log_file = os.path.join(base_dir, "logs", f"{repo_group}.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    with open(log_file, 'w', encoding='utf-8') as f:
        cmd = [
            sys.executable,
            os.path.join(base_dir, "run.py"),
            "--group", repo_group,
            "--output-dir", base_dir,
            "--sdk-version", sdk_version,
            "--release-mode", release_mode
        ]

        # 执行命令
        process = subprocess.Popen(
            cmd,
            stdout=f,
            stderr=subprocess.STDOUT
        )

        # 等待进程完成
        process.wait()

def run_with_multiprocessing(base_dir, groups, sdk_version, release_mode):
    """使用Python多进程并行执行"""
    processes = []
    for group in groups:
        p = multiprocessing.Process(
            target=run_group,
            args=(base_dir, group, sdk_version, release_mode)
        )
        processes.append(p)
        p.start()

    print("已启动三个并行进程，请查看各自的日志文件了解运行情况")

    # 等待所有进程完成
    for p in processes:
        p.join()

    print("所有进程已完成")

def print_commands_for_manual_execution(base_dir, groups, sdk_version, release_mode):
    """打印命令供用户在PyCharm中手动执行"""
    print("\n请在PyCharm中打开三个终端窗口，分别运行以下命令:")
    print("="*80)
    
    for group in groups:
        result_dir = os.path.join(base_dir, f"results_{group}")
        cmd = f'python "{base_dir}\\run.py" --group {group} --output-dir "{result_dir}" --sdk-version {sdk_version} --release-mode {release_mode}'
        print(f"组 {group}:")
        print(cmd)
        print("-"*80)

# 添加一个合并报告的函数
def merge_reports(repo_types):
    """合并所有仓库组的报告为一个总体报告"""
    print(f"\n{Fore.CYAN}正在合并所有仓库组的报告...{Fore.RESET}")
    
    # 合并HTML报告
    merged_html_report_path = os.path.join(HTML_REPORT_DIR, "merged_report.html")
    
    # 合并JSON测试结果
    merged_results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "total_libs": 0,
        "passed_libs": 0,
        "failed_libs": 0,
        "libraries": []
    }
    
    for repo_type in repo_types:
        json_path = os.path.join(PROJECT_DIR, f"TestJson/{repo_type}/overall_results.json")
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                try:
                    results = json.load(f)
                    merged_results["total"] += results.get("total", 0)
                    merged_results["passed"] += results.get("passed", 0)
                    merged_results["failed"] += results.get("failed", 0)
                    merged_results["total_libs"] += results.get("total_libs", 0)
                    merged_results["passed_libs"] += results.get("passed_libs", 0)
                    merged_results["failed_libs"] += results.get("failed_libs", 0)
                    
                    # 添加仓库组标识
                    for lib in results.get("libraries", []):
                        lib["repo_type"] = repo_type
                        merged_results["libraries"].append(lib)
                except json.JSONDecodeError:
                    print(f"警告: 无法解析JSON文件 {json_path}")
    
    # 保存合并后的JSON结果
    os.makedirs(os.path.join(PROJECT_DIR, "TestJson/merged"), exist_ok=True)
    with open(os.path.join(PROJECT_DIR, "TestJson/merged/overall_results.json"), 'w', encoding='utf-8') as f:
        json.dump(merged_results, f, ensure_ascii=False, indent=2) # type: ignore

    # 生成合并的HTML报告
    generate_merged_html_report(merged_results, merged_html_report_path)

    print(f"{Fore.GREEN}合并报告已生成: {merged_html_report_path}{Fore.RESET}")
    return merged_results

if __name__ == "__main__":
    run_parallel_tests()
