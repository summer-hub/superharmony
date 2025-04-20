import os
import subprocess
import json
import time
import traceback
import uuid
import argparse
import signal
import sys
from colorama import init, Fore

from BuildAndRun import clone_and_build
from GenerateAllureReport import generate_allure_report
from GenerateHtmlReport import generate_html_report
from ReadExcel import read_libraries_from_excel, parse_git_url
from ReportGenerator import generate_final_report
from config import check_dependencies, PROJECT_DIR, ALLURE_RESULTS_DIR, npm_path, ALLURE_REPORT_DIR, \
    STATIC_REPORT_DIR, REPORT_ZIP

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
            if os.name == 'nt':  # Windows
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(current_process.pid)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:  # Unix/Linux
                os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
            print(f"{Fore.GREEN}子进程已终止{Fore.RESET}")
        except Exception as e:
            print(f"{Fore.RED}终止子进程时出错: {str(e)}{Fore.RESET}")
    else:
        print(f"{Fore.YELLOW}当前没有运行的子进程需要终止{Fore.RESET}")

    # 如果是SIGINT（Ctrl+C），则直接退出程序
    if sig == signal.SIGINT:
        print(f"{Fore.YELLOW}用户按下Ctrl+C，正在退出程序...{Fore.RESET}")
        sys.exit(1)

