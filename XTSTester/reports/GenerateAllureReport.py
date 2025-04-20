import os
import json
import time
import uuid

from utils.config import ALLURE_RESULTS_DIR


def generate_allure_report(test_data, library_name):
    """生成Allure格式的测试报告"""
    try:
        # 确保allure-results目录存在
        os.makedirs(ALLURE_RESULTS_DIR, exist_ok=True)
        
        # 检查test_data的格式并提取test_results
        if isinstance(test_data, dict) and "test_results" in test_data:
            # 如果传入的是extract_test_details返回的完整字典
            test_results = test_data["test_results"]
            summary = test_data.get("summary", {})
        else:
            # 向后兼容：如果直接传入了test_results
            test_results = test_data
            summary = {}
        
        # 确保test_results是字典类型
        if not isinstance(test_results, dict):
            print(f"警告：库 {library_name} 的测试结果不是有效的字典格式")
            # 创建一个空字典作为默认值
            test_results = {}

        # 为每个测试生成唯一的UUID
        lib_uuid = str(uuid.uuid4())

        # 创建库级别的测试套件结果
        lib_total = sum(len(tests) for tests in test_results.values())
        lib_passed = sum(1 for cls in test_results.values() for test in cls if isinstance(test, dict) and test.get('status') == 'passed')
        lib_failed = lib_total - lib_passed
        
        # 修改状态判断逻辑：当总测试数为0时，状态应为"unknown"，与HTML报告保持一致
        if lib_total == 0:
            lib_status = "unknown"
        else:
            lib_status = "passed" if lib_failed == 0 else "failed"

        # 创建库级别的测试套件JSON，但不写入文件
        suite_result = {
            "uuid": lib_uuid,
            "historyId": f"{library_name}_suite",
            "name": f"{library_name} 测试套件",
            "fullName": f"{library_name}",
            "status": lib_status,
            "stage": "finished",
            "start": int(time.time() * 1000),
            "stop": int(time.time() * 1000) + 1000,  # 假设套件执行时间为1秒
            "labels": [
                {"name": "suite", "value": library_name},
                {"name": "package", "value": library_name}
            ],
            "statusDetails": {
                "message": f"总计: {lib_passed}/{lib_total} 测试通过, {lib_failed} 失败"
            }
        }

        # 如果没有测试结果，创建一个特殊的测试结果表示未执行
        if lib_total == 0:
            test_uuid = str(uuid.uuid4())
            result_file = os.path.join(ALLURE_RESULTS_DIR, f"{test_uuid}-result.json")
            
            test_result = {
                "uuid": test_uuid,
                "historyId": f"{library_name}_no_tests",
                "name": f"{library_name} - 未执行测试",
                "fullName": f"{library_name}.no_tests",
                "status": "skipped",  # 使用skipped表示未执行
                "stage": "finished",
                "start": int(time.time() * 1000),
                "stop": int(time.time() * 1000) + 100,
                "labels": [
                    {"name": "suite", "value": library_name},
                    {"name": "package", "value": library_name},
                    {"name": "testClass", "value": "NoTests"},
                    {"name": "testMethod", "value": "no_tests"}
                ],
                "statusDetails": {
                    "message": "该库没有执行任何测试",
                    "trace": "可能原因：库构建失败、没有测试用例或测试框架问题"
                }
            }
            
            # 写入测试结果文件
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(test_result, f, ensure_ascii=False, indent=2)
                
            print(f"为库 {library_name} 创建了未执行测试的Allure记录")
            return

        # 创建Allure结果文件
        for test_class, tests in test_results.items():
            # 确保tests是列表类型
            if not isinstance(tests, list):
                print(f"警告：库 {library_name} 的测试类 {test_class} 的测试结果不是有效的列表格式")
                continue  # 跳过无效的测试类
                
            for test in tests:
                # 增加类型检查，确保test是字典类型
                if not isinstance(test, dict):
                    print(f"警告：库 {library_name} 的测试类 {test_class} 中的测试结果不是有效的字典格式")
                    continue  # 跳过无效的测试结果

                test_status = test.get('status', 'unknown')
                test_name = test.get('name', 'unknown')

                # 确保test_time是字符串并处理时间格式
                test_time_str = test.get('time', '0 ms')
                if isinstance(test_time_str, str):
                    test_time_ms = int(test_time_str.replace('ms', '').strip())
                else:
                    test_time_ms = 0

                # 生成测试的UUID
                test_uuid = str(uuid.uuid4())
                
                # 创建Allure结果文件
                result_file = os.path.join(ALLURE_RESULTS_DIR, f"{test_uuid}-result.json")
                
                # 准备测试结果数据
                test_result = {
                    "uuid": test_uuid,
                    "historyId": f"{library_name}.{test_class}.{test_name}",
                    "name": test_name,
                    "fullName": f"{library_name}.{test_class}.{test_name}",
                    "status": test_status,
                    "stage": "finished",
                    "start": int(time.time() * 1000),
                    "stop": int(time.time() * 1000) + test_time_ms,
                    "labels": [
                        {"name": "suite", "value": library_name},
                        {"name": "package", "value": library_name},
                        {"name": "testClass", "value": test_class},
                        {"name": "testMethod", "value": test_name}
                    ]
                }
                
                # 如果测试失败，添加错误信息
                if test_status == "failed" and 'error_stack' in test:
                    test_result["statusDetails"] = {
                        "message": test.get('error_message', '测试失败'),
                        "trace": test.get('error_stack', '')
                    }
                
                # 写入测试结果文件
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(test_result, f, ensure_ascii=False, indent=2)  # type: ignore
        
        print(f"已为库 {library_name} 生成Allure报告数据")
        
    except Exception as e:
        print(f"生成库 {library_name} 的Allure报告时出错: {str(e)}")
        import traceback
        traceback.print_exc()
