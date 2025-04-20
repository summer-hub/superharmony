"""
XTSRunner 主程序入口
简化版入口文件，用于启动测试
"""

import argparse
import os
import time
from colorama import init, Fore
from reports.ReportGenerator import generate_final_report
from utils.config import EXCEL_FILE_PATH, PROJECT_DIR
from main import run_all_libraries
from utils.config import SDK_API_MAPPING, set_sdk_version, set_release_mode
from parallel.parallel_runner import run_parallel_tests
from core.ReadExcel import read_libraries_from_excel, filter_library_by_repo_type
from ui.web_ui import start_web_ui

def show_welcome_message():
    """显示欢迎信息和使用说明"""
    init()  # 初始化colorama
    print(f"{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}欢迎使用 XTSRunner - OpenHarmony 三方库测试工具{Fore.RESET}")
    print(f"{Fore.CYAN}{'='*80}{Fore.RESET}")
    print("\n使用说明:")
    print("  1. 命令行模式: 使用参数直接运行特定测试")
    print("     示例: python run.py --group openharmony-sig --sdk-version 5.0.4 --release-mode y")
    print("\n  2. 交互模式: 不带参数运行，通过交互方式配置测试")
    print("     示例: python run.py")
    print("\n  3. 并行模式: 同时测试三个仓库组")
    print("     示例: python run.py --parallel")
    print("\n可用参数:")
    print("  --group        指定仓库组 (openharmony-sig, openharmony-tpc, openharmony_tpc_samples)")
    print("  --libs-file    包含库列表的文件路径")
    print("  --output-dir   输出目录")
    print("  --sdk-version  SDK版本，例如5.0.4")
    print("  --release-mode 是否开启release模式编译 (y/n)")
    print("  --parallel     并行运行三个仓库组")
    print(f"{Fore.CYAN}{'='*80}{Fore.RESET}\n")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='运行三方库测试')
    parser.add_argument('--web-ui', action='store_true', help='启动Web界面')
    parser.add_argument('--group', help='指定仓库组 (openharmony-sig, openharmony-tpc, openharmony_tpc_samples)')
    parser.add_argument('--libs-file', help='包含库列表的文件路径')
    parser.add_argument('--output-dir', help='输出目录')
    parser.add_argument('--sdk-version', help='SDK版本，例如5.0.4')
    parser.add_argument('--release-mode', choices=['y', 'n'], help='是否开启release模式编译')
    parser.add_argument('--parallel', action='store_true', help='是否并行运行三个仓库组')
    return parser.parse_args()