# 注册信号处理函数
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def run_all_libraries(repo_type, args, libraries=None, urls=None):
    global name, interrupted
    init()  # 初始化颜色输出
    """按顺序执行Excel中的所有库"""
    # 检查依赖
    check_dependencies()
    
    # 重置中断标志
    interrupted = False
    
    # 如果没有传入libraries和urls，则从Excel读取
    if libraries is None or urls is None:
        libraries, _, urls = read_libraries_from_excel()
    
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
            print(f"\n{'='*50}")
            print(f"开始执行第 {idx}/{len(libraries)} 个库: {library_name}")
            print(f"{'='*50}")
            
            # 获取库的URL
            url = urls.get(library_name)
            if not url:
                print(f"错误：找不到库 {library_name} 的URL信息")
                continue
                
            # 解析URL获取owner、name和sub_dir
            owner, name, sub_dir = parse_git_url(url)
            
            if not owner or not name:
                print(f"错误：无法从URL解析出有效的仓库信息: {url}")
                continue
            print(f"解析URL得到仓库信息: owner={owner}, name={name}, sub_dir={sub_dir}")

            # 调用clone and build函数并获取测试结果
            print(f"开始克隆和构建库: {library_name}")
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
                    # 提取实际的测试结果
                    actual_test_results = test_results["test_results"]
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
                
                # 生成该库的Allure报告
                generate_allure_report(test_results, name)
            else:
                e = None
                # 如果test_results不是字典，创建一个默认的测试结果
                default_test_results = {
                    "ErrorTestClass": [{
                        "name": "errorTest",
                        "status": "error",  # 出错的库标记为错误
                        "time": "1ms",
                        "error_message": str(e) if e else "未知错误"  # 保存错误信息
                    }]
                }

                # 生成默认的Allure报告
                generate_allure_report(default_test_results, name)

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

                print(f"警告：库 {name} 未返回有效的测试结果，已创建默认测试结果")
                
        except (subprocess.CalledProcessError, OSError, IOError) as e:
            print(f"执行库 {library_name} 时出错: {str(e)}")
            print(f"详细错误信息:")
            print(f"- 当前工作目录: {os.getcwd()}")
            print(f"- 尝试访问的路径: {os.path.abspath(name)}")
            if hasattr(e, 'cmd'):
                print(f"- 执行的命令: {e.cmd}")
            if hasattr(e, 'output'):
                print(f"- 命令输出: {e.output.decode('utf-8') if isinstance(e.output, bytes) else e.output}")
            
            # 添加错误的库到结果中，并创建默认测试结果
            try:
                # 首先检查test_results的类型
                if isinstance(test_results, int):
                    print(f"警告：库 {library_name} 返回了无效的测试结果类型(int)")
                
                # 获取库的URL和解析信息（如果可能）
                url = urls.get(library_name, "")
                owner, name, _ = parse_git_url(url) if url else (None, None, None)
                
                # 如果无法获取name，使用library_name
                if not name:
                    name = library_name
                
                # 创建默认的测试结果
                default_test_results = {
                    "ErrorTestClass": [{
                        "name": "errorTest",
                        "status": "error",  # 出错的库标记为错误
                        "time": "1ms",
                        "error_message": str(e)  # 保存错误信息
                    }]
                }
                
                # 生成默认的Allure报告
                generate_allure_report(default_test_results, name)
                
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

    # 生成总体Allure报告
    try:
        print("\n生成Allure总体报告...")

        # 在生成Allure报告之前，创建一个总体结果的JSON文件
        # 这将在报告中显示为一个顶级测试套件
        overall_uuid = str(uuid.uuid4())
        overall_status = "passed" if overall_results["failed"] == 0 else "failed"
        
        # 创建总体测试套件JSON
        overall_suite = {
            "uuid": overall_uuid,
            "historyId": "overall_test_results",
            "name": f"总体测试结果: {overall_results['passed']}/{overall_results['total']} 测试通过",
            "fullName": "总体测试结果",
            "status": overall_status,
            "stage": "finished",
            "start": int(time.time() * 1000),
            "stop": int(time.time() * 1000) + 1000,
            "labels": [
                {"name": "suite", "value": "总体测试结果"},
                {"name": "package", "value": "总体测试结果"}
            ],
            "statusDetails": {
                "message": f"库级别: {overall_results['passed_libs']}/{overall_results['total_libs']} 个库通过\n"
                        f"测试用例: {overall_results['passed']}/{overall_results['total']} 个测试通过, {overall_results['failed']} 个失败"
            },
            # 增强描述部分，使用HTML格式提供更详细的统计信息
            "description": f"""
<h3>总体测试结果</h3>
<p><b>库级别统计:</b> {overall_results['passed_libs']}/{overall_results['total_libs']} 个库通过, {overall_results.get('failed_libs', 0)} 个失败, {overall_results.get('error_libs', 0)} 个错误</p>
<p><b>测试用例统计:</b> {overall_results['passed']}/{overall_results['total']} 个测试通过, {overall_results['failed']} 个失败, {overall_results.get('error', 0)} 个错误</p>
<hr/>
<h4>各库测试结果汇总:</h4>
<table border="1" style="border-collapse: collapse; width: 100%;">
<tr style="background-color: #f2f2f2;">
  <th style="padding: 8px; text-align: left;">库名</th>
  <th style="padding: 8px; text-align: center;">状态</th>
  <th style="padding: 8px; text-align: center;">测试通过数</th>
  <th style="padding: 8px; text-align: center;">测试总数</th>
  <th style="padding: 8px; text-align: center;">通过率</th>
</tr>
{"".join([f'''
<tr>
  <td style="padding: 8px;">{lib["name"]}</td>
  <td style="padding: 8px; text-align: center; color: {'green' if lib["status"] == 'passed' else 'red'};">
    {'[PASS]' if lib["status"] == 'passed' else '[ERROR]' if lib["status"] == 'error' else '[FAIL]'}
  </td>
  <td style="padding: 8px; text-align: center;">{lib["passed"]}</td>
  <td style="padding: 8px; text-align: center;">{lib["total"]}</td>
  <td style="padding: 8px; text-align: center;">
    {(lib["passed"]/lib["total"]*100) if lib["total"] > 0 else 0:.2f}%
  </td>
</tr>''' for lib in overall_results["libraries"]])}
</table>
<p style="margin-top: 15px;"><b>总计:</b> {overall_results['passed']}/{overall_results['total']} 测试通过, {overall_results['failed']} 失败, {overall_results.get('error', 0)} 错误</p>
"""
        }
        
        # 写入总体测试套件结果文件
        overall_file = os.path.join(ALLURE_RESULTS_DIR, "overall_test_results.json")
        with open(overall_file, 'w', encoding='utf-8') as f:
            json.dump(overall_suite, f, ensure_ascii=False, indent=2) # type: ignore
        
        # 为每个库创建一个与总体测试套件关联的测试结果
        for lib in overall_results["libraries"]:
            lib_name = lib["name"]
            lib_status = lib["status"]
            lib_passed = lib["passed"]
            lib_total = lib["total"]
            lib_failed = lib["failed"]
            
            lib_result = {
                "uuid": str(uuid.uuid4()),
                "historyId": f"overall_{lib_name}",
                "name": f"{lib_name}: {lib_passed}/{lib_total} 测试通过",
                "fullName": f"总体测试结果.{lib_name}",
                "status": "passed" if lib_status == "passed" else "failed",
                "stage": "finished",
                "start": int(time.time() * 1000),
                "stop": int(time.time() * 1000) + 500,
                "labels": [
                    {"name": "suite", "value": lib_name},
                    {"name": "package", "value": "总体测试结果"},
                    {"name": "parentSuite", "value": "总体测试结果"}
                ],
                "statusDetails": {
                    "message": f"总计: {lib_passed}/{lib_total} 测试通过, {lib_failed} 失败"
                }
            }
            
            # 写入库级别的测试结果文件
            lib_file = os.path.join(ALLURE_RESULTS_DIR, f"overall_{lib_name}_result.json")
            with open(lib_file, 'w', encoding='utf-8') as f:
                json.dump(lib_result, f, ensure_ascii=False, indent=2) # type: ignore
        
        # 生成HTML报告（无论Allure是否可用，都生成HTML报告）
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

        # 尝试生成Allure报告
        print("\n尝试生成Allure测试报告...")
        
        allure_available = False
        allure_report_generated = False
        
        # 检查allure命令是否可用
        try:
            # 尝试直接使用allure命令
            result = subprocess.run(["allure", "--version"], 
                                   check=False, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   shell=True)
            if result.returncode == 0:
                allure_available = True
                print("找到allure命令行工具")
        except Exception:
            print("直接使用allure命令失败")
        
        # 如果直接使用allure命令失败，尝试使用npm安装
        if not allure_available:
            try:
                print("尝试使用npm安装allure-commandline...")
                subprocess.run([npm_path, "install", "-g", "allure-commandline"], 
                              check=False, 
                              stdout=subprocess.PIPE)
                
                # 再次检查allure命令是否可用
                result = subprocess.run(["allure", "--version"], 
                                      check=False, 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE,
                                      shell=True)
                if result.returncode == 0:
                    allure_available = True
                    print("成功安装allure-commandline")
            except Exception as e:
                print(f"使用npm安装allure失败: {str(e)}")
        
        # 尝试生成Allure报告
        if allure_available:
            try:
                # 生成交互式Allure报告
                subprocess.run(["allure", "generate", ALLURE_RESULTS_DIR, 
                               "-o", ALLURE_REPORT_DIR, "--clean"],
                              check=True,
                              shell=True)
                print(f"Allure交互式报告已生成: {ALLURE_REPORT_DIR}")
                allure_report_generated = True
                
                # 尝试打开报告（非阻塞方式）
                try:
                    subprocess.Popen(["allure", "open", ALLURE_REPORT_DIR], shell=True)
                    print("已自动打开Allure报告")
                except Exception as e:
                    print(f"自动打开Allure报告失败: {str(e)}")
                    print(f"请手动打开报告: {ALLURE_REPORT_DIR}")
            except Exception as e:
                print(f"生成Allure交互式报告时出错: {str(e)}")
        else:
            print("无法找到或安装allure命令行工具，跳过生成Allure交互式报告")
        
        # 生成静态HTML版本的Allure报告（无论交互式报告是否成功）
        print("\n生成静态版Allure报告...")
        
        if not os.path.exists(STATIC_REPORT_DIR):
            os.makedirs(STATIC_REPORT_DIR)
        
        static_report_generated = False
        if allure_available:
            try:
                # 使用allure generate命令生成静态报告
                generate_cmd = f'allure generate {ALLURE_RESULTS_DIR} -o {STATIC_REPORT_DIR} --clean'
                subprocess.run(generate_cmd, shell=True, check=True)
                static_report_generated = True
                print(f"静态版Allure报告已生成: {STATIC_REPORT_DIR}")
                
                # 将报告打包成zip文件，方便分享
                import shutil
                
                shutil.make_archive(os.path.splitext(REPORT_ZIP)[0], 'zip', STATIC_REPORT_DIR)
                print(f"静态报告压缩包已生成: {REPORT_ZIP}")
                print("你可以将生成的压缩包发送给其他人，解压后打开 index.html 即可查看完整报告")
            except Exception as e:
                print(f"生成静态版Allure报告时出错: {str(e)}")
        else:
            print("由于无法找到allure命令行工具，跳过生成静态版Allure报告")
        
        # 总结报告生成情况
        print("\n报告生成情况汇总:")
        # 修改判断逻辑：只要html_report_path不为None，就认为HTML报告已成功生成
        print(f"- HTML报告: {Fore.GREEN}[PASS] 已生成{Fore.RESET}")
        print(f"- Allure交互式报告: {Fore.GREEN + '[PASS] 已生成' if allure_report_generated else Fore.RED + '[FAIL] 生成失败'}{Fore.RESET}")
        print(f"- Allure静态报告: {Fore.GREEN + '[PASS] 已生成' if static_report_generated else Fore.RED + '[FAIL] 生成失败'}{Fore.RESET}")
        
        # 提供报告路径信息
        print("\n报告路径:")
        # 总是显示HTML报告路径，因为即使有单个库报告生成失败，总报告仍然是有效的
        print(f"- HTML报告: {html_report_path}")
        if allure_report_generated:
            print(f"- Allure交互式报告: {ALLURE_REPORT_DIR}")
        if static_report_generated:
            print(f"- Allure静态报告: {STATIC_REPORT_DIR}")
            print(f"- 静态报告压缩包: {os.path.join(PROJECT_DIR, 'allure-report-static.zip')}")
            
    except Exception as e:
        print(f"生成测试报告时出错: {str(e)}")
        traceback.print_exc()
        # 确保至少生成HTML报告作为备选
        try:
            # 检查是否是由于中断导致的异常，如果是则不生成HTML报告
            if not interrupted:
                print("尝试生成基本HTML报告作为备选...")
                generate_html_report(overall_results)
            else:
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
            
        # 显示正确的测试结果
        error_count = lib.get("error", 0)
        failed_count = lib.get("failed", 0)
        print(f"{status_icon} {lib['original_name']}{Fore.RESET}: {lib['passed']}/{lib['total']} 测试通过, {failed_count} 失败, {error_count} 错误")
    
    print(f"{'='*50}")

if __name__ == "__main__":
    start_time = time.time()
    current_time = time.strftime("%Y/%m/%d %H时%M分%S秒", time.localtime(start_time))
    print(f"测试开始时间: {current_time}")
    
    # 获取用户输入的SDK版本
    from config import SDK_API_MAPPING, set_sdk_version
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
            from config import set_release_mode
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
