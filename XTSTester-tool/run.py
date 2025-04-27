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
from reports.ReportGenerator import set_parallel_mode

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
    parser.add_argument('--group', help='指定仓库组 (openharmony-sig, openharmony-tpc, openharmony_tpc_samples, auto)')
    parser.add_argument('--libs-file', help='包含库列表的文件路径')
    parser.add_argument('--output-dir', help='输出目录')
    parser.add_argument('--sdk-version', help='SDK版本，例如5.0.4')
    parser.add_argument('--release-mode', choices=['y', 'n'], help='是否开启release模式编译')
    parser.add_argument('--parallel', action='store_true', help='是否并行运行三个仓库组')
    parser.add_argument('--specific-libraries', action='append', help='指定要测试的特定库名称，可多次使用此参数指定多个库')
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
    print("5. 搜索并测试特定库")
    
    while True:
        choice = input("请输入选择 (1-5): ").strip()
        if choice == '1':
            args.group = "openharmony-sig"
            args.parallel = False
            args.specific_libraries = None
            break
        elif choice == '2':
            args.group = "openharmony-tpc"
            args.parallel = False
            args.specific_libraries = None
            break
        elif choice == '3':
            args.group = "openharmony_tpc_samples"
            args.parallel = False
            args.specific_libraries = None
            break
        elif choice == '4':
            args.group = None
            args.parallel = True
            args.specific_libraries = None
            break
        elif choice == '5':
            # 搜索特定库
            from core.ReadExcel import fuzzy_match_libraries
            
            search_term = input("请输入要搜索的库名关键词: ").strip()
            matched_libraries = fuzzy_match_libraries(search_term)
            
            if not matched_libraries:
                print(f"未找到包含 '{search_term}' 的库，请重新选择")
                continue
                
            print(f"\n找到 {len(matched_libraries)} 个匹配的库:")
            for i, lib in enumerate(matched_libraries, 1):
                print(f"{i}. {lib['name']}")
                
            # 让用户选择要测试的库
            selected_indices = input("\n请输入要测试的库的序号(多个序号用逗号分隔，输入'all'测试所有匹配的库): ").strip()
            
            if selected_indices.lower() == 'all':
                selected_libraries = matched_libraries
            else:
                try:
                    indices = [int(idx.strip()) for idx in selected_indices.split(',')]
                    selected_libraries = [matched_libraries[idx-1] for idx in indices if 1 <= idx <= len(matched_libraries)]
                    
                    if not selected_libraries:
                        print("未选择有效的库，请重新选择")
                        continue
                except ValueError:
                    print("输入格式错误，请输入有效的数字序号")
                    continue
            
            # 直接使用自动检测模式，不再询问用户
            print("\n将使用自动检测模式确定库的仓库类型")
            args.group = "auto"
            args.parallel = False
            args.specific_libraries = selected_libraries
            break
        else:
            print("无效的选择，请重新输入")

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
        release_mode = input("是否开启release模式编译? 默认是n(y/n): ").strip().lower()
        if release_mode in ['y', 'n', '']:
            args.release_mode = release_mode if release_mode else 'n'
            set_release_mode(args.release_mode == 'y')
            break
        else:
            print("请输入 'y' 或 'n' (默认为n)")
    
    # 设置SDK版本
    set_sdk_version(args.sdk_version)
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
        if hasattr(args, 'sdk_version') and args.sdk_version:
            set_sdk_version(args.sdk_version)
        if hasattr(args, 'release_mode') and args.release_mode:
            set_release_mode(args.release_mode == 'y')
    
    # 如果指定了并行运行，则启动并行处理
    if args.parallel:
        print("\n启动并行测试模式...\n")
        # 设置并行模式（3个仓库组）
        set_parallel_mode(True, 3)
        run_parallel_tests(args)
    else:
        # 单进程模式
        set_parallel_mode(False)
        print(f"\n开始执行 {args.group} 仓库组的测试...\n")

    # Create args namespace with output_dir and repo_type
    args_namespace = argparse.Namespace(
        output_dir=args.output_dir if hasattr(args, 'output_dir') and args.output_dir else os.path.join(PROJECT_DIR, "results"),
        repo_type=args.group if hasattr(args, 'group') else "default",
        specific_libraries=args.specific_libraries if hasattr(args, 'specific_libraries') else None
    )

    # Filter libraries by repo_type before running
    libraries, _, urls = read_libraries_from_excel()

    # 如果指定了特定库，则使用这些库
    if hasattr(args, 'specific_libraries') and args.specific_libraries:
        libraries = args.specific_libraries
    # 否则，按仓库类型过滤
    elif hasattr(args, 'group') and args.group and args.group != "auto":
        libraries = [lib for lib in libraries
                     if filter_library_by_repo_type(lib, args.group)]
        print(f"过滤后库数量: {len(libraries)}")

    # 记录开始时间
    start_time = time.time()
    current_time = time.strftime("%Y/%m/%d %H时%M分%S秒", time.localtime(start_time))
    print(f"测试开始时间: {current_time}")

    # 执行测试
    run_all_libraries(
        repo_type=args_namespace.repo_type,
        args=args_namespace,
        libraries=libraries,
        urls=urls
    )

    # 记录结束时间
    end_time = time.time()
    current_time = time.strftime("%Y/%m/%d %H时%M分%S秒", time.localtime(end_time))
    print(f"测试结束时间: {current_time}")

    # 计算并打印持续时间
    duration = end_time - start_time
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    print(f"总耗时: {hours}小时{minutes}分钟{seconds}秒")

    # 在所有库测试完成后生成最终报告
    generate_final_report()

if __name__ == "__main__":
    main()
