from ExtractTestDetails import extract_test_details
from GenerateTestReport import generate_test_report
from GenerateAllureReport import generate_allure_report
from GenerateHtmlReport import generate_html_report, update_overall_results

import sys
import os
# 动态添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 全局变量，用于存储所有库的测试结果
all_libraries_results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "total_libs": 0,
    "passed_libs": 0,
    "libraries": []
}

# 回调函数列表，用于通知测试完成
report_completion_callbacks = []

def register_completion_callback(callback):
    """注册一个在报告生成完成时调用的回调函数"""
    if callback not in report_completion_callbacks:
        report_completion_callbacks.append(callback)

def generate_reports(test_names, output, original_name):
    """
    生成测试报告并更新总体测试结果

    该函数为单个库生成测试报告,并将结果整合到总体测试结果中。主要功能包括:
    - 解析测试结果数据
    - 生成HTML格式的详细测试报告
    - 生成Allure测试报告
    - 更新总体测试结果统计
    - 保存库的详细测试信息

    参数:
        test_names: 测试用例名称列表
        output: 测试输出结果
        original_name: 被测试库的名称

    异常:
        捕获并打印所有异常信息

    全局变量:
        all_libraries_results: 存储所有库的测试结果
    """
    try:
        global all_libraries_results
        
        # 确保output是字符串类型
        if not isinstance(output, str):
            print(f"警告：测试输出不是字符串类型 (实际类型: {type(output)})，尝试转换")
            if isinstance(output, (tuple, list)) and len(output) > 0:
                output = str(output[0])
            else:
                output = str(output) if output is not None else ""
        
        # 解析测试结果（只需解析一次）
        extracted_data = extract_test_details(output)
        
        # 从返回的字典中提取各个部分
        test_results = extracted_data["test_results"]
        summary = extracted_data["summary"]
        class_times = extracted_data["class_times"]

        try:
            # 生成HTML详细报告
            generate_test_report(test_names, output, original_name)  # 使用original_name而不是library_name
        except Exception as html_err:
            print(f"生成HTML报告时出错: {str(html_err)}")
        
        try:
            # 生成Allure报告
            generate_allure_report(test_results, original_name)  # 使用original_name而不是library_name
        except Exception as allure_err:
            print(f"生成Allure报告时出错: {str(allure_err)}")
        
        # 更新总体结果
        lib_status = "passed" if summary["failed"] == 0 and summary["error"] == 0 else "failed"
        
        # 添加当前库的结果到全局结果中
        all_libraries_results["total"] += summary["total"]
        all_libraries_results["passed"] += summary["passed"]
        all_libraries_results["failed"] += summary["failed"]
        all_libraries_results["total_libs"] += 1
        if lib_status == "passed":
            all_libraries_results["passed_libs"] += 1
            
        # 添加库的详细信息
        all_libraries_results["libraries"].append({
            "name": original_name,  # 使用original_name而不是library_name
            "passed": summary["passed"],
            "failed": summary["failed"],
            "total": summary["total"],
            "status": lib_status,
            "test_results": test_results,  # 保存详细的测试结果
            "summary": summary  # 保存摘要信息
        })
        
        # 更新总体结果文件（但不生成最终报告）
        update_overall_results(all_libraries_results)
        
        print(f"\n库 {original_name} 的测试报告已生成")  # 使用original_name而不是library_name
        
    except Exception as e:
        print(f"生成报告时出错: {str(e)}")
        import traceback
        traceback.print_exc()

def generate_final_report():
    """在所有库测试完成后生成最终的HTML总览报告"""
    try:
        global all_libraries_results
        
        # 生成最终的HTML总览报告
        generate_html_report(all_libraries_results)
        
        print("\n所有测试报告已生成完成")
        
        # 调用所有注册的回调函数，通知测试完成
        for callback in report_completion_callbacks:
            try:
                callback()
            except Exception as callback_err:
                print(f"执行完成回调时出错: {str(callback_err)}")
        
        # 重置全局变量，为下一次运行做准备
        all_libraries_results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "total_libs": 0,
            "passed_libs": 0,
            "libraries": []
        }
        
    except Exception as e:
        print(f"生成最终报告时出错: {str(e)}")
        import traceback
        traceback.print_exc()