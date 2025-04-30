import os
import time
import json
from collections import defaultdict
import colorama  # 添加彩色输出支持

# 初始化colorama
colorama.init()

from utils.config import HTML_REPORT_DIR, OVERALL_RESULTS_FILE
from core.ReadExcel import read_libraries_from_excel, parse_git_url

# 定义彩色输出函数
def print_error(message):
    """打印红色错误信息"""
    print(f"{colorama.Fore.RED}{message}{colorama.Style.RESET_ALL}")

def print_warning(message):
    """打印黄色警告信息"""
    print(f"{colorama.Fore.YELLOW}{message}{colorama.Style.RESET_ALL}")

def print_success(message):
    """打印绿色成功信息"""
    print(f"{colorama.Fore.GREEN}{message}{colorama.Style.RESET_ALL}")

def update_overall_results(overall_results):
    """更新总体结果文件"""
    try:
        # 确保目录存在
        results_dir = os.path.dirname(OVERALL_RESULTS_FILE)
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            print(f"创建目录: {results_dir}")
        
        # 保存总体结果到JSON文件
        with open(OVERALL_RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(overall_results, f, ensure_ascii=False, indent=2) # type: ignore
            
    except Exception as e:
        print_error(f"更新总体结果文件时出错: {str(e)}")

def generate_html_report(overall_results):
    """生成详细的HTML测试报告"""
    try:
        print("生成详细HTML测试报告...")
        
        # 获取库列表和URL信息
        libraries, _, urls = read_libraries_from_excel()
        
        # 获取当前时间作为报告时间
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        # 按仓库类型分组库
        repo_groups = defaultdict(lambda: defaultdict(list))
        
        for lib in overall_results.get("libraries", []):
            lib_name = lib.get("name", "")
            if lib_name in urls:
                url = urls[lib_name]
                owner, repo_name, sub_dir = parse_git_url(url)
                
                # 特殊处理openharmony_tpc_samples仓库
                if repo_name == "openharmony_tpc_samples" and sub_dir:
                    repo_groups[owner]["openharmony_tpc_samples"].append((lib_name, lib, sub_dir))
                else:
                    repo_groups[owner][repo_name].append((lib_name, lib, ""))
        
        # 生成每个库的单独报告
        for lib in overall_results.get("libraries", []):
            try:
                lib_name = lib.get("name", "")
                if not lib_name:
                    print_warning("警告: 发现没有名称的库，跳过生成报告")
                    continue
                    
                lib_report_path = generate_library_report(lib, lib_name, urls.get(lib_name, ""), HTML_REPORT_DIR)
                
                # 只有当报告路径有效时才添加到库信息中
                if lib_report_path:
                    lib["report_path"] = os.path.relpath(lib_report_path, HTML_REPORT_DIR)
                else:
                    print_warning(f"警告: 库 {lib_name} 的报告生成失败，跳过添加报告路径")
            except Exception as e:
                print_error(f"处理库 {lib.get('name', '未知库')} 报告时出错: {str(e)}")
                # 继续处理下一个库，不中断整体报告生成
        
        # 生成总体报告
        try:
            main_report_path = generate_main_report(overall_results, repo_groups, current_time, HTML_REPORT_DIR)
            if main_report_path:
                print_success(f"HTML报告已生成: {main_report_path}")
                return main_report_path
            else:
                default_path = os.path.join(HTML_REPORT_DIR, "index.html")
                print_warning(f"主报告生成可能不完整，使用默认路径: {default_path}")
                return default_path
        except Exception as e:
            print_error(f"生成主报告时出错: {str(e)}")
            # 返回默认报告路径，即使生成失败
            return os.path.join(HTML_REPORT_DIR, "index.html")
        
    except Exception as e:
        print_error(f"生成HTML报告时出错: {str(e)}")
        # 不打印完整的堆栈跟踪，只显示简单的错误信息
        return None

def generate_library_report(lib, lib_name, url, HTML_REPORT_DIR):
    """为单个库生成HTML报告"""
    try:
        # 类型检查
        if not isinstance(lib, dict):
            print_error(f"错误: 库 {lib_name} 的数据不是有效的字典格式")
            return None
            
        # 创建库报告目录
        lib_dir = os.path.join(HTML_REPORT_DIR, "libraries")
        if not os.path.exists(lib_dir):
            os.makedirs(lib_dir)
        
        # 准备库报告数据
        lib_passed = lib.get("passed", 0)
        lib_failed = lib.get("failed", 0)
        lib_total = lib.get("total", 0)
        
        # 修改状态判断逻辑：当总测试数为0时，状态应为"unknown"
        if lib_total == 0:
            lib_status = "unknown"
        else:
            lib_status = lib.get("status", "unknown")
            
        pass_rate = (lib_passed / lib_total * 100) if lib_total > 0 else 0
        
        # 解析Git URL
        owner, repo_name, sub_dir = parse_git_url(url)
        repo_info = f"{owner}/{repo_name}"
        if sub_dir:
            repo_info += f" (子目录: {sub_dir})"
        
        # 生成测试类级别的HTML内容
        test_classes_html = ""
        if "test_results" in lib:
            # 确保test_results是字典类型
            if not isinstance(lib["test_results"], dict):
                print_error(f"错误: 库 {lib_name} 的测试结果不是有效的字典格式")
                # 创建一个空的测试结果部分
                test_classes_html = "<p>无有效的测试结果数据</p>"
            else:
                for test_class, tests in lib["test_results"].items():
                    try:
                        class_passed = all(test.get('status') == 'passed' for test in tests if isinstance(test, dict))
                        class_status = "passed" if class_passed else "failed"
                        class_status_icon = "✓" if class_passed else "✗"
                        
                        # 计算测试类的总执行时间，增加错误处理
                        class_time_ms = 0
                        for test in tests:
                            if not isinstance(test, dict):
                                continue
                            test_time_str = test.get('time', '0 ms')
                            if isinstance(test_time_str, str):
                                try:
                                    time_value = test_time_str.replace('ms', '').strip()
                                    class_time_ms += int(time_value)
                                except (ValueError, TypeError):
                                    # 忽略无法解析的时间值
                                    pass
                        
                        # 生成测试方法级别的HTML内容
                        test_methods_html = ""
                        for test in tests:
                            if not isinstance(test, dict):
                                continue
                                
                            test_name = test.get('name', 'unknown')
                            test_status = test.get('status', 'unknown')
                            test_time = test.get('time', '0ms')
                            test_status_icon = "✓" if test_status == "passed" else "✗"
                            test_status_class = "passed" if test_status == "passed" else "failed"
                            
                            # 添加错误信息（如果有）
                            error_html = ""
                            if 'error_stack' in test and test['error_stack']:
                                error_html = f"""
                                <div class="error-details">
                                    <pre>{test['error_stack']}</pre>
                                </div>
                                """
                            
                            test_methods_html += f"""
                            <tr class="{test_status_class}">
                                <td><span class="status-icon">{test_status_icon}</span> {test_name}</td>
                                <td>{test_status}</td>
                                <td>{test_time}</td>
                            </tr>
                            {error_html}
                            """
                        
                        # 添加测试类信息
                        test_classes_html += f"""
                        <div class="test-class {class_status}">
                            <div class="test-class-header" onclick="toggleTestClass(this)">
                                <span class="status-icon">{class_status_icon}</span>
                                <span class="test-class-name">{test_class}</span>
                                <span class="test-class-time">{class_time_ms} ms</span>
                            </div>
                            <div class="test-methods">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>测试方法</th>
                                            <th>状态</th>
                                            <th>耗时</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {test_methods_html}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                        """
                    except Exception as e:
                        print_error(f"处理库 {lib_name} 的测试类 {test_class} 时出错: {str(e)}")
                        # 继续处理下一个测试类
        
        # 生成库报告HTML
        lib_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>测试报告 - {lib_name}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        .summary {{
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary-title {{
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .summary-item {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
        }}
        .passed {{
            color: #28a745;
        }}
        .failed {{
            color: #dc3545;
        }}
        .unknown {{
            color: #6c757d;
        }}
        .status-icon {{
            font-weight: bold;
            margin-right: 5px;
        }}
        .test-class {{
            margin-bottom: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            overflow: hidden;
        }}
        .test-class.passed {{
            border-left: 5px solid #28a745;
        }}
        .test-class.failed {{
            border-left: 5px solid #dc3545;
        }}
        .test-class-header {{
            padding: 10px 15px;
            background-color: #f8f9fa;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .test-class-name {{
            font-weight: bold;
            flex-grow: 1;
        }}
        .test-class-time {{
            color: #6c757d;
            font-size: 0.9em;
        }}
        .test-methods {{
            display: none;
            padding: 0 15px 15px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f8f9fa;
        }}
        tr.passed td {{
            background-color: rgba(40, 167, 69, 0.1);
        }}
        tr.failed td {{
            background-color: rgba(220, 53, 69, 0.1);
        }}
        .error-details {{
            margin: 10px 0;
            padding: 10px;
            background-color: #f8d7da;
            border-radius: 5px;
            font-family: monospace;
            white-space: pre-wrap;
            font-size: 0.9em;
        }}
        .repo-info {{
            background-color: #e9ecef;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .repo-info a {{
            color: #007bff;
            text-decoration: none;
        }}
        .repo-info a:hover {{
            text-decoration: underline;
        }}
        .back-link {{
            margin-bottom: 20px;
        }}
        .back-link a {{
            color: #007bff;
            text-decoration: none;
        }}
        .back-link a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="back-link">
        <a href="../index.html">← 返回总体报告</a>
    </div>
    
    <h1>测试报告 - {lib_name}</h1>
    
    <div class="repo-info">
        <strong>仓库信息:</strong> <a href="{url}" target="_blank">{repo_info}</a>
    </div>
    
    <div class="summary">
        <div class="summary-title">测试摘要</div>
        <div class="summary-item">
            <span>总测试数:</span>
            <span>{lib_total}</span>
        </div>
        <div class="summary-item">
            <span>通过测试:</span>
            <span class="passed">{lib_passed}</span>
        </div>
        <div class="summary-item">
            <span>失败测试:</span>
            <span class="failed">{lib_failed}</span>
        </div>
        <div class="summary-item">
            <span>通过率:</span>
            <span class="{lib_status}">{pass_rate:.2f}%</span>
        </div>
        <div class="summary-item">
            <span>状态:</span>
            <span class="{lib_status}">{lib_status.upper()}</span>
        </div>
    </div>
    
    <h2>测试详情</h2>
    {test_classes_html}
    
    <script>
        function toggleTestClass(element) {{
            const testMethods = element.nextElementSibling;
            if (testMethods.style.display === "block") {{
                testMethods.style.display = "none";
            }} else {{
                testMethods.style.display = "block";
            }}
        }}
        
        // 页面加载时展开所有失败的测试类
        document.addEventListener('DOMContentLoaded', function() {{
            const failedClasses = document.querySelectorAll('.test-class.failed .test-class-header');
            failedClasses.forEach(function(element) {{
                element.nextElementSibling.style.display = "block";
            }});
        }});
    </script>
</body>
</html>
        """
        
        # 保存库报告
        lib_report_path = os.path.join(lib_dir, f"{lib_name.replace(' ', '_')}.html")
        with open(lib_report_path, 'w', encoding='utf-8') as f:
            f.write(lib_html)
        
        return lib_report_path
    
    except Exception as e:
        print_error(f"生成库报告时出错 ({lib_name}): {str(e)}")
        return None

def generate_main_report(overall_results, repo_groups, current_time, HTML_REPORT_DIR):
    """生成主HTML报告"""
    try:
        # 准备报告数据
        total_tests = overall_results.get("total", 0)
        passed_tests = overall_results.get("passed", 0)
        failed_tests = overall_results.get("failed", 0)
        unknown_tests = total_tests - passed_tests - failed_tests
        total_libs = overall_results.get("total_libs", 0)
        passed_libs = overall_results.get("passed_libs", 0)
        failed_libs = total_libs - passed_libs
        unknown_libs = sum(1 for lib in overall_results.get("libraries", []) 
                      if lib.get("total", 0) == 0)
        
        # 计算通过率
        test_pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        lib_pass_rate = (passed_libs / total_libs * 100) if total_libs > 0 else 0
        
        # 修复报告链接路径
        for lib in overall_results.get("libraries", []):
            if "report_path" in lib:
                # 确保路径正确，不要包含重复的libraries目录
                lib["report_path"] = lib["report_path"].replace("libraries/libraries/", "libraries/")
        
        # 生成仓库分组的HTML内容
        repo_groups_html = ""
        
        for owner in sorted(repo_groups.keys()):
            owner_html = f"""
            <div class="repo-owner">
                <h2>{owner}</h2>
            """
            
            for repo_name in sorted(repo_groups[owner].keys()):
                repo_html = f"""
                <div class="repo">
                    <h3>{repo_name}</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>库名称</th>
                                <th>状态</th>
                                <th>通过/总计</th>
                                <th>通过率</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                """
                
                # 特殊处理openharmony_tpc_samples仓库
                if repo_name == "openharmony_tpc_samples":
                    # 按子目录分组
                    sub_dirs = defaultdict(list)
                    for lib_name, lib, sub_dir in repo_groups[owner][repo_name]:
                        sub_dirs[sub_dir].append((lib_name, lib))
                    
                    for sub_dir in sorted(sub_dirs.keys()):
                        repo_html += f"""
                        <tr class="sub-dir-header">
                            <td colspan="5"><strong>子目录: {sub_dir}</strong></td>
                        </tr>
                        """
                        
                        for lib_name, lib in sub_dirs[sub_dir]:
                            lib_passed = lib.get("passed", 0)
                            lib_total = lib.get("total", 0)
                            
                            # 修改状态判断逻辑：当总测试数为0时，状态应为"unknown"
                            if lib_total == 0:
                                lib_status = "unknown"
                            else:
                                lib_status = lib.get("status", "unknown")
                                
                            lib_pass_rate = (lib_passed / lib_total * 100) if lib_total > 0 else 0
                            status_class = "passed" if lib_status == "passed" else ("unknown" if lib_status == "unknown" else "failed")
                            report_path = lib.get("report_path", "")
                            
                            repo_html += f"""
                            <tr class="{status_class}">
                                <td>{lib_name}</td>
                                <td class="{status_class}">{lib_status.upper()}</td>
                                <td>{lib_passed}/{lib_total}</td>
                                <td>{lib_pass_rate:.2f}%</td>
                                <td><a href="libraries/{lib_name.replace(' ', '_')}.html" class="view-report">查看报告</a></td>
                            </tr>
                            """
                else:
                    # 常规仓库
                    for lib_name, lib, _ in repo_groups[owner][repo_name]:
                        lib_passed = lib.get("passed", 0)
                        lib_total = lib.get("total", 0)
                        
                        # 修改状态判断逻辑：当总测试数为0时，状态应为"unknown"
                        if lib_total == 0:
                            lib_status = "unknown"
                        else:
                            lib_status = lib.get("status", "unknown")
                            
                        lib_pass_rate = (lib_passed / lib_total * 100) if lib_total > 0 else 0
                        status_class = "passed" if lib_status == "passed" else ("unknown" if lib_status == "unknown" else "failed")
                        report_path = lib.get("report_path", "")
                        
                        repo_html += f"""
                        <tr class="{status_class}">
                            <td>{lib_name}</td>
                            <td class="{status_class}">{lib_status.upper()}</td>
                            <td>{lib_passed}/{lib_total}</td>
                            <td>{lib_pass_rate:.2f}%</td>
                            <td><a href="{report_path}" class="view-report">查看报告</a></td>
                        </tr>
                        """
                
                repo_html += """
                        </tbody>
                    </table>
                </div>
                """
                
                owner_html += repo_html
            
            owner_html += "</div>"
            repo_groups_html += owner_html
        
        # 生成主报告HTML
        main_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenHarmony 三方库测试报告</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        .summary {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            flex: 1;
            min-width: 200px;
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary-title {{
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 10px;
            color: #2c3e50;
        }}
        .summary-value {{
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .summary-label {{
            color: #6c757d;
        }}
        .passed {{
            color: #28a745;
        }}
        .failed {{
            color: #dc3545;
        }}
        .unknown {{
            color: #6c757d;
        }}
        .repo-owner {{
            margin-bottom: 30px;
        }}
        .repo {{
            margin-bottom: 20px;
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f1f1f1;
        }}
        tr.passed td {{
            background-color: rgba(40, 167, 69, 0.1);
        }}
        tr.failed td {{
            background-color: rgba(220, 53, 69, 0.1);
        }}
        tr.sub-dir-header td {{
            background-color: #e9ecef;
            font-weight: bold;
        }}
        .view-report {{
            display: inline-block;
            padding: 5px 10px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 3px;
        }}
        .view-report:hover {{
            background-color: #0056b3;
        }}
        .timestamp {{
            color: #6c757d;
            font-size: 0.9em;
            margin-bottom: 20px;
        }}
        .progress-bar {{
            height: 20px;
            background-color: #e9ecef;
            border-radius: 5px;
            margin-top: 5px;
            overflow: hidden;
        }}
        .progress-bar-fill {{
            height: 100%;
            background-color: #28a745;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <h1>OpenHarmony 三方库测试报告</h1>
    <div class="timestamp">生成时间: {current_time}</div>
    
    <div class="summary">
        <div class="summary-card">
            <div class="summary-title">测试用例统计</div>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-value">{total_tests}</div>
                    <div class="summary-label">总测试数</div>
                </div>
                <div class="summary-item passed">
                    <div class="summary-value">{passed_tests}</div>
                    <div class="summary-label">通过测试</div>
                </div>
                <div class="summary-item failed">
                    <div class="summary-value">{failed_tests}</div>
                    <div class="summary-label">失败测试</div>
                </div>
                <div class="summary-item unknown">
                    <div class="summary-value">{unknown_tests}</div>
                    <div class="summary-label">未执行测试</div>
                </div>
            </div>
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-bar-fill" style="width: {test_pass_rate}%;"></div>
                </div>
                <div class="progress-text">通过率: {test_pass_rate:.2f}%</div>
            </div>
        </div>
        
        <div class="summary-card">
            <div class="summary-title">三方库统计</div>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-value">{total_libs}</div>
                    <div class="summary-label">总库数</div>
                </div>
                <div class="summary-item passed">
                    <div class="summary-value">{passed_libs}</div>
                    <div class="summary-label">通过库数</div>
                </div>
                <div class="summary-item failed">
                    <div class="summary-value">{failed_libs}</div>
                    <div class="summary-label">失败库数</div>
                </div>
                <div class="summary-item unknown">
                    <div class="summary-value">{unknown_libs}</div>
                    <div class="summary-label">未测试库数</div>
                </div>
            </div>
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-bar-fill" style="width: {lib_pass_rate}%;"></div>
                </div>
                <div class="progress-text">通过率: {lib_pass_rate:.2f}%</div>
            </div>
        </div>
    </div>
    
    <h2>测试结果详情</h2>
    {repo_groups_html}
    
    <script>
        // 页面加载时自动展开失败的测试
        document.addEventListener('DOMContentLoaded', function() {{
            // 可以添加交互功能，如筛选、排序等
        }});
    </script>
</body>
</html>
        """
        
        # 保存主报告
        main_report_path = os.path.join(HTML_REPORT_DIR, "index.html")
        with open(main_report_path, 'w', encoding='utf-8') as f:
            f.write(main_html)
        return main_report_path
    
    except Exception as e:
        print(f"生成主报告时出错: {str(e)}")
        return None