def interactive_mode():
    """交互式模式，提示用户输入参数"""

    
    args = type('Args', (), {})()
    
    # 显示仓库组选项
    print("请选择要测试的仓库组:")
    print("1. openharmony-sig")
    print("2. openharmony-tpc")
    print("3. openharmony_tpc_samples")
    print("4. 并行运行所有仓库组")
    
    while True:
        choice = input("请输入选择 (1-4): ").strip()
        if choice == '1':
            args.group = "openharmony-sig"
            args.parallel = False
            break
        elif choice == '2':
            args.group = "openharmony-tpc"
            args.parallel = False
            break
        elif choice == '3':
            args.group = "openharmony_tpc_samples"
            args.parallel = False
            break
        elif choice == '4':
            args.group = None
            args.parallel = True
            break
        else:
            print("无效的选择，请重新输入")
    
    # 如果不是并行模式，询问是否使用库列表文件
    if not args.parallel:
        print(f"默认将使用配置文件中的Excel表格: {os.path.basename(EXCEL_FILE_PATH)}")
        use_libs_file = input("是否使用自定义库列表文件? (y/n，默认n): ").strip().lower() or 'n'
        if use_libs_file == 'y':
            while True:
                libs_file = input("请输入库列表文件路径: ").strip()
                if os.path.exists(libs_file):
                    args.libs_file = libs_file
                    break
                else:
                    print(f"文件 {libs_file} 不存在，请重新输入")
        else:
            args.libs_file = None
            print(f"将使用默认Excel文件: {EXCEL_FILE_PATH}")
    else:
        args.libs_file = None
    
    # 询问输出目录
    default_output_dir = os.path.join(PROJECT_DIR, "results")
    print(f"默认输出目录: {default_output_dir}")
    use_custom_output = input("是否使用自定义输出目录? (y/n，默认n): ").strip().lower() or 'n'
    if use_custom_output == 'y':
        output_dir = input("请输入输出目录路径: ").strip()
        args.output_dir = output_dir
    else:
        args.output_dir = default_output_dir
        print(f"将使用默认输出目录: {default_output_dir}")
    
    # 询问SDK版本
    print("\n可用的SDK版本:")
    for i, version in enumerate(SDK_API_MAPPING.keys(), 1):
        print(f"{i}. {version}")
    
    while True:
        sdk_choice = input("请选择SDK版本 (输入序号): ").strip()
        try:
            sdk_idx = int(sdk_choice) - 1
            if 0 <= sdk_idx < len(SDK_API_MAPPING):
                args.sdk_version = list(SDK_API_MAPPING.keys())[sdk_idx]
                break
            else:
                print("无效的选择，请重新输入")
        except ValueError:
            print("请输入有效的数字")
    
    # 询问release模式
    while True:
        release_mode = input("是否开启release模式编译? (y/n): ").strip().lower()
        if release_mode in ['y', 'n']:
            args.release_mode = release_mode
            set_release_mode(release_mode == 'y')
            break
        else:
            print("请输入 'y' 或 'n'")
    
    # 设置SDK版本
    set_sdk_version(args.sdk_version)
    
    # 询问是否启动Web UI
    use_web_ui = input("是否启动Web界面? (y/n，默认n): ").strip().lower() or 'n'
    if use_web_ui == 'y':
        args.web_ui = True
    else:
        args.web_ui = False
    
    return args


def main():
    """主函数"""
    # 显示欢迎信息
    show_welcome_message()
    
    # 解析命令行参数
    args = parse_arguments()
    
    # 检查是否有命令行参数，如果没有则进入交互模式
    if not any(vars(args).values()):
        print("未检测到命令行参数，进入交互模式...\n")
        args = interactive_mode()
    else:
        # 设置SDK版本和release模式
        if hasattr(args, 'sdk_version'):
            set_sdk_version(args.sdk_version)
        if hasattr(args, 'release_mode'):
            set_release_mode(args.release_mode == 'y')
    
    # 如果指定了并行运行，则启动并行处理
    if args.parallel:
        print("\n启动并行测试模式...\n")

        run_parallel_tests(args)
    else:
        # 导入main模块中的函数并执行单一进程
        print(f"\n开始执行 {args.group} 仓库组的测试...\n")

    # Create args namespace with output_dir and repo_type
    args_namespace = argparse.Namespace(
        output_dir=args.output_dir if hasattr(args, 'output_dir') else os.getcwd(),
        repo_type=args.group if hasattr(args, 'group') else "default"
    )
    
    # Filter libraries by repo_type before running
    libraries, _, urls = read_libraries_from_excel()
    
    if hasattr(args, 'group') and args.group:
        libraries = [lib for lib in libraries 
                    if filter_library_by_repo_type(lib, args.group)]
        print(f"过滤后库数量: {len(libraries)}")
    # Pass the filtered libraries to run_all_libraries
    start_time = time.time()
    current_time = time.strftime("%Y/%m/%d %H时%M分%S秒", time.localtime(start_time))
    print(f"测试开始时间: {current_time}")

    # 如果指定了启动Web UI，则启动Web界面
    if args.web_ui:
        start_web_ui()
    else:
        # 原有测试逻辑
        run_all_libraries(
            repo_type=args_namespace.repo_type, 
            args=args_namespace,
            libraries=libraries,
            urls=urls
        )
    end_time = time.time()
    current_time = time.strftime("%Y/%m/%d %H时%M分%S秒", time.localtime(end_time))
    print(f"测试结束时间: {current_time}")

    # Calculate and print duration
    duration = end_time - start_time
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    print(f"总耗时: {hours}小时{minutes}分钟{seconds}秒")
    # 在所有库测试完成后生成最终报告
    generate_final_report()


if __name__ == "__main__":
    main()
