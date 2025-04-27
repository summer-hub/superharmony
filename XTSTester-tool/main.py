import os
import subprocess
import time
import argparse
import signal
import sys
from colorama import init, Fore

from core.BuildAndRun import clone_and_build
from reports.GenerateHtmlReport import generate_html_report
from core.ReadExcel import read_libraries_from_excel, get_repo_info
from reports.ReportGenerator import generate_final_report
from utils.config import check_dependencies, PROJECT_DIR

# 全局变量，用于控制测试中断
interrupted = False
current_process = None  # 添加全局变量存储当前子进程

# 信号处理函数
def signal_handler(sig, frame):
    global interrupted, current_process
    print(f"\n{Fore.YELLOW}收到中断信号，正在安全停止测试...{Fore.RESET}")
    interrupted = True
    
    # 强制终止当前正在运行的子进程（如果有）
    if current_process is not None and hasattr(current_process, 'pid'):
        try:
            print(f"{Fore.YELLOW}正在终止当前运行的子进程...{Fore.RESET}")
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(current_process.pid)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            print(f"{Fore.RED}终止子进程时出错: {str(e)}{Fore.RESET}")
    else:
        print(f"{Fore.YELLOW}当前子进程以非常规方式终止{Fore.RESET}")

    # 如果是SIGINT（Ctrl+C），则直接退出程序
    if sig == signal.SIGINT:
        print(f"{Fore.YELLOW}用户按下Ctrl+C，正在退出程序...{Fore.RESET}")
        sys.exit(1)

# 注册信号处理函数
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def run_all_libraries(repo_type, args, libraries=None, urls=None):
    global current_process, interrupted
    init()  # 初始化颜色输出
    """按顺序执行Excel中的所有库"""
    # 检查依赖
    check_dependencies()
    
    # 重置中断标志
    interrupted = False
    
    # 如果没有传入libraries和urls，则从Excel读取
    if libraries is None or urls is None:
        libraries, _, urls = read_libraries_from_excel()
    
    # 如果指定了特定库，则只测试这些库
    if hasattr(args, 'specific_libraries') and args.specific_libraries:
        specific_libraries = args.specific_libraries
        # 确保所有指定的库都在Excel中
        filtered_libraries = []
        for lib in specific_libraries:
            if lib in libraries:
                filtered_libraries.append(lib)
            else:
                print(f"警告：指定的库 {lib} 不在Excel中，将被跳过")
        libraries = filtered_libraries
        print(f"将测试 {len(libraries)} 个指定的库")

    # 如果repo_type是auto，则根据URL自动检测每个库的仓库类型
    if repo_type == "auto":
        print("使用自动检测模式确定库的仓库类型")
        filtered_libraries = []
        for lib in libraries:
            owner, name, _ = get_repo_info(lib)
            # 提取库名用于打印
            display_name = lib['name'] if isinstance(lib, dict) and 'name' in lib else lib
            if owner == "openharmony-sig":
                print(f"库 {display_name} 属于 openharmony-sig 仓库组")
                filtered_libraries.append(lib)
            elif owner == "openharmony-tpc" and name != "openharmony_tpc_samples":
                print(f"库 {display_name} 属于 openharmony-tpc 仓库组")
                filtered_libraries.append(lib)
            elif name == "openharmony_tpc_samples":
                print(f"库 {display_name} 属于 openharmony_tpc_samples 仓库组")
                filtered_libraries.append(lib)
            else:
                print(f"警告：无法确定库 {display_name} 的仓库类型，将被跳过")
        libraries = filtered_libraries
    
    # 记录总体测试结果
    overall_results = {
        "total": 0,           # 总测试用例数
        "passed": 0,          # 通过的测试用例数
        "failed": 0,          # 失败的测试用例数
        "error": 0,           # 错误的测试用例数
        "total_libs": len(libraries),  # 总库数
        "passed_libs": 0,     # 通过的库数
        "failed_libs": 0,     # 失败的库数
        "error_libs": 0,     # 错误的库数
        "libraries": []       # 库级别的详细结果
    }

    # 添加错误列表库
    failed_libraries = []
    
    # 按顺序执行每个库
    for idx, library_name in enumerate(libraries, 1):
        # 检查是否被中断
        if interrupted:
            print(f"\n{Fore.YELLOW}测试被用户中断，停止执行剩余库{Fore.RESET}")
            # 添加中断信息到结果中
            overall_results["interrupted"] = True
            overall_results["interrupted_at"] = library_name
            break
            
        test_results = None
        try:
            # 提取库名用于打印
            display_name = library_name['name'] if isinstance(library_name, dict) and 'name' in library_name else library_name
            print(f"\n{'='*50}")
            print(f"开始执行第 {idx}/{len(libraries)} 个库: {display_name}")
            print(f"{'='*50}")
            
            # 解析URL获取owner、name和sub_dir
            owner, name, sub_dir = get_repo_info(library_name) # 使用原始 library_name 获取信息
            print(f"解析得到仓库信息: owner={owner}, name={name}, sub_dir={sub_dir}")

            # 调用clone and build函数并获取测试结果
            print(f"开始克隆和构建库: {display_name}")
            try:
                # 修改为使用全局变量跟踪子进程
                global current_process
                current_process = None  # 重置当前进程
                test_results = clone_and_build(library_name)
                current_process = None  # 子进程完成后重置
            except Exception as e:
                current_process = None  # 确保在异常情况下也重置
                print(f"克隆和构建时出错: {str(e)}")
                raise
            
            # 确保test_results是字典类型
            if isinstance(test_results, dict):
                # 检查test_results是否包含test_results、summary和class_times键
                # 这表明它可能是extract_test_details返回的完整字典
                if "test_results" in test_results and "summary" in test_results:
                    # 提取实际的测试结果s
                    summary = test_results.get("summary", {})
                    
                    # 使用summary中的统计数据
                    lib_total = summary.get("total", 0)
                    lib_passed = summary.get("passed", 0)
                    lib_failed = summary.get("failed", 0)
                    lib_error = summary.get("error", 0)
                else:
                    # 原始计算方式
                    lib_total = sum(len(tests) for key, tests in test_results.items() 
                                if key != '_statistics' and isinstance(tests, list))
                    lib_passed = sum(1 for key, tests in test_results.items() 
                                    if key != '_statistics' and isinstance(tests, list)
                                    for test in tests if test.get('status') == 'passed')
                    lib_failed = sum(1 for key, tests in test_results.items() 
                                    if key != '_statistics' and isinstance(tests, list)
                                    for test in tests if test.get('status') == 'failed')
                    lib_error = lib_total - lib_passed - lib_failed
                
                # 更新总体结果
                overall_results["total"] += lib_total
                overall_results["passed"] += lib_passed
                overall_results["failed"] += lib_failed
                overall_results["error"] += lib_error
                
                # 判断库的状态
                if lib_error > 0:
                    lib_status = "error"
                    overall_results["error_libs"] += 1
                elif lib_failed > 0:
                    lib_status = "failed"
                    overall_results["failed_libs"] += 1
                elif lib_passed == lib_total and lib_total > 0:
                    lib_status = "passed"
                    overall_results["passed_libs"] += 1
                else:
                    # 如果没有明确的错误或失败，但通过数小于总数，视为错误
                    lib_status = "error"
                    overall_results["error_libs"] += 1
                
                # 保存原始库名，用于最终报告显示
                overall_results["libraries"].append({
                    "name": name,
                    "original_name": library_name,  # 保存Excel中的原始库名
                    "total": lib_total,
                    "passed": lib_passed,
                    "failed": lib_failed,
                    "error": lib_error,
                    "status": lib_status,  # 使用新的状态判断结果
                    "test_results": test_results  # 保存详细的测试结果
                })
                
            else:
                e = None
                # 添加一个默认的记录
                overall_results["libraries"].append({
                    "name": name,
                    "original_name": library_name,  # 保存Excel中的原始库名
                    "total": 1,
                    "passed": 0,
                    "failed": 0,
                    "error": 1,  # 标记为错误
                    "status": "error",  # 出错的库标记为错误
                    "error_message": str(e)  # 记录错误信息
                })
                overall_results["total"] += 1
                overall_results["error"] += 1
                overall_results["error_libs"] += 1

                # 将库添加到失败列表中
                failed_libraries.append(library_name)

                print(f"警告：库 {name} 未返回有效的测试结果")
                
        except (subprocess.CalledProcessError, OSError, IOError) as e:
            print(f"执行库 {library_name} 时出错: {str(e)}")
            print(f"详细错误信息:")
            print(f"- 当前工作目录: {os.getcwd()}")
            print(f"- 尝试访问的路径: {os.path.abspath(library_name)}")
            if hasattr(e, 'cmd'):
                print(f"- 执行的命令: {e.cmd}")
            if hasattr(e, 'output'):
                print(f"- 命令输出: {e.output.decode('utf-8') if isinstance(e.output, bytes) else e.output}")
            
            # 添加错误的库到结果中
            try:
                # 首先检查test_results的类型
                if isinstance(test_results, int):
                    print(f"警告：库 {library_name} 返回了无效的测试结果类型(int)")
                
                # 使用get_repo_info获取仓库信息
                owner, name, _ = get_repo_info(library_name)
                
                # 更新总体结果
                overall_results["libraries"].append({
                    "name": name,
                    "original_name": library_name,  # 保存Excel中的原始库名
                    "total": 1,
                    "passed": 0,
                    "failed": 0,
                    "error": 1,  # 标记为错误
                    "status": "error",  # 出错的库标记为错误
                    "error_message": str(e)  # 记录错误信息
                })
                overall_results["total"] += 1
                overall_results["error"] += 1
                overall_results["error_libs"] += 1
                
                # 将库添加到失败列表中  
                failed_libraries.append(library_name)
                
            except Exception as inner_e:
                print(f"处理错误结果时发生异常: {str(inner_e)}")
            
            continue
    
    # 测试完成后，记录失败的库
    if failed_libraries:
        print(f"{Fore.RED}以下库测试失败:{Fore.RESET}")
        for lib in failed_libraries:
            print(f"- {lib}")

        # 将失败的库写入文件
        with open(os.path.join(args.output_dir, f"{repo_type}_failed_libraries.txt"), 'w') as f:
            for lib in failed_libraries:
                f.write(f"{lib}\n")

    # 生成HTML报告
    print("\n生成HTML测试报告...")
    # 检查是否被中断，如果被中断则跳过生成HTML报告
    if interrupted:
        print(f"{Fore.YELLOW}测试被中断，跳过生成HTML报告以避免覆盖现有报告{Fore.RESET}")
        html_report_path = None
    else:
        html_report_path = generate_html_report(overall_results)
        if html_report_path:
            print(f"HTML报告已生成: {html_report_path}")
        else:
            print(f"{Fore.YELLOW}警告: HTML总报告生成可能不完整，将使用默认路径{Fore.RESET}")
            html_report_path = os.path.join(PROJECT_DIR, "results", "html-report", "index.html")

    # 总结报告生成情况
    print("\n报告生成情况汇总:")
    print(f"- HTML报告: {Fore.GREEN}[PASS] 已生成{Fore.RESET}")
    
    # 提供报告路径信息
    print("\n报告路径:")
    print(f"- HTML报告: {html_report_path}")

    # 确保至少生成HTML报告作为备选
    try:
        # 检查是否是由于中断导致的异常，如果是则不生成HTML报告
        if not interrupted and not html_report_path:
            print("尝试生成基本HTML报告作为备选...")
            generate_html_report(overall_results)
        elif interrupted:
            print(f"{Fore.YELLOW}测试被中断，跳过生成HTML报告以避免覆盖现有报告{Fore.RESET}")
    except Exception as html_e:
        print(f"生成基本HTML报告也失败: {str(html_e)}")

    # 修改终端显示部分，使用更可靠的方式显示状态
    print(f"\n{'='*50}")
    print(Fore.CYAN + "总体测试结果摘要:" + Fore.RESET)
    print(f"{'='*50}")
    
    # 重新计算库级别统计
    passed_libs = sum(1 for lib in overall_results["libraries"] if lib["status"] == "passed")
    failed_libs = sum(1 for lib in overall_results["libraries"] if lib["status"] == "failed")
    error_libs = sum(1 for lib in overall_results["libraries"] if lib["status"] == "error")
    total_libs = len(overall_results["libraries"])
    
    # 更新overall_results中的统计数据
    overall_results["passed_libs"] = passed_libs
    overall_results["failed_libs"] = failed_libs
    overall_results["error_libs"] = error_libs if "error_libs" in overall_results else error_libs
    
    # 重新计算测试用例统计
    total_tests = sum(lib["total"] for lib in overall_results["libraries"])
    passed_tests = sum(lib["passed"] for lib in overall_results["libraries"])
    failed_tests = sum(lib.get("failed", 0) for lib in overall_results["libraries"])
    error_tests = sum(lib.get("error", 0) for lib in overall_results["libraries"])
    
    # 更新overall_results中的测试用例统计
    overall_results["total"] = total_tests
    overall_results["passed"] = passed_tests
    overall_results["failed"] = failed_tests
    overall_results["error"] = error_tests if "error" in overall_results else error_tests
    
    # 显示正确的统计信息
    print(f"库级别统计: {passed_libs}/{total_libs} 个库通过, {failed_libs} 个失败, {error_libs} 个错误")
    print(f"测试用例统计: {passed_tests}/{total_tests} 个测试用例通过, {failed_tests} 个失败, {error_tests} 个错误")
    print(f"{'='*50}")
    
    for lib in overall_results["libraries"]:
        # 确保状态正确
        if lib.get("error", 0) > 0:
            lib["status"] = "error"
        elif lib.get("failed", 0) > 0 or lib["passed"] < lib["total"]:
            lib["status"] = "failed"
        elif lib["passed"] == lib["total"] and lib["total"] > 0:
            lib["status"] = "passed"
        
        # 使用[PASS]/[FAIL]/[ERROR]替代Unicode字符，避免编码问题
        if lib["status"] == "passed":
            status_icon = Fore.GREEN + "[PASS]"
        elif lib["status"] == "error":
            status_icon = Fore.RED + "[ERROR]"  # 错误状态使用[ERROR]标记
        else:
            status_icon = Fore.RED + "[FAIL]"
            
        # 提取库名用于打印
        display_name = lib['original_name']['name'] if isinstance(lib['original_name'], dict) and 'name' in lib['original_name'] else lib['original_name']
        # 显示正确的测试结果
        error_count = lib.get("error", 0)
        failed_count = lib.get("failed", 0)
        print(f"{status_icon} {display_name}{Fore.RESET}: {lib['passed']}/{lib['total']} 测试通过, {failed_count} 失败, {error_count} 错误")
    
    print(f"{'='*50}")

if __name__ == "__main__":
    start_time = time.time()
    current_time = time.strftime("%Y/%m/%d %H时%M分%S秒", time.localtime(start_time))
    print(f"测试开始时间: {current_time}")
    
    # 获取用户输入的SDK版本
    from utils.config import SDK_API_MAPPING, set_sdk_version
    while True:
        sdk_version = input("请输入SDK版本 (例如: 5.0.4): ").strip()
        if sdk_version in SDK_API_MAPPING:
            # 使用新的函数设置版本
            set_sdk_version(sdk_version)
            break
        print(f"无效的SDK版本。支持的版本: {', '.join(SDK_API_MAPPING.keys())}")
    
    # 询问用户是否开启release模式
    while True:
        release_mode = input("是否开启release模式编译? (y/n): ").strip().lower()
        if release_mode in ['y', 'n']:
            # 设置全局变量
            from utils.config import set_release_mode
            set_release_mode(release_mode == 'y')
            break
        print("请输入 'y' 或 'n'")
    
    # Run the main function with required arguments
    run_all_libraries(repo_type="default", args=argparse.Namespace(output_dir=os.getcwd()))
    
    # Get end time and print
